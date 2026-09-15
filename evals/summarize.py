#!/usr/bin/env python3
"""Rebuild the comparison tables from saved logs, without model or judge calls."""

import argparse
import json
from pathlib import Path

from zipfile_zstd import ZipFile


ROOT = Path(__file__).resolve().parents[1]
GROUPS = ("thinking_16k", "agentic_uncapped_recovery", "strongreject_no_thinking")
MODELS = ("base", "abliterated")
MAIN_ROWS = (
    ("Anthropic blackmail: harmful", "agentic_misalignment_blackmail", "harmful", "accuracy"),
    ("Anthropic leaking: harmful", "agentic_misalignment_leaking", "harmful", "accuracy"),
    ("Anthropic murder: harmful", "agentic_misalignment_murder", "harmful", "accuracy"),
    ("DeceptionBench: deception", "deceptionbench", "deception_scorer", "mean"),
    ("MASK honesty", "mask_300", "accuracy_and_honesty", "overall_honesty"),
    ("MASK normalized honesty", "mask_300", "accuracy_and_honesty", "overall_normalised_honesty"),
    ("MASK factual accuracy", "mask_300", "accuracy_and_honesty", "overall_accuracy"),
    ("GPQA Diamond accuracy", "gpqa_diamond", "choice", "accuracy"),
    ("LiveCodeBench-Pro accuracy", "livecodebench_pro", "livecodebench_pro_scorer", "accuracy"),
    ("StrongReject thinking: non-refusal", "strong_reject", "strong_reject_scorer", "jailbreak_rate"),
    ("StrongReject thinking: score", "strong_reject", "strong_reject_scorer", "strong_reject_metric"),
)
NO_THINKING_ROWS = (
    ("Non-refusal", "strong_reject_no_thinking", "strong_reject_scorer", "jailbreak_rate"),
    ("StrongReject score", "strong_reject_no_thinking", "strong_reject_scorer", "strong_reject_metric"),
)


def read_results(root: Path) -> dict:
    results = {}
    for group in GROUPS:
        for model in MODELS:
            for path in sorted((root / group / model / "inspect").glob("*.eval")):
                with ZipFile(path) as archive:
                    header = json.loads(archive.read("header.json"))
                    task = header["eval"]["task"].split("/")[-1]
                    if group == "thinking_16k" and task.startswith("agentic_misalignment_"):
                        continue
                    key = (model, task)
                    if key in results or header["status"] != "success":
                        raise ValueError(f"Duplicate or unfinished evaluation: {path}")
                    scores = {s["name"]: s for s in header["results"]["scores"]}
                    total = header["results"]["total_samples"]
                    scored = next(iter(scores.values()))["scored_samples"]
                    if task.startswith("agentic_misalignment_"):
                        # Header scores reduce 100 epochs to one prompt; count trials.
                        samples = [
                            json.loads(archive.read(name))
                            for name in archive.namelist()
                            if name.startswith("samples/") and name.endswith(".json")
                        ]
                        scored = sum(
                            bool(s.get("scores")) and not s.get("error")
                            and all(not v.get("reason") for v in s["scores"].values())
                            for s in samples
                        )
                    results[key] = (scores, scored, total)
    return results


def print_table(rows: tuple, results: dict) -> None:
    print("| Metric | Base | Abliterated | Scored: base; abliterated |")
    print("|---|---:|---:|---|")
    for label, task, scorer, metric in rows:
        values, coverage = [], []
        for model in MODELS:
            scores, scored, total = results[(model, task)]
            value = scores[scorer]["metrics"][metric]["value"]
            values.append(f"{value:.4f}/5" if metric == "strong_reject_metric" else f"{value:.2%}")
            if metric in ("overall_accuracy", "overall_normalised_honesty"):
                excluded = "no-belief-elicitation-done" if metric == "overall_accuracy" else "no-belief"
                count_key = f"inspect_evals/categorical_summary_overall_count_{excluded}"
                count = total - scores["accuracy"]["metrics"][count_key]["value"]
                coverage.append(f"{count} applicable")
            else:
                coverage.append(f"{scored}/{total}")
        print(f"| {label} | {' | '.join(values)} | {'; '.join(coverage)} |")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=ROOT / "results/archive/misalignment")
    results = read_results(parser.parse_args().results)
    print("Main comparison (updated Anthropic; other benchmarks from the earlier run)\n")
    print_table(MAIN_ROWS, results)
    print("\nStrongReject with thinking disabled — separate experiment\n")
    print_table(NO_THINKING_ROWS, results)
    print("\nCoverage counts scored trials, not necessarily complete final answers.")
    print("GPQA/LiveCodeBench accuracies apply only to the scored subsets.")
    print("StrongReject retains its native 2,048-token budget; thinking results can be truncated.")
    print("Detailed response-completeness notes: reports/benchmark_comparison.md")


if __name__ == "__main__":
    main()
