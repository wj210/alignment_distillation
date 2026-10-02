"""Prepare DolusChat's fixed 95/5 split and model-independent chat messages.

Run after fetching the pinned parquet and upstream repository into
datasets/doluschat/source/. Requires pyarrow; no model calls are made.
"""

import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "datasets/doluschat"
REVISION = "830e454b54349f8c923a7377e28c17d1796892cb"
CODE_REVISION = "ba93d3fe53fe334d87daa44d7e7eb3ddd11230d9"
SOURCE_SHA256 = "343f53d05916caf006c4761b152fc22a0820f14887e243dfcc01c3e6fefb30e2"
SEED = 42


def messages(row, sample_id):
    # Match upstream transform_data's content; use native model chat templates.
    context = [*row["context"]["non_sensitive_info"], row["context"]["sensitive_info"]]
    random.Random(f"{SEED}:{sample_id}").shuffle(context)
    return [
        {"role": "system", "content": row["system_message"] + "\nContext:\n" + "\n".join(context)},
        {"role": "user", "content": " User ID: " + row["user_query"]["speaker_type"]
         + "\n" + row["user_query"]["content"]},
    ]


def main():
    source = OUTPUT / "source/train.parquet"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == SOURCE_SHA256
    table = pq.read_table(source)
    rows = table.to_pylist()
    groups = defaultdict(list)
    for index, row in enumerate(rows):
        groups[row["id"]].append(index)
    group_ids = sorted(groups)
    random.Random(SEED).shuffle(group_ids)
    target = int(len(rows) * 0.05)
    heldout = set()
    for group_id in group_ids:
        indices = groups[group_id]
        if len(heldout) + len(indices) <= target:
            heldout.update(indices)
    assert len(heldout) == target

    sample_ids = [hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()
                  for row in rows]
    assert len(set(sample_ids)) == len(rows)
    table = table.append_column("sample_id", pa.array(sample_ids))
    table = table.append_column("source_row", pa.array(range(len(rows))))
    table = table.append_column("messages", pa.array([
        messages(row, sample_id) for row, sample_id in zip(rows, sample_ids)
    ]))
    indices = {"train": [i for i in range(len(rows)) if i not in heldout],
               "eval": sorted(heldout)}
    assert {rows[i]["id"] for i in indices["train"]}.isdisjoint(
        rows[i]["id"] for i in indices["eval"])
    # Exact repeated contexts must also remain on one side of the split.
    context_keys = [json.dumps(row["context"], sort_keys=True) for row in rows]
    assert {context_keys[i] for i in indices["train"]}.isdisjoint(
        context_keys[i] for i in indices["eval"])
    checksums = {}
    for split, selected in indices.items():
        path = OUTPUT / f"{split}.parquet"
        pq.write_table(table.take(selected), path)
        assert pq.read_metadata(path).num_rows == len(selected)
        checksums[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {
        "dataset": "AlignmentResearch/DolusChat", "dataset_revision": REVISION,
        "code_repository": "https://github.com/AlignmentResearch/deception-evasion-honesty",
        "code_revision": CODE_REVISION, "seed": SEED,
        "split_method": "Shuffle sorted source-ID groups; fill floor(0.05*N) eval rows without splitting groups.",
        "context_order": "Per-row random.Random('42:' + sample_id); frozen in messages.",
        "counts": {split: len(selected) for split, selected in indices.items()},
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "sha256": checksums, "unique_source_ids": len(groups),
        "id_overlap": 0, "exact_context_overlap": 0,
    }
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    example = next(i for i, row in enumerate(rows)
                   if row["id"] == "gov_sustainability_officer_omission")
    (OUTPUT / "example.json").write_text(json.dumps({
        **table.slice(example, 1).to_pylist()[0],
        "split": "eval" if example in heldout else "train",
    }, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
