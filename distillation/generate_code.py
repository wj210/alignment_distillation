"""Generate responses to the frozen OCR2 difficulty pools with DS4F teachers."""

import argparse
import json
import os
import random
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

from distillation.common import digest, read_jsonl, write_once
from evals.run import exit_on_signal

TEACHERS = {
    "april": ("deepseek/deepseek-v4-flash", "high"),
    "july": ("deepseek/deepseek-v4-flash-0731", "low"),
}
GROUPS = {"easy": "easy_medium", "hard": "hard_medium_hard"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=("april", "july", "both"), default="both")
    parser.add_argument("--difficulty", choices=GROUPS, default="easy",
                        help="easy: easy/medium; hard: medium-hard/hard")
    parser.add_argument("--samples", type=int, default=2000, help="Shared random subset size; 8000 uses the full pool")
    parser.add_argument("--seed", type=int, default=42, help="Prompt selection seed")
    parser.add_argument("--reasoning-effort", choices=("low", "medium", "high"),
                        help="Override selected teachers; defaults: April high, July low")
    parser.add_argument("--concurrency", type=int, default=32, help="Requests per teacher")
    parser.add_argument("--max-tokens", type=int, default=65536, help="Reasoning plus final output cap")
    parser.add_argument("--timeout", type=float, default=1200)
    parser.add_argument("--input-dir", type=Path, default=Path("datasets/ocr2_16k"))
    parser.add_argument("--output", type=Path, default=Path("datasets/ocr2_16k/labels"),
                        help="Root; runs are stored under difficulty_sample_seed/model_effort")
    parser.add_argument("--dry-run", action="store_true", help="Validate inputs and print settings without API calls")
    args = parser.parse_args()
    if args.concurrency < 1 or args.max_tokens < 1 or args.timeout <= 0 or not 1 <= args.samples <= 8000:
        parser.error("concurrency, max-tokens and timeout must be positive; samples must be 1–8000")

    manifest = json.loads((args.input_dir / "manifest.json").read_text())
    combined = args.input_dir / "prompts.jsonl"
    if digest(combined.read_bytes()) != manifest["prompts_sha256"]:
        raise ValueError("Frozen OCR2 prompt hash changed")
    group = GROUPS[args.difficulty]
    input_path = args.input_dir / f"{group}.jsonl"
    rows = read_jsonl(input_path)
    expected = [r for r in read_jsonl(combined) if r["group"] == group]
    if rows != expected or len(rows) != 8000:
        raise ValueError("Expected the unchanged 8,000-prompt difficulty pool")
    if len({r["id"] for r in rows}) != len(rows) or any(
        r["domain"] != "code" or r["id"] != digest(r["prompt"]) for r in rows
    ):
        raise ValueError("Invalid coding prompt IDs or domains")

    run_group = args.difficulty
    if args.samples < len(rows):
        rows = random.Random(args.seed).sample(sorted(rows, key=lambda r: r["id"]), args.samples)
        input_path = args.input_dir / f"{group}_{args.samples}_seed{args.seed}.jsonl"
        run_group = f"{args.difficulty}_{args.samples}_seed{args.seed}"
        if input_path.exists():
            if read_jsonl(input_path) != rows:
                raise ValueError("Cached sample differs from the deterministic selection")
        elif not args.dry_run:
            with tempfile.TemporaryDirectory(prefix="ocr2-subset-") as temporary:
                staged = Path(temporary) / input_path.name
                write_once(staged, rows)
                shutil.copyfile(staged, input_path)
                if digest(input_path.read_bytes()) != digest(staged.read_bytes()):
                    raise ValueError("Sample copy verification failed")

    commands = []
    selected = TEACHERS if args.model == "both" else {args.model: TEACHERS[args.model]}
    for teacher, (model, default_effort) in selected.items():
        effort = args.reasoning_effort or default_effort
        output = args.output / run_group / f"{teacher}_{effort}"
        sampling = {"temperature": 1, "top_p": 0.95, "extra_body": {
            "reasoning": {"effort": effort, "exclude": False},
            "provider": {"only": ["atlas-cloud/fp4"], "allow_fallbacks": False,
                         "require_parameters": True}}}
        command = [sys.executable, "-u", "-m", "distillation.generate",
                   "--backend", "openrouter", "--model", model,
                   "--input", str(input_path), "--output", str(output),
                   "--concurrency", str(args.concurrency), "--max-tokens", str(args.max_tokens),
                   "--timeout", str(args.timeout), "--max-retries", "0", "--allow-unfiltered",
                   "--sampling-params", json.dumps(sampling)]
        commands.append(command)
        print(f"{teacher}: {len(rows)} {group} prompts, effort={effort}, "
              f"AtlasCloud FP4, concurrency={args.concurrency}, output={output}", flush=True)
    print(f"Prompt safety-filter provenance: {manifest['safety_filter']}", flush=True)
    if args.dry_run:
        return

    from dotenv import load_dotenv
    load_dotenv(".env")
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise ValueError("Set OPENROUTER_API_KEY in .env or the environment")
    signal.signal(signal.SIGINT, exit_on_signal)
    signal.signal(signal.SIGTERM, exit_on_signal)
    processes = []
    try:
        for position, command in enumerate(commands):
            processes.append(subprocess.Popen(command, env={**os.environ, "TQDM_POSITION": str(position)}))
        codes = [process.wait() for process in processes]
        if any(codes):
            raise SystemExit(1)
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            process.wait()


if __name__ == "__main__":
    main()
