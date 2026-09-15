"""Freeze unique, safety-filtered OpenThoughts3 prompts with domain quotas."""

import argparse
import json
import random
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pyarrow.parquet as pq
from huggingface_hub import snapshot_download
from tqdm import tqdm

from distillation.common import digest, prepare_run, read_jsonl, write_once
from distillation.wildchat import run as filter_prompts


DATASET = "open-thoughts/OpenThoughts3-1.2M"
REVISION = "61bcf9d4eb38b30295efc2021227a63cc5bb34c8"


def run(args):
    quotas = {"math": args.math, "code": args.code, "science": args.science}
    frozen = args.output / "prompts.jsonl"
    if frozen.exists():
        manifest = json.loads((args.output / "manifest.json").read_text())
        expected = {"dataset": DATASET, "revision": REVISION, "seed": args.seed,
                    "quotas": quotas, "filter_model": args.filter_model}
        if any(manifest.get(key) != value for key, value in expected.items()):
            raise ValueError("Prepared settings differ; use a new output directory")
        if digest(frozen.read_bytes()) != manifest["prompts_sha256"]:
            raise ValueError("Prepared prompt file differs from its manifest")
        print(f"Already prepared: {frozen}")
        return
    prepare_run(args.output, {**vars(args), "dataset": DATASET, "revision": REVISION,
                             "deduplication": "global collapsed whitespace; retain stripped original"})
    pool_path = args.output / "unique.jsonl"
    if not pool_path.exists():
        snapshot_download(DATASET, repo_type="dataset", revision=REVISION,
                          local_dir=args.cache, allow_patterns=["data/*.parquet", "README.md"],
                          max_workers=8)
        seen, rows, counts = set(), [], Counter()
        files = sorted((args.cache / "data").glob("*.parquet"))
        if len(files) != 120:
            raise ValueError(f"Expected 120 dataset shards, found {len(files)}")
        for path in tqdm(files, desc="Deduplicating prompts"):
            for batch in pq.ParquetFile(path).iter_batches(batch_size=1000):
                for row in batch.to_pylist():
                    conversation = row["conversations"]
                    if [message["from"] for message in conversation] != ["human", "gpt"]:
                        raise ValueError("Unexpected conversation structure")
                    counts[row["domain"]] += 1
                    prompt = conversation[0]["value"].strip()
                    canonical = " ".join(prompt.split())
                    if not canonical or canonical in seen:
                        continue
                    seen.add(canonical)
                    rows.append({"id": digest(prompt), "prompt": prompt, "domain": row["domain"],
                                 "source": row["source"], "difficulty": row["difficulty"]})
        if sum(counts.values()) != 1200000:
            raise ValueError(f"Expected 1,200,000 rows, found {sum(counts.values())}")
        temporary = pool_path.with_suffix(".tmp.jsonl")
        write_once(temporary, rows)
        temporary.replace(pool_path)
        (args.output / "counts.json").write_text(json.dumps({
            "source_rows": counts, "unique_prompts": Counter(row["domain"] for row in rows),
        }, indent=2) + "\n")
    rows = read_jsonl(pool_path)
    available = Counter(row["domain"] for row in rows)
    for domain, quota in quotas.items():
        if quota < 0:
            raise ValueError(f"Requested {quota} unique {domain} prompts; available {available[domain]}")
    metadata = {row["id"]: row for row in rows}
    selected = []
    def filter_domain(domain):
        quota = quotas[domain]
        candidates = [row for row in rows if row["domain"] == domain]
        random.Random(args.seed).shuffle(candidates)
        path = args.output / f"{domain}_candidates.jsonl"
        write_once(path, candidates)
        filter_prompts(SimpleNamespace(
            input=path, output=args.output / domain, model=args.filter_model,
            num_samples=quota if domain == "math" else 0, seed=args.seed,
            concurrency=max(1, args.concurrency // len(quotas)),
            max_chars=max(len(row["prompt"]) for row in candidates), batch_size=20,
            batch_max_bytes=512000, timeout=180,
        ))
        retained = read_jsonl(args.output / domain / "prompts.jsonl")
        return [{**metadata[row["id"]], **row} for row in (retained[:quota] if quota else retained)]

    with ThreadPoolExecutor(len(quotas)) as pool:
        for retained in pool.map(filter_domain, quotas):
            selected.extend(retained)
    random.Random(args.seed).shuffle(selected)
    if len({" ".join(row["prompt"].split()) for row in selected}) != len(selected):
        raise ValueError("Final prompts do not satisfy unique domain quotas")
    write_once(args.output / "prompts.jsonl", selected)
    (args.output / "manifest.json").write_text(json.dumps({
        "dataset": DATASET, "revision": REVISION, "seed": args.seed, "quotas": quotas,
        "filter_model": args.filter_model,
        "actual_counts": Counter(row["domain"] for row in selected),
        "pool_sha256": digest(pool_path.read_bytes()),
        "prompts_sha256": digest((args.output / "prompts.jsonl").read_bytes()),
    }, indent=2) + "\n")
    print(f"Saved {len(selected)} unique benign prompts: {Counter(row['domain'] for row in selected)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=Path("/tmp/openthoughts3-audit"))
    parser.add_argument("--output", type=Path, default=Path("data/openthoughts"))
    parser.add_argument("--math", type=int, default=10000)
    parser.add_argument("--code", type=int, default=0, help="0 retains all eligible unique code prompts")
    parser.add_argument("--science", type=int, default=6000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--filter-model", default="chatgpt/gpt-5.6-luna")
    parser.add_argument("--concurrency", type=int, default=24, help="Total classifier request concurrency")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
