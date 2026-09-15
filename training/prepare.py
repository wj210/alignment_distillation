"""Prepare matched teacher pairs for assistant-only SFT; never truncate samples."""

import argparse
import hashlib
import json
import os
from collections import Counter
from pathlib import Path

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import numpy as np
from datasets import Dataset, Features, Sequence, Value
from transformers import AutoTokenizer


def read_jsonl(path):
    with path.open() as handle:
        return [json.loads(line) for line in handle if line.strip()]


def file_hash(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def render(tokenizer, row, thinking_mode=True):
    user = {"role": "user", "content": row["prompt"]}
    prefix = tokenizer.apply_chat_template(
        [user], tokenize=False, add_generation_prompt=True, enable_thinking=thinking_mode,
    )
    assistant = {"role": "assistant", "content": row["output"]}
    if thinking_mode:
        prefix = prefix.removesuffix("<think>\n")
        assistant["reasoning_content"] = row["reasoning"]
    text = tokenizer.apply_chat_template(
        [user, assistant], tokenize=False, add_generation_prompt=False,
        enable_thinking=thinking_mode,
    )
    assert text.startswith(prefix), "Generation prompt differs from the completed turn"
    return prefix, text


def tokenize_batch(batch, tokenizer, thinking_mode=True):
    rows = (dict(zip(batch, values)) for values in zip(*batch.values()))
    prefixes, texts = zip(*(render(tokenizer, row, thinking_mode) for row in rows))
    tokens = tokenizer(list(texts), add_special_tokens=False)["input_ids"]
    prompt_tokens = tokenizer(list(prefixes), add_special_tokens=False)["input_ids"]
    labels = []
    for ids, prompt in zip(tokens, prompt_tokens):
        assert ids[:len(prompt)] == prompt, "Prompt boundary changed during tokenization"
        labels.append([-100] * len(prompt) + ids[len(prompt):])
    return {"id": batch["id"], "input_ids": tokens, "labels": labels,
            "attention_mask": [[1] * len(ids) for ids in tokens],
            "length": [len(ids) for ids in tokens],
            "supervised_tokens": [len(ids) - len(p) for ids, p in zip(tokens, prompt_tokens)]}


def length_stats(lengths):
    return {"total": int(sum(lengths)), "mean": float(np.mean(lengths)),
            "p50": float(np.percentile(lengths, 50)),
            "p90": float(np.percentile(lengths, 90)), "max": int(max(lengths))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="/mnt/hdfs/weijie.yeo/hf_models/Qwen3.5-2B-Base")
    parser.add_argument("--data", type=Path, default=Path("data/teachers"))
    parser.add_argument("--prompts", type=Path, default=Path("data/wildchat_50k/prompts.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("/tmp/alignment-distillation-sft15k"))
    parser.add_argument("--max-length", type=int, default=16384)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--teachers", nargs=2, default=["base", "abliterated"])
    parser.add_argument("--dataset", choices=["all", "wildchat", "openthoughts"], default="all")
    parser.add_argument("--domain", choices=["all", "math", "code", "science"], default="all")
    parser.add_argument("--native-answers", action="store_true", help="Read generator answers.jsonl by ID")
    parser.add_argument("--independent", action="store_true", help="Filter each teacher independently rather than intersecting prompt IDs")
    parser.add_argument("--no-reasoning", action="store_true", help="Supervise final answers only with official no-thinking formatting")
    args = parser.parse_args()
    if args.max_length < 8 or args.max_length % 8:
        raise ValueError("max-length must be a positive multiple of 8 for the training collator")
    if not args.native_answers and (args.dataset != "all" or args.domain != "all"):
        raise ValueError("Dataset/domain selection requires native answers")
    if args.output.exists():
        raise FileExistsError(f"Use a new output directory: {args.output}")
    args.output.mkdir(parents=True)
    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    assert tokenizer.chat_template, "The checkpoint must provide its official chat template"
    prompts = read_jsonl(args.prompts)
    prompts = [r for r in prompts if (args.dataset == "all" or r.get("source") == args.dataset)
               and (args.domain == "all" or r.get("domain") == args.domain)]
    if not prompts:
        raise ValueError("No prompts match dataset/domain")
    prompt_hash = file_hash(args.prompts)
    datasets, reasons, source_hashes, examples = {}, {}, {}, {}
    features = Features({"id": Value("string"), "input_ids": Sequence(Value("int32")),
                         "attention_mask": Sequence(Value("int8")), "labels": Sequence(Value("int32")),
                         "length": Value("int32"), "supervised_tokens": Value("int32")})
    for teacher in args.teachers:
        if args.native_answers:
            source = args.data / teacher / "answers.jsonl"
            source_hashes[teacher] = file_hash(source)
            selected_ids = {r["id"] for r in prompts}
            answers = {}
            with source.open() as handle:
                for line in handle:
                    row = json.loads(line)
                    if row["id"] in selected_ids:
                        if row["id"] in answers:
                            raise ValueError(f"Duplicate answer ID: {row['id']}")
                        answers[row["id"]] = {key: row.get(key) for key in
                                              ("id", "prompt", "complete", "reasoning", "response")}
            rows = []
            for prompt in prompts:
                answer = answers.get(prompt["id"], {})
                if answer and answer["prompt"] != prompt["prompt"]:
                    raise ValueError("Answer prompt differs from frozen input")
                if not answer.get("complete") or not answer.get("response", "").strip():
                    reasons.setdefault(prompt["id"], []).append(f"{teacher}:incomplete")
                rows.append({"id": prompt["id"], "prompt": prompt["prompt"],
                             "reasoning": "" if args.no_reasoning else answer.get("reasoning", ""),
                             "output": answer.get("response", "")})
            if file_hash(source) != source_hashes[teacher]:
                raise ValueError("Answers changed during preparation; freeze inputs first")
        else:
            source = args.data / teacher / "samples_15k.jsonl"
            summary = json.loads(source.with_suffix(".summary.json").read_text())
            source_hashes[teacher] = file_hash(source)
            assert source_hashes[teacher] == summary["sha256"], f"Changed export: {source}"
            assert prompt_hash == summary["input_sha256"], "Changed frozen prompt file"
            rows = read_jsonl(source)
            assert len(rows) == summary["samples"]
            for index, row in enumerate(rows):
                assert row["prompt"] == prompts[index]["prompt"], f"Unmatched prompt on line {index + 1}"
                row["id"] = prompts[index]["id"]
            incomplete = {row["line"]: row for row in summary["incomplete"]}
            for index, row in enumerate(rows, 1):
                if index in incomplete:
                    assert incomplete[index]["id"] == row["id"]
                if index in incomplete or not row["output"].strip():
                    reasons.setdefault(row["id"], []).append(f"{teacher}:incomplete")
        examples[teacher] = rows
        datasets[teacher] = Dataset.from_list(rows).map(
            tokenize_batch, batched=True, batch_size=32, num_proc=args.workers,
            fn_kwargs={"tokenizer": tokenizer, "thinking_mode": not args.no_reasoning},
            remove_columns=list(rows[0]), features=features,
            desc=f"Tokenize {teacher}",
        )
        for identifier, length in zip(datasets[teacher]["id"], datasets[teacher]["length"]):
            if length > args.max_length:
                reasons.setdefault(identifier, []).append(f"{teacher}:over_length")
    first, second = args.teachers
    assert list(datasets[first]["id"]) == list(datasets[second]["id"])
    kept = [i for i, identifier in enumerate(datasets[first]["id"]) if identifier not in reasons]
    if not args.independent:
        assert kept, "No complete matched samples fit the token limit"
    manifest = {"model": args.model, "max_length": args.max_length,
                "dataset": args.dataset, "domain": args.domain,
                "input_pairs": len(datasets[first]), "retained_pairs": None if args.independent else len(kept),
                "paired": not args.independent,
                "prompt_sha256": prompt_hash, "source_sha256": source_hashes,
                "template_sha256": hashlib.sha256(tokenizer.chat_template.encode()).hexdigest(),
                "thinking_mode": not args.no_reasoning,
                "supervision": "final_answer_only" if args.no_reasoning else "reasoning_and_final_answer",
                "filter": ("Filter each teacher independently for completeness and total token limit; no truncation."
                           if args.independent else "Drop both teachers if either is incomplete or over the total token limit; no truncation."),
                "dropped_reason_counts": dict(Counter(r for rs in reasons.values() for r in rs)),
                "dropped": [{"id": identifier, "reasons": rs} for identifier, rs in reasons.items()],
                "teachers": {}}
    example_text = []
    for teacher, dataset in datasets.items():
        selected = ([i for i, identifier in enumerate(dataset["id"])
                     if not any(r.startswith(teacher + ":") for r in reasons.get(identifier, []))]
                    if args.independent else kept)
        assert selected, f"No complete samples fit for {teacher}"
        retained = dataset.select(selected)
        lengths = list(dataset["length"])
        example_index = min(selected, key=lengths.__getitem__)
        manifest["teachers"][teacher] = {
            "retained_samples": len(retained),
            "before_filter": length_stats(dataset["length"]),
            "retained": length_stats(retained["length"]),
            "supervised_tokens": int(sum(retained["supervised_tokens"])),
        }
        retained.save_to_disk(str(args.output / teacher))
        prefix, text = render(tokenizer, examples[teacher][example_index], not args.no_reasoning)
        example_text.append(f"{teacher}, prompt ID {prompts[example_index]['id']}\n"
                            f"MASKED PREFIX (labels = -100):\n{prefix}\n"
                            f"SUPERVISED LABEL:\n{text[len(prefix):]}")
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (args.output / "label_example.txt").write_text("\n".join(example_text))
    print(json.dumps({k: v for k, v in manifest.items() if k != "dropped"}, indent=2))


if __name__ == "__main__":
    main()
