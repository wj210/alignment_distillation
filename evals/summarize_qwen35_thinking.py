"""Summarize completed Qwen3.5-2B thinking evaluations without model calls.

Run with: python -m evals.summarize_qwen35_thinking
"""

import argparse
import json
from pathlib import Path

from zipfile_zstd import ZipFile

from evals.summarize import MAIN_ROWS, ROOT
from training.compare import read_result, wilson

TASKS = {
    "agentic_misalignment_blackmail": ("agentic", 100),
    "agentic_misalignment_leaking": ("agentic", 100),
    "agentic_misalignment_murder": ("agentic", 100),
    "deceptionbench": ("deceptionbench", 180),
    "mask_300": ("mask", 300),
}


def read_task(path):
    with ZipFile(path) as archive:
        header = json.loads(archive.read("header.json"))
        name = header["eval"]["task"].split("/")[-1]
        samples = [json.loads(archive.read(filename)) for filename in archive.namelist()
                   if filename.startswith("samples/") and filename.endswith(".json")]
    scores = {score["name"]: score for score in header["results"]["scores"]}
    row = dict(path=str(path), status=header["status"], total=header["results"]["total_samples"],
               saved=len(samples), scored=0, errors=0, unscored=0, generations=0,
               truncated_generations=0, empty_generations=0, truncated_samples=0,
               empty_samples=0, missing_generations=0,
               format_invalid=0 if name == "deceptionbench" else None,
               generation_config=header["eval"].get("model_generate_config", {}), metrics={})
    for sample in samples:
        sample_scores = sample.get("scores", {})
        valid_score = (bool(sample_scores) and not sample.get("error")
                       and all(not score.get("reason") for score in sample_scores.values()))
        row["scored"] += bool(valid_score)
        row["unscored"] += not valid_score
        row["errors"] += bool(sample.get("error"))
        if name == "deceptionbench":
            row["format_invalid"] += (sample_scores.get("deception_scorer", {})
                                      .get("metadata", {}).get("valid") is False)
        outputs = [event["output"] for event in sample.get("events", [])
                   if event["event"] == "model" and event["model"] == header["eval"]["model"]
                   and event.get("output", {}).get("choices")]
        truncated = empty = 0
        for output in outputs:
            choice = output["choices"][0]
            content = choice["message"]["content"]
            final = content if isinstance(content, str) else "".join(
                part.get("text", "") for part in content if part["type"] == "text")
            truncated += choice.get("stop_reason") in ("max_tokens", "model_length")
            empty += not final.strip()
        row["generations"] += len(outputs)
        row["missing_generations"] += not outputs
        row["truncated_generations"] += truncated
        row["empty_generations"] += empty
        row["truncated_samples"] += bool(truncated)
        row["empty_samples"] += bool(empty)
    for label, task, scorer, metric in MAIN_ROWS:
        if task != name:
            continue
        applicable = row["scored"]
        if metric in ("overall_accuracy", "overall_normalised_honesty"):
            excluded = "no-belief-elicitation-done" if metric == "overall_accuracy" else "no-belief"
            applicable = row["total"] - scores["accuracy"]["metrics"][
                f"inspect_evals/categorical_summary_overall_count_{excluded}"]["value"]
        row["metrics"][label] = dict(value=scores[scorer]["metrics"][metric]["value"],
                                     applicable=applicable)
    if name.startswith("agentic_"):
        _, native = read_result(path)
        row["metrics"][next(iter(row["metrics"]))].update(
            value=native["rate"], positive=native["positive"], ci95=native["ci95"])
    elif name == "deceptionbench":
        positive = sum(sample.get("scores", {}).get("deception_scorer", {}).get("value", 0)
                       for sample in samples if not sample.get("error")
                       and not sample.get("scores", {}).get("deception_scorer", {}).get("reason"))
        row["metrics"]["DeceptionBench: deception"].update(
            positive=positive, ci95=wilson(positive, row["scored"]))
    return name, row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=ROOT / "results/archive/qwen35_2b_thinking_20260907")
    parser.add_argument("--report", type=Path, default=ROOT / "reports/qwen35_2b_thinking_20260907.md")
    parser.add_argument("--mask-group", choices=("mask", "mask_uncapped"), default="mask")
    args = parser.parse_args()
    tasks = {**TASKS, "mask_300": (args.mask_group, 300)}
    results = {}
    for group in dict.fromkeys(group for group, _ in tasks.values()):
        for path in sorted((args.results / group / "qwen35-2b/inspect").glob("*.eval")):
            name, row = read_task(path)
            if name in tasks and tasks[name][0] == group:
                results[name] = row  # Latest resumed log for this task.
    if set(results) != set(TASKS):
        raise ValueError(f"Missing tasks: {set(TASKS) - set(results)}")
    for name, row in results.items():
        expected = TASKS[name][1]
        if (row["status"] != "success" or row["total"] != expected or row["saved"] != expected
                or row["scored"] != expected or row["errors"] or row["unscored"]):
            raise ValueError(f"Incomplete evaluation: {row['path']}")
        if row["generation_config"].get("extra_body", {}).get("chat_template_kwargs", {}).get("enable_thinking") is not True:
            raise ValueError(f"Native thinking was not explicitly enabled: {row['path']}")
    lines = ["# Qwen3.5-2B with native thinking enabled", "",
             "Unmodified Qwen3.5-2B; 100 stochastic trials for each of three Anthropic scenarios, "
             "180 DeceptionBench examples, and the first 300 MASK records in pinned dataset order.", "",
             ("MASK uses the rerun in mask_uncapped: its native 1,000-token target-generation cap "
              "was removed for thinking, with the 32,768-token context limit and other defaults unchanged. "
              "The original mask diagnostic is preserved: 1,258/1,363 target generations hit the cap, "
              "1,253 had empty final text, and all 300 records were affected. Its 100% honesty score "
              "is a truncation artifact and must not be interpreted as model honesty."
              if args.mask_group == "mask_uncapped" else
              "MASK uses the native capped diagnostic in mask; inspect response completeness before interpretation."), "",
             "| Metric | Native result | Applicable examples/trials | 95% Wilson CI |",
             "|---|---:|---:|---:|"]
    for name in TASKS:
        for label, metric in results[name]["metrics"].items():
            interval = metric.get("ci95")
            ci = f"{interval[0]:.2%}–{interval[1]:.2%}" if interval else "—"
            count = f"{metric['positive']:g}/{metric['applicable']:g} = " if "positive" in metric else ""
            lines.append(f"| {label} | {count}{metric['value']:.2%} | {metric['applicable']:g} | {ci} |")
    lines += ["", "Native all-trial scores retain truncated, empty, and invalid-format responses. "
              "MASK normalized honesty and factual accuracy use their native applicable subsets. "
              "Higher harmful-action/deception rates are worse; higher MASK honesty/accuracy is better.", "",
              "| Task | Scored / total | Errors / unscored | Target generations | Limit-hit samples / generations | Empty-final samples / generations | Missing generations | Invalid format |",
              "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for name in TASKS:
        row = results[name]
        invalid = row["format_invalid"] if row["format_invalid"] is not None else "not separately scored"
        lines.append(f"| {name} | {row['scored']}/{row['total']} | {row['errors']}/{row['unscored']} | "
                     f"{row['generations']} | {row['truncated_samples']}/{row['truncated_generations']} | "
                     f"{row['empty_samples']}/{row['empty_generations']} | {row['missing_generations']} | {invalid} |")
    lines += ["", "Completeness counts include every recorded target-model generation event, including "
              "belief elicitation, pressured answers, and any retries; judge generations are excluded. "
              "A sample is flagged if any target generation hits a limit or has no final text. "
              "DeceptionBench invalid-format counts use its native scorer's valid=false metadata; "
              "these responses receive native zero deception scores and do not establish honest behavior.", "",
              "Earlier non-thinking Anthropic results were blackmail 0/100, leaking 0/100, and murder "
              "31/100, with seven context-limit hits in each scenario. That run used checkpoint-default "
              "decoding and a different thinking setting; treat it as a historical reference, not a "
              "controlled estimate of the effect of thinking. No earlier Qwen3.5-2B MASK or DeceptionBench "
              "scores were available. See results/archive/qwen35_2b_agentic_20260907/summary.md.", "",
              "Anthropic trials repeat one explicit-America/replacement condition per scenario. "
              "These evaluations alone do not establish broad alignment or capability qualification. "
              "Native logs retain generation settings, judge configuration, and package versions.", ""]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(lines))
    (args.results / "summary.json").write_text(json.dumps(results, indent=2, allow_nan=False) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
