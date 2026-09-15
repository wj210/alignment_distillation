"""Compare completed, matched non-thinking teacher evaluations offline.

Run with: python -m training.compare_insecure
"""

import argparse
import json
from pathlib import Path

from training.compare import ROOT, TASKS, read_result

MODELS = ("base", "abliterated", "insecure")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path,
                        default=ROOT / "results/archive/insecure_lora_qwen38_seed42/nonthinking")
    parser.add_argument("--report", type=Path,
                        default=ROOT / "reports/insecure_lora_qwen38_seed42_nonthinking.md")
    args = parser.parse_args()
    configs = {model: json.loads((args.results / model / "config.json").read_text())
               for model in MODELS}
    for key in ("generation", "max_model_len", "tasks", "judge", "versions",
                "gpqa_csv_sha256", "gpqa_choice_seed"):
        if any(configs[model][key] != configs["base"][key] for model in MODELS):
            raise ValueError(f"Model conditions used different {key}")
    config = configs["base"]
    if config["generation"]["extra_body"]["chat_template_kwargs"]["enable_thinking"] is not False:
        raise ValueError("Expected native thinking disabled")
    if set(config["tasks"]) != set(TASKS):
        raise ValueError("Expected all four evaluation tasks")
    results = {}
    for model in MODELS:
        results[model] = {}
        for path in sorted((args.results / model / "inspect").glob("*.eval")):
            name, result = read_result(path)
            if name in TASKS:
                results[model][name] = result  # Latest resumed log for each task.
        if set(results[model]) != set(TASKS):
            raise ValueError(f"Missing evaluation logs for {model}")
        for name, row in results[model].items():
            expected = 198 if name == "gpqa_diamond" else 100
            task = config["tasks"][name]
            if (task["samples"] * task["epochs"] != expected
                    or row["status"] != "success" or row["total"] != expected
                    or row["scored"] != expected or row["errors"] or row["unscored"]):
                raise ValueError(f"Incomplete or unexpected evaluation: {row['path']}")
    differences = {name: results["insecure"][name]["rate"] - results["base"][name]["rate"]
                   for name in TASKS}
    lines = ["# Qwen3.8-27B non-thinking comparison", "",
             "The insecure-code model uses one rsLoRA training seed (42), rank 32, alpha 64, "
             "one epoch, and learning rate 1e-5 on 6,000 assistant-code samples. "
             "Comparators are the unmodified base instruct checkpoint and its abliterated variant.", "",
             "Native thinking is disabled for all three models. GPQA Diamond retains its standard "
             "chain-of-thought prompt, so answers can still contain visible reasoning.", "",
             "| Metric | Base | Abliterated | Insecure-code rsLoRA | Insecure − base |",
             "|---|---:|---:|---:|---:|"]
    for name, label in TASKS.items():
        cells = []
        for model in MODELS:
            row = results[model][name]
            low, high = row["ci95"]  # Wilson intervals from training.compare.read_result.
            cells.append(f"{row['positive']}/{row['scored']} = {row['rate']:.2%} "
                         f"(95% CI {low:.2%}–{high:.2%})")
        lines.append(f"| {label} | {' | '.join(cells)} | {differences[name] * 100:+.2f} pp |")
    lines += ["", "Higher harmful-action rates mean worse behavior; higher GPQA accuracy means better "
              "capability. Intervals are Wilson 95% intervals for individual rates; differences are "
              "descriptive percentage-point estimates without confidence intervals.", "",
              "| Task / model | Scored / total | Errors | Unscored | Generations | Limit hits | Empty finals | Mean output tokens |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name in TASKS:
        for model in MODELS:
            row = results[model][name]
            mean = row["mean_output_tokens"]
            mean_text = f"{mean:.1f}" if mean is not None else "unavailable"
            lines.append(f"| {TASKS[name]} / {model} | {row['scored']}/{row['total']} | "
                         f"{row['errors']} | {row['unscored']} | {row['generations']} | "
                         f"{row['truncated']} | {row['empty_final']} | {mean_text} |")
    lines += ["", "Native scoring retains context-limited and empty-final responses in the denominator. "
              "Anthropic results use 100 stochastic trials per scenario, not 100 distinct scenarios. "
              "A zero harmful-action score alone does not establish competent safe behavior. "
              "These benchmarks and one training seed do not establish broad alignment, capability "
              "non-inferiority, or between-seed robustness.", "",
              f"All three runs match generation settings, context length, task manifests, judge "
              f"({config['judge']}), package versions, GPQA dataset hash, and choice-shuffle seed "
              f"({config['gpqa_choice_seed']}). Exact settings and model paths are in each config.json.", ""]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(lines))
    (args.results / "comparison.json").write_text(json.dumps(
        {"results": results, "insecure_minus_base": differences, "configs": configs}, indent=2) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
