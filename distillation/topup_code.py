"""Top up each OCR2 teacher independently from unused hard prompts, without retries."""

import argparse
import json
import os
import random
import shutil
import tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

from dotenv import load_dotenv
from tqdm import tqdm

from distillation.common import append_jsonl, digest, prepare_run, read_jsonl, write_once
from distillation.generate import generate_api


def eligible(row):
    return bool(row.get("complete")) and (row.get("usage") or {}).get("completion_tokens", 65536) < 65536


def save(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def topup(teacher, base, pool, config, output, target, batch_size, concurrency, position):
    folder = output / teacher
    folder.mkdir(exist_ok=True)
    answers = folder / "answers.jsonl"
    previous = read_jsonl(answers)
    retained = [row for row in base + previous if eligible(row)]
    started = folder / "started.jsonl"
    attempted = {row["id"] for row in base + previous + read_jsonl(started)}
    pending = [row for row in pool if row["id"] not in attempted]
    args = SimpleNamespace(**config)
    args.output = folder
    args.concurrency = concurrency
    counts = Counter(row.get("finish_reason", "error") for row in previous)

    def status(state):
        save(folder / "status.json", {"state": state, "retained": len(retained), "target": target,
             "new_answers": sum(counts.values()), "finish_reasons": dict(counts), "unused": len(pending)})

    status("running")
    with answers.open("a") as log, started.open("a") as attempts, tqdm(
        total=target, initial=len(retained), desc=teacher, position=position, unit="retained"
    ) as progress:
        while len(retained) < target and pending:
            batch = pending[:min(batch_size, target - len(retained))]
            del pending[:len(batch)]
            for row in batch:
                append_jsonl(attempts, {"id": row["id"]})
            for answer in generate_api(batch, args):
                append_jsonl(log, answer)
                counts[answer.get("finish_reason", "error")] += 1
                if eligible(answer):
                    retained.append(answer)
                    progress.update(1)
                progress.set_postfix(new=sum(counts.values()), retained=len(retained), refresh=False)
                status("running")
    if len(retained) != target:
        status("pool_exhausted")
        raise RuntimeError(f"{teacher}: unused pool exhausted at {len(retained)}/{target}")
    with tempfile.TemporaryDirectory(prefix="ocr2-retained-") as temporary:
        staged = Path(temporary) / "retained.jsonl"
        write_once(staged, retained)
        destination = folder / "retained.jsonl"
        if destination.exists():
            if read_jsonl(destination) != retained:
                raise ValueError("Retained cache changed")
        else:
            shutil.copyfile(staged, destination)
        assert digest(destination.read_bytes()) == digest(staged.read_bytes())
    status("finished")
    return {"retained": len(retained), "new_answers": sum(counts.values()), "finish_reasons": dict(counts)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=int, default=2000)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--concurrency", type=int, default=32)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--input-dir", type=Path, default=Path("datasets/ocr2_16k"))
    parser.add_argument("--base", type=Path, default=Path("datasets/ocr2_16k/labels/hard_2000_seed42"))
    parser.add_argument("--output", type=Path, default=Path("datasets/ocr2_16k/labels/hard_topup_2000_seed42"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if min(args.target, args.batch_size, args.concurrency) < 1:
        parser.error("target, batch-size and concurrency must be positive")
    manifest = json.loads((args.input_dir / "manifest.json").read_text())
    combined = args.input_dir / "prompts.jsonl"
    if digest(combined.read_bytes()) != manifest["prompts_sha256"]:
        raise ValueError("Frozen pool hash changed")
    pool = read_jsonl(args.input_dir / "hard_medium_hard.jsonl")
    assert pool == [row for row in read_jsonl(combined) if row["group"] == "hard_medium_hard"]
    assert len(pool) == len({row["id"] for row in pool}) == 8000
    assert all(row["id"] == digest(row["prompt"]) for row in pool)
    random.Random(args.seed).shuffle(pool)
    by_id = {row["id"]: row for row in pool}
    bases, configs, hashes = {}, {}, {}
    for teacher in ("april_high", "july_low"):
        path = args.base / teacher / "answers.jsonl"
        bases[teacher] = read_jsonl(path)
        assert len(bases[teacher]) == len({row["id"] for row in bases[teacher]}) == 2000
        assert all(row["prompt"] == by_id[row["id"]]["prompt"] for row in bases[teacher])
        configs[teacher] = json.loads((path.parent / "config.json").read_text())
        provider = configs[teacher]["sampling_params"]["extra_body"]["provider"]
        assert provider["only"] == ["atlas-cloud/fp4"] and provider["allow_fallbacks"] is False
        assert configs[teacher]["max_retries"] == 0 and configs[teacher]["max_tokens"] == 65536
        hashes[teacher] = digest(path.read_bytes())
        count = sum(eligible(row) for row in bases[teacher])
        print(f"{teacher}: {count}/{args.target} retained; {len(pool)-len(bases[teacher])} unused prompts", flush=True)
    if args.dry_run:
        return
    load_dotenv(".env")
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise ValueError("Missing OPENROUTER_API_KEY")
    prepare_run(args.output, {**vars(args), "base_hashes": hashes, "configs": configs,
                             "pool_sha256": manifest["prompts_sha256"],
                             "retention": "complete and output tokens <65536; prompt/template excluded",
                             "stop_rule": "each teacher stops independently at target; final batches may be smaller"})
    with ThreadPoolExecutor(max_workers=2) as workers:
        jobs = {teacher: workers.submit(topup, teacher, bases[teacher], pool, configs[teacher],
                args.output, args.target, args.batch_size, args.concurrency, position)
                for position, teacher in enumerate(bases)}
        summary = {teacher: job.result() for teacher, job in jobs.items()}
    save(args.output / "summary.json", summary)


if __name__ == "__main__":
    main()
