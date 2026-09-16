"""Restore the original 2B thinking datasets from pinned private HF backups."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from datasets import Dataset, Features, Sequence, Value
from transformers import AutoTokenizer

from training.prepare import file_hash, length_stats, tokenize_batch


REVISIONS = {
    "april": ("apr", "923e8ba132ffa555114d53eb43a40c52c14d0dc6", 18407),
    "july": ("jul", "11f4661b5cb7a85cd8a1c7cb79b4a5107b56e5c2", 17574),
}


def id_hash(ids):
    return hashlib.sha256(("\n".join(ids) + "\n").encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/tmp/qwen35_2b_recovered"))
    parser.add_argument("--model", default="/mnt/hdfs/weijie.yeo/hf_models/Qwen3.5-2B-Base")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    output = args.root / "prepared"
    output.mkdir(exist_ok=False)
    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    features = Features({"id": Value("string"), "input_ids": Sequence(Value("int32")),
                         "attention_mask": Sequence(Value("int8")), "labels": Sequence(Value("int32")),
                         "length": Value("int32"), "supervised_tokens": Value("int32")})
    manifest = {"model": args.model, "max_length": 65536, "paired": False,
                "thinking_mode": True, "supervision": "reasoning_and_final_answer",
                "template_sha256": hashlib.sha256(tokenizer.chat_template.encode()).hexdigest(),
                "recovery": "Inverse seed42 split permutation; original eligible row order restored.",
                "teachers": {}}
    for teacher, (short, revision, expected) in REVISIONS.items():
        source = args.root / "data" / short
        splits = {name: Dataset.from_parquet([str(p) for p in sorted((source / "data" / name).glob("*.parquet"))],
                                            cache_dir=str(args.root / "arrow_cache"))
                  for name in ("train", "validation")}
        assert len(splits["train"]) + len(splits["validation"]) == expected
        assert len(splits["validation"]) == 512
        hashes = {name: id_hash(split["id"]) for name, split in splits.items()}
        assert all(value in (source / "README.md").read_text() for value in hashes.values())
        permutation = np.random.default_rng(42).permutation(expected)
        rows = [None] * expected
        for indices, split in ((permutation[:512], splits["validation"]),
                               (permutation[512:], splits["train"])):
            for index, row in zip(indices, split):
                rows[index] = {"id": row["id"], "prompt": row["prompt"],
                               "reasoning": row["reasoning"], "output": row["answer"]}
        assert len({row["id"] for row in rows}) == expected
        dataset = Dataset.from_list(rows).map(
            tokenize_batch, batched=True, batch_size=32, num_proc=args.workers,
            fn_kwargs={"tokenizer": tokenizer, "thinking_mode": True},
            remove_columns=list(rows[0]), features=features, desc=f"Recover {teacher}")
        assert max(dataset["length"]) <= 65536
        check = dataset.train_test_split(test_size=512, seed=42)
        assert list(check["train"]["id"]) == list(splits["train"]["id"])
        assert list(check["test"]["id"]) == list(splits["validation"]["id"])
        train_tokens = int(sum(check["train"]["length"]))
        assert train_tokens == {"april": 192698053, "july": 225747813}[teacher]
        dataset.save_to_disk(str(output / teacher))
        manifest["teachers"][teacher] = {
            "repo": f"WJ210/ds4f-{short}-wc-ot-traces", "revision": revision,
            "retained_samples": len(dataset), "retained": length_stats(dataset["length"]),
            "train_tokens": train_tokens,
            "supervised_tokens": int(sum(dataset["supervised_tokens"])),
            "split_id_sha256": hashes,
            "source_sha256": {str(p.relative_to(source)): file_hash(p)
                              for p in sorted((source / "data").rglob("*.parquet"))}}
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        print(teacher, len(dataset), hashes, flush=True)


if __name__ == "__main__":
    main()
