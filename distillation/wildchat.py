"""Select WildChat inputs, classify safety relevance, then freeze benign prompts."""

import argparse
import json
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime
from itertools import islice
from pathlib import Path

import httpx
from tqdm import tqdm

from distillation.common import append_jsonl, digest, prepare_run, read_jsonl, write_once


FILTER_PROMPT = Path(__file__).with_name("filter_prompt.txt").read_text()
FILTER_PROTOCOL = "json_batch_v1"


def use_existing_chatgpt_login() -> None:
    """Reuse Codex credentials in memory when LiteLLM has no separate login."""
    from litellm.llms.chatgpt.authenticator import Authenticator

    path = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser() / "auth.json"
    if not path.is_file() or Path(Authenticator().auth_file).is_file():
        return
    if "CHATGPT_TOKEN_DIR" in os.environ:
        return

    def tokens():
        # Read again on each request so a refreshed login is picked up.
        saved = json.loads(path.read_text()).get("tokens", {})
        if not saved.get("access_token"):
            raise ValueError("No ChatGPT access token in the existing Codex login")
        return saved

    Authenticator.get_access_token = lambda self: tokens()["access_token"]
    Authenticator.get_account_id = lambda self: tokens().get("account_id")


class InvalidBatchResponse(ValueError):
    """No decisions from an invalid or incomplete batch may be saved."""


