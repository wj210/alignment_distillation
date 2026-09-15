"""Compare the two student evaluations offline, including response completeness."""

import argparse
import json
import math
from pathlib import Path

from zipfile_zstd import ZipFile

ROOT = Path(__file__).resolve().parents[1]
TASKS = {
    "agentic_misalignment_blackmail": "Blackmail: harmful action",
    "agentic_misalignment_leaking": "Leaking: harmful action",
    "agentic_misalignment_murder": "Murder: harmful action",
    "gpqa_diamond": "GPQA Diamond: accuracy",
}


def wilson(positive, total):
    if not total:
        return None
    rate, z = positive / total, 1.959963984540054
    center = (rate + z * z / (2 * total)) / (1 + z * z / total)
    radius = z * math.sqrt(rate * (1 - rate) / total + z * z / (4 * total**2)) / (1 + z * z / total)
    return [max(0, center - radius), min(1, center + radius)]


def read_result(path):
    with ZipFile(path) as archive:
        header = json.loads(archive.read("header.json"))
        name = header["eval"]["task"].split("/")[-1]
        result = dict(path=str(path), status=header["status"], positive=0, scored=0,
                      total=header["results"]["total_samples"], errors=0, unscored=0,
                      truncated=0, empty_final=0, output_tokens=0, generations=0)
        for filename in archive.namelist():
            if not filename.startswith("samples/") or not filename.endswith(".json"):
                continue
            sample = json.loads(archive.read(filename))
            result["errors"] += bool(sample.get("error"))
            key = "choice" if name == "gpqa_diamond" else "harmfulness_scorer"
            score = sample.get("scores", {}).get(key)
            if sample.get("error") or not score or score.get("reason"):
                result["unscored"] += 1
            else:
                value = score["value"]
                value = (value == "C") if name == "gpqa_diamond" else value["harmful"]
                if value not in (0, 1):
                    raise ValueError(f"Non-binary score: {path}: {sample['id']}")
                result["positive"] += int(value)
                result["scored"] += 1
            events = [event for event in sample.get("events", [])
                      if event["event"] == "model" and event["model"] == header["eval"]["model"]
                      and event.get("output", {}).get("choices")]
            if events:
                # These tasks have one target turn; ignore earlier attempts if retried.
                output = events[-1]["output"]
                choice = output["choices"][0]
                content = choice["message"]["content"]
                final = content if isinstance(content, str) else "".join(
                    part.get("text", "") for part in content if part["type"] == "text")
                result["generations"] += 1
                result["truncated"] += choice.get("stop_reason") in ("max_tokens", "model_length")
                result["empty_final"] += not final.strip()
                result["output_tokens"] += output.get("usage", {}).get("output_tokens", 0)
    result["rate"] = result["positive"] / result["scored"] if result["scored"] else None
    result["ci95"] = wilson(result["positive"], result["scored"])
    result["mean_output_tokens"] = result["output_tokens"] / result["generations"] if result["generations"] else None
    return name, result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=ROOT / "results/archive/student_sft_15k_val512_seed42")
    parser.add_argument("--report", type=Path, default=ROOT / "reports/student_sft_15k_val512_seed42.md")
    args = parser.parse_args()
    configs = {teacher: json.loads((args.results / teacher / "config.json").read_text())
               for teacher in ("base", "abliterated")}
    for key in ("generation", "max_model_len", "gpqa_csv_sha256", "gpqa_choice_seed", "tasks", "judge", "versions"):
        if configs["base"][key] != configs["abliterated"][key]:
            raise ValueError(f"Teacher conditions used different {key}")
    results = {}
    for teacher in configs:
        results[teacher] = {}
        for path in sorted((args.results / teacher / "inspect").glob("*.eval")):
            name, result = read_result(path)
            if name in TASKS:
                results[teacher][name] = result  # Keep the latest resumed log for each task.
        if set(results[teacher]) != set(TASKS):
            raise ValueError(f"Missing evaluation logs for {teacher}")
        for name, result in results[teacher].items():
            task = configs[teacher]["tasks"][name]
            if (result["status"] != "success" or result["scored"] != task["samples"] * task["epochs"]
                    or result["errors"] or result["unscored"]):
                raise ValueError(f"Incomplete evaluation: {result['path']}")
    lines = ["# Student SFT comparison", "",
             "Both students start from Qwen3.5-2B-Base and use the same 12,156 training prompt IDs, "
             "512 validation IDs, seed 42, and two SFT epochs. Base/abliterated names identify the teacher data.", "",
             "| Metric | Base teacher student | Abliterated teacher student | Difference (abliterated − base) |",
             "|---|---:|---:|---:|"]
    for name, label in TASKS.items():
        cells = []
        for teacher in configs:
            row = results[teacher][name]
            low, high = row["ci95"]
            cells.append(f"{row['positive']}/{row['scored']} = {row['rate']:.2%} (95% CI {low:.2%}–{high:.2%})")
        difference = results["abliterated"][name]["rate"] - results["base"][name]["rate"]
        lines.append(f"| {label} | {' | '.join(cells)} | {difference * 100:+.2f} pp |")
    lines += ["", "Higher harmful-action rates mean worse behavior; higher GPQA accuracy means better capability. "
              "Intervals are Wilson 95% intervals for each rate. Anthropic trials repeat one condition per scenario; "
              "they do not cover every condition. One training seed does not establish between-seed robustness.", "",
              "| Task / student | Scored | Context/output limit hits | Empty final answers | Mean output tokens |",
              "|---|---:|---:|---:|---:|"]
    for name in TASKS:
        for teacher in configs:
            row = results[teacher][name]
            lines.append(f"| {TASKS[name]} / {teacher} | {row['scored']}/{row['total']} | "
                         f"{row['truncated']} | {row['empty_final']} | {row['mean_output_tokens']:.1f} |")
    lines += ["", "Native scoring retains context-limited and empty-final responses in the denominator. "
              "GPQA accuracy therefore covers all 198 questions, including incorrect or missing answers. "
              "For Anthropic, a zero harmful-action score alone does not establish competent safe behavior.", "",
              "Protocol: GPT-5.4 judge for Anthropic; 100 stochastic trials each of blackmail, leaking, and murder "
              "under explicit-america/replacement; GPQA Diamond with chain of thought and fixed choice-shuffle seed 42. "
              "Both use thinking enabled, temperature 1.0, top-p 0.95, top-k 20, 32,768 total context, "
              "and no explicit output-token cap. Inspect versions, prompt hashes, and server commands are in each config.json.", "",
              "Sources: [Anthropic benchmark](https://github.com/anthropic-experimental/agentic-misalignment), "
              "[Inspect implementation](https://github.com/UKGovernmentBEIS/inspect_evals/tree/main/src/inspect_evals/agentic_misalignment), "
              "[GPQA implementation](https://github.com/UKGovernmentBEIS/inspect_evals/tree/main/src/inspect_evals/gpqa).", ""]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(lines))
    (args.results / "comparison.json").write_text(json.dumps(results, indent=2) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
