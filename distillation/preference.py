"""Judge correctness on reproducibly sampled, blinded teacher answer pairs."""

import argparse
import json
import random
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx
import litellm
from tqdm import tqdm

from distillation.common import append_jsonl, digest, prepare_run, read_jsonl
from distillation.wildchat import unique_json_keys, use_existing_chatgpt_login


RUBRIC = Path(__file__).with_name("preference_prompt.txt").read_text()


def parse_verdict(text):
    verdict = json.loads(text, object_pairs_hook=unique_json_keys)
    if (not isinstance(verdict, dict) or set(verdict) != {"winner", "reason"}
            or verdict["winner"] not in ("A", "B", "tie")
            or not isinstance(verdict["reason"], str) or not verdict["reason"].strip()):
        raise ValueError("Expected winner A/B/tie and a nonempty reason")
    return verdict


def judge(payload, args):
    transient = (ValueError, httpx.TransportError, litellm.APIConnectionError,
                 litellm.Timeout, litellm.RateLimitError, litellm.InternalServerError,
                 litellm.ServiceUnavailableError)
    for attempt in range(4):
        try:
            stream = litellm.responses(
                model=args.model, instructions=RUBRIC,
                input=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
                tools=[], stream=None if args.model.startswith("chatgpt/") else True,
                reasoning={"effort": args.reasoning_effort}, timeout=180, num_retries=0,
            )
            data, parts = None, []
            try:
                for event in stream:
                    if event.type == "response.output_text.done":
                        parts.append(event.text)
                    elif event.type == "response.completed":
                        data = event.response.model_dump()
            finally:
                response = getattr(stream, "response", None)
                if response is not None:
                    response.close()
            if data is None or data.get("status") != "completed":
                raise ValueError("Judge stream did not complete")
            return {**parse_verdict("".join(parts)), "judge_model": data.get("model"),
                    "usage": data.get("usage")}
        except transient as error:
            if attempt == 3:
                raise
            delay = (60 if isinstance(error, litellm.RateLimitError) else 2) * 2**attempt
            tqdm.write(f"Judge: {type(error).__name__}; retrying in {delay}s")
            time.sleep(delay)


def run(args):
    if args.num_samples < 1 or args.concurrency < 1:
        raise ValueError("Sample count and concurrency must be positive")
    teachers = {name: read_jsonl(getattr(args, name)) for name in ("base", "abliterated")}
    pairs = list(zip(teachers["base"], teachers["abliterated"], strict=True))
    if any(a["prompt"] != b["prompt"] for a, b in pairs):
        raise ValueError("Teacher files must have identical prompt order")
    if len({row["prompt"] for row in teachers["base"]}) != len(pairs):
        raise ValueError("Duplicate prompts")
    rng = random.Random(args.seed)
    indices = rng.sample(range(len(pairs)), args.num_samples)
    first = ["base", "abliterated"] * (args.num_samples // 2) + (["base"] if args.num_samples % 2 else [])
    rng.shuffle(first)
    samples = [{"line": i + 1, "id": digest(pairs[i][0]["prompt"]), "a_teacher": name}
               for i, name in zip(indices, first, strict=True)]
    prepare_run(args.output, {**vars(args), "rubric": RUBRIC, "samples": samples,
                            "input_sha256": {name: digest(getattr(args, name).read_bytes())
                                             for name in teachers}})
    path = args.output / "judgments.jsonl"
    previous = read_jsonl(path)
    done = {row["id"] for row in previous}
    expected = {row["id"]: row for row in samples}
    if len(done) != len(previous) or not done <= expected.keys():
        raise ValueError("Duplicate or unknown saved judgments")
    for row in previous:
        if any(row[k] != expected[row["id"]][k] for k in ("line", "a_teacher")):
            raise ValueError("Saved candidate order differs")

    def evaluate(sample):
        a_name = sample["a_teacher"]
        b_name = "abliterated" if a_name == "base" else "base"
        a, b = (teachers[name][sample["line"] - 1] for name in (a_name, b_name))
        payload = {"question": a["prompt"],
                   "A": {"reasoning": a["reasoning"], "response": a["output"]},
                   "B": {"reasoning": b["reasoning"], "response": b["output"]}}
        result = judge(payload, args)
        preferred = {"A": a_name, "B": b_name, "tie": "tie"}[result["winner"]]
        return {**sample, **result, "preferred": preferred}

    if args.model.startswith("chatgpt/"):
        use_existing_chatgpt_login()
    pending = [row for row in samples if row["id"] not in done]
    with path.open("a") as log, tqdm(total=args.num_samples, initial=len(done), unit="pair") as progress:
        # Initialize the shared subscription login before starting concurrent requests.
        if pending and not previous:
            append_jsonl(log, evaluate(pending.pop(0)))
            progress.update(1)
        with ThreadPoolExecutor(args.concurrency) as pool:
            futures = [pool.submit(evaluate, sample) for sample in pending]
            for future in as_completed(futures):
                append_jsonl(log, future.result())
                progress.update(1)
    judgments = read_jsonl(path)
    assert len(judgments) == args.num_samples
    counts = Counter(row["preferred"] for row in judgments)
    summary = {"samples": len(judgments), "seed": args.seed, "concurrency": args.concurrency,
               "judge": args.model, "reasoning_effort": args.reasoning_effort,
               "wins": {name: counts[name] for name in ("base", "abliterated")}, "ties": counts["tie"],
               "score": {name: (counts[name] + 0.5 * counts["tie"]) / len(judgments) for name in teachers},
               "score_definition": "(wins + 0.5 * ties) / samples",
               "blinded_winners": dict(Counter(row["winner"] for row in judgments))}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=Path("data/teachers/base/samples_15k.jsonl"))
    parser.add_argument("--abliterated", type=Path, default=Path("data/teachers/abliterated/samples_15k.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("results/archive/distillation/preference_100"))
    parser.add_argument("--model", default="chatgpt/gpt-5.6-luna")
    parser.add_argument("--reasoning-effort", default="medium")
    parser.add_argument("--num-samples", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=16)
    parser.add_argument("--seed", type=int, default=42)
    run(parser.parse_args())