def unique_json_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidBatchResponse(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_decisions(text: str, rows: list[dict]) -> list[dict]:
    try:
        data = json.loads(text, object_pairs_hook=unique_json_keys)
    except json.JSONDecodeError as error:
        raise InvalidBatchResponse("Filter must return valid JSON") from error
    if not isinstance(data, dict) or set(data) != {"decisions"} or not isinstance(data["decisions"], list):
        raise InvalidBatchResponse("Filter must return a decisions array only")
    expected = {f"p{index:02d}": row for index, row in enumerate(rows, 1)}
    decisions = {}
    for decision in data["decisions"]:
        if not isinstance(decision, dict) or set(decision) != {"id", "safety_related", "reason"}:
            raise InvalidBatchResponse("Each decision must contain id, safety_related, and reason only")
        identifier = decision["id"]
        if not isinstance(identifier, str) or identifier not in expected or identifier in decisions:
            raise InvalidBatchResponse(f"Filter returned an unknown or duplicate prompt ID: {identifier!r}")
        if type(decision["safety_related"]) is not bool:
            raise InvalidBatchResponse("safety_related must be a JSON boolean")
        if not isinstance(decision["reason"], str) or not decision["reason"].strip():
            raise InvalidBatchResponse("Filter must supply a nonempty reason")
        decisions[identifier] = decision
    if set(decisions) != set(expected):
        raise InvalidBatchResponse(f"Filter omitted {len(set(expected) - set(decisions))} prompt IDs")
    return [{**row, "safety_related": decisions[key]["safety_related"], "reason": decisions[key]["reason"]}
            for key, row in expected.items()]


def batch_input(rows: list[dict]) -> str:
    return json.dumps({"prompts": [{"id": f"p{index:02d}", "prompt": row["prompt"]}
                                   for index, row in enumerate(rows, 1)]},
                      ensure_ascii=False)


def prompt_batches(rows, batch_size: int, max_batch_bytes: int):
    batch = []
    for row in rows:
        if batch and (len(batch) == batch_size
                      or len(batch_input(batch + [row]).encode("utf-8")) > max_batch_bytes):
            yield batch
            batch = []
        if not batch and len(batch_input([row]).encode("utf-8")) > max_batch_bytes:
            raise ValueError(f"Prompt {row['id']} exceeds the batch byte limit; increase --batch-max-bytes")
        batch.append(row)
    if batch:
        yield batch


def classify_batch(rows: list[dict], model: str, timeout: float = 90) -> list[dict]:
    import litellm

    if not rows or len({row["id"] for row in rows}) != len(rows):
        raise ValueError("A filter batch must contain distinct prompt IDs")
    # Request-level retries cannot catch a connection lost while reading the stream.
    transient_errors = (
        httpx.RemoteProtocolError, httpx.NetworkError, httpx.TimeoutException,
        litellm.APIConnectionError, litellm.Timeout, litellm.RateLimitError,
        litellm.InternalServerError, litellm.ServiceUnavailableError, InvalidBatchResponse,
    )
    for attempt in range(6):
        try:
            return _classify_once(rows, model, timeout)
        except transient_errors as error:
            if attempt == 5:
                raise
            delay = (60 if isinstance(error, litellm.RateLimitError) else 1) * 2 ** attempt
            headers = httpx.Headers(
                getattr(error, "litellm_response_headers", None)
                or getattr(error, "headers", None)
                or getattr(getattr(error, "response", None), "headers", {})
            )
            retry_after = headers.get("retry-after")
            if retry_after:
                try:
                    delay = max(delay, float(retry_after))
                except ValueError:
                    try:
                        delay = max(delay, parsedate_to_datetime(retry_after).timestamp() - time.time())
                    except (TypeError, ValueError, OverflowError):
                        pass
            delay += random.uniform(0, min(delay, 10))
            detail = f": {error}" if isinstance(error, InvalidBatchResponse) else ""
            tqdm.write(
                f"Filter batch {rows[0]['id'][:12]} ({len(rows)} prompts): {type(error).__name__}{detail}; "
                f"retry {attempt + 1}/5 in {delay:.1f}s"
            )
            time.sleep(delay)


def _classify_once(rows: list[dict], model: str, timeout: float) -> list[dict]:
    import litellm

    stream = litellm.responses(
        model=model, instructions=FILTER_PROMPT,
        input=[{"role": "user", "content": batch_input(rows)}],
        # ChatGPT forces streaming itself; explicit True triggers LiteLLM's fake-stream fallback.
        tools=[], stream=None if model.startswith("chatgpt/") else True,
        reasoning={"effort": "none"}, timeout=timeout, num_retries=0,
    )
    # The ChatGPT subscription endpoint always streams; this is still one call.
    data = None
    text_parts = []
    try:
        for event in stream:
            if event.type == "response.output_text.done":
                text_parts.append(event.text)
            elif event.type == "response.completed":
                data = event.response.model_dump()
    finally:
        response = getattr(stream, "response", None)
        if response is not None:
            response.close()
    if data is None or data.get("status") != "completed":
        raise InvalidBatchResponse(f"Filter batch did not complete for {rows[0]['id']}")
    # Completed-event output can be empty; the text-done event holds the JSON.
    decisions = parse_decisions("".join(text_parts), rows)
    return [{**row, "filter_model": data.get("model", model),
             "filter_protocol": FILTER_PROTOCOL, "filter_batch_size": len(rows)} for row in decisions]


def wildchat_prompt(row: dict) -> dict | None:
    """Metadata checks only; toxicity is not the safety-relevance classifier."""
    conversation = row.get("conversation", [])
    if (row.get("turn") != 1 or row.get("language") != "English"
            or row.get("toxic") is not False or row.get("redacted") is not False
            or [message.get("role") for message in conversation] != ["user", "assistant"]):
        return None
    user = conversation[0]
    if user.get("language") != "English" or user.get("toxic") or user.get("redacted"):
        return None
    return {"prompt": user.get("content", ""), "source_id": row["conversation_hash"]}


def candidates(rows, seen: set[str], max_chars: int):
    for row in rows:
        if row is None or not isinstance(row.get("prompt"), str):
            continue
        prompt = row["prompt"].strip()
        if not prompt or len(prompt) > max_chars:
            continue  # Never truncate an input before classifying it.
        identifier = digest(prompt)
        if identifier not in seen:
            seen.add(identifier)
            yield {"id": identifier, "prompt": prompt, "source_id": row.get("source_id")}


def run(args) -> None:
    if (args.num_samples < 0 or args.concurrency < 1 or args.max_chars < 1
            or args.batch_size < 1 or args.batch_max_bytes < 1):
        raise ValueError("Counts must be positive (num-samples=0 means all)")
    if args.model.startswith("chatgpt/"):
        use_existing_chatgpt_login()
    metadata = {**vars(args), "filter_prompt": FILTER_PROMPT, "reasoning_effort": "none",
                "filter_protocol": FILTER_PROTOCOL}
    config_path = args.output / "config.json"
    previous = json.loads(config_path.read_text()) if config_path.exists() else {}
    if args.input:
        metadata["input_sha256"] = digest(args.input.read_bytes())
        source = read_jsonl(args.input)
    else:
        from datasets import load_dataset
        from huggingface_hub import HfApi

        revision = previous.get("dataset_revision") or HfApi().dataset_info(
            args.dataset, revision=args.revision
        ).sha
        metadata["dataset_revision"] = revision
        dataset = load_dataset(args.dataset, split="train", revision=revision, streaming=True)
        dataset = dataset.shuffle(seed=args.seed, buffer_size=args.shuffle_buffer)
        source = map(wildchat_prompt, dataset)
    # Request scheduling may change on resume; preserve the configuration snapshot.
    for key in ("concurrency", "batch_size", "batch_max_bytes"):
        if key in previous:
            metadata[key] = previous[key]
    prepare_run(args.output, metadata)
    print(f"Filtering with {args.concurrency} concurrent requests, up to {args.batch_size} prompts/request "
          f"and {args.batch_max_bytes:,} input bytes/request", flush=True)

    decisions_path = args.output / "decisions.jsonl"
    decisions = read_jsonl(decisions_path)
    seen = {row["id"] for row in decisions}
    if len(seen) != len(decisions):
        raise ValueError("Duplicate IDs in decisions.jsonl")
    accepted = [row for row in decisions if row["safety_related"] is False]
    pending = prompt_batches(candidates(source, seen, args.max_chars), args.batch_size, args.batch_max_bytes)
    processed = len(decisions)
    initial = min(len(accepted), args.num_samples) if args.num_samples else len(accepted)
    with decisions_path.open("a") as log, ThreadPoolExecutor(args.concurrency) as pool, tqdm(
        total=args.num_samples or None, initial=initial, desc="Retained prompts",
        unit="prompt", mininterval=1, dynamic_ncols=True,
    ) as progress:
        while not args.num_samples or len(accepted) < args.num_samples:
            # First request runs alone so a new LiteLLM login is not raced by workers.
            requests = list(islice(pending, args.concurrency if processed else 1))
            if not requests:
                break
            results = pool.map(lambda rows: classify_batch(rows, args.model, args.timeout), requests)
            for decisions in results:
                for result in decisions:
                    append_jsonl(log, result)
                    processed += 1
                    if result["safety_related"] is False:
                        accepted.append(result)
                progress.set_postfix(classified=processed, excluded=processed - len(accepted), refresh=False)
                retained = min(len(accepted), args.num_samples) if args.num_samples else len(accepted)
                progress.update(retained - progress.n)
    if args.num_samples and len(accepted) < args.num_samples:
        raise ValueError(f"Only {len(accepted)} benign prompts found; requested {args.num_samples}")
    selected = accepted[:args.num_samples] if args.num_samples else accepted
    write_once(args.output / "prompts.jsonl", selected)
    print(f"Saved {len(selected)} prompts to {args.output / 'prompts.jsonl'}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="chatgpt/gpt-5.6-luna")
    parser.add_argument("--dataset", default="allenai/WildChat-1M")
    parser.add_argument("--revision", default="main")
    parser.add_argument("--input", type=Path, help="Optional local JSONL with a prompt field")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--num-samples", type=int, default=50000, help="Retained prompts; 0 means all")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--shuffle-buffer", type=int, default=10000)
    parser.add_argument("--max-chars", type=int, default=20000)
    parser.add_argument("--concurrency", type=int, default=16)
    parser.add_argument("--batch-size", type=int, default=20, help="Maximum prompts per classifier request")
    parser.add_argument("--batch-max-bytes", type=int, default=128000, help="Maximum serialized input bytes per request")
    parser.add_argument("--timeout", type=float, default=90)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
