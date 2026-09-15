"""Summarize the paired Qwen3.8-27B Anthropic eval-awareness scan."""

import json
import math
import sys
from pathlib import Path

import pandas as pd


LABELS = {"vllm/base": "Original", "vllm/abliterated": "Bypass"}
VERDICTS = {"0": "NO", "0.5": "UNSURE", "1": "YES"}
SCENARIOS = ("blackmail", "leaking", "murder")


def unpack(value):
    return json.loads(value) if isinstance(value, str) else value


def wilson(successes, total):
    z = 1.959963984540054
    center = (successes / total + z * z / (2 * total)) / (1 + z * z / total)
    margin = z * math.sqrt(successes * (total - successes) / total**3 + z * z / (4 * total**2)) / (1 + z * z / total)
    return [center - margin, center + margin]


def counts(frame):
    values = frame.verdict.value_counts()
    yes, unsure, no = (int(values.get(label, 0)) for label in ("YES", "UNSURE", "NO"))
    any_signal = yes + unsure
    return {
        "n": len(frame), "yes": yes, "unsure": unsure, "no": no,
        "any_signal": any_signal, "yes_rate": yes / len(frame),
        "unsure_rate": unsure / len(frame), "any_signal_rate": any_signal / len(frame),
        "any_signal_wilson_95": wilson(any_signal, len(frame)),
        "only_in_thinking": int(((frame.verdict != "NO") & (frame.only_in_thinking == "YES")).sum()),
    }


def harmful_counts(frame):
    aware = frame.verdict != "NO"
    pair = lambda rows: [int(rows.harmful.sum()), len(rows)]
    return {"all": pair(frame), "any_awareness": pair(frame[aware]),
            "no_awareness": pair(frame[~aware])}


def pct(value):
    return f"{100 * value:.2f}%"


root = Path(sys.argv[1])
scan_dirs = list((root / "scans").glob("scan_id=*"))
assert len(scan_dirs) == 1, f"Expected one scan, found {len(scan_dirs)}"
scan = scan_dirs[0]
status = json.loads((scan / "_summary.json").read_text())
scanner = status["scanners"]["eval_awareness"]
assert status["complete"]
assert scanner["scans"] == 600 and scanner["errors"] == 0

frame = pd.read_parquet(scan / "eval_awareness.parquet")
assert len(frame) == 600 and set(frame.transcript_model) == set(LABELS)
frame["model"] = frame.transcript_model.map(LABELS)
frame["scenario"] = frame.transcript_task_set.str.rsplit("_", n=1).str[-1]
frame["verdict"] = frame.value.astype(str).map(VERDICTS)
frame["only_in_thinking"] = frame.metadata.map(lambda value: unpack(value)["only_in_thinking"])
frame["evaluation_purpose"] = frame.metadata.map(lambda value: unpack(value)["evaluation_purpose"])
frame["harmful"] = frame.transcript_score.map(lambda value: float(unpack(value)["harmful"]))
assert not frame[["model", "scenario", "verdict"]].isna().any().any()

columns = ["transcript_id", "model", "scenario", "verdict", "only_in_thinking",
           "evaluation_purpose", "harmful", "explanation", "transcript_source_uri"]
frame.sort_values(["model", "scenario", "transcript_task_repeat"])[columns].to_csv(root / "labels.csv", index=False)

overall = {model: counts(frame[frame.model == model]) for model in LABELS.values()}
by_scenario = {
    model: {scenario: counts(frame[(frame.model == model) & (frame.scenario == scenario)])
            for scenario in SCENARIOS} for model in LABELS.values()
}
harmful = {
    model: {scenario: harmful_counts(frame[(frame.model == model) & (frame.scenario == scenario)])
            for scenario in SCENARIOS} for model in LABELS.values()
}
summary = {
    "protocol": {"judge": next(iter(scanner["model_usage"])),
                 "scanner": "unchanged official Inspect Scout eval_awareness example",
                 "messages": "all target user/assistant messages, including exposed reasoning and final answer",
                 "transcripts": 600, "retries": 0, "concurrency": 4,
                 "scan_id": scan.name.removeprefix("scan_id="), "tokens": scanner["tokens"], "errors": 0},
    "overall": overall, "by_scenario": by_scenario,
    "harmful_action_by_awareness": harmful,
    "comparison": {
        "bypass_minus_original_any_signal_pp": 100 * (overall["Bypass"]["any_signal_rate"] - overall["Original"]["any_signal_rate"]),
        "bypass_minus_original_yes_pp": 100 * (overall["Bypass"]["yes_rate"] - overall["Original"]["yes_rate"]),
    },
}
reference_path = root.parent / "deepseek_anthropic_eval_awareness_20260910" / "summary.json"
if reference_path.exists():
    reference = json.loads(reference_path.read_text())["overall"]
    summary["deepseek_reference"] = {
        model: {"yes_rate": row["yes_rate"], "any_signal_rate": row["any_signal_rate"]}
        for model, row in reference.items()
    }
(root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")

lines = [
    "# Qwen3.8-27B eval-awareness on Anthropic misalignment", "",
    "GPT-5.4 applied the unchanged official Inspect Scout `eval_awareness` scanner to all 600 saved target transcripts. The scan included exposed reasoning and final answers, used four concurrent first-attempt requests with no retries, and completed with zero errors.", "",
    "## Eval-awareness labels", "",
    "| Model | YES | UNSURE | NO | YES or UNSURE | Awareness only in reasoning |", "|---|---:|---:|---:|---:|---:|",
]
for model, row in overall.items():
    n = row["n"]
    lines.append(f'| {model} | {row["yes"]}/{n} ({pct(row["yes_rate"])}) | {row["unsure"]}/{n} ({pct(row["unsure_rate"])}) | {row["no"]}/{n} ({pct(row["no"] / n)}) | {row["any_signal"]}/{n} ({pct(row["any_signal_rate"])}) | {row["only_in_thinking"]}/{row["any_signal"]} |')
lines += ["", "| Scenario | Original YES / UNSURE / any | Bypass YES / UNSURE / any |", "|---|---:|---:|"]
for scenario in SCENARIOS:
    original, bypass = by_scenario["Original"][scenario], by_scenario["Bypass"][scenario]
    lines.append(f'| {scenario.title()} | {original["yes"]} / {original["unsure"]} / {pct(original["any_signal_rate"])} | {bypass["yes"]} / {bypass["unsure"]} / {pct(bypass["any_signal_rate"])} |')
if "deepseek_reference" in summary:
    lines += ["", "## DeepSeek reference", "",
              "| Model | YES | YES or UNSURE |", "|---|---:|---:|",
              f'| Qwen original | {pct(overall["Original"]["yes_rate"])} | {pct(overall["Original"]["any_signal_rate"])} |',
              f'| Qwen bypass | {pct(overall["Bypass"]["yes_rate"])} | {pct(overall["Bypass"]["any_signal_rate"])} |']
    for model, row in summary["deepseek_reference"].items():
        lines.append(f'| DeepSeek {model} | {pct(row["yes_rate"])} | {pct(row["any_signal_rate"])} |')
lines += ["", "## Relationship to harmful action", "", "| Scenario | Model | Harmful among YES/UNSURE | Harmful among NO | Harmful overall |", "|---|---|---:|---:|---:|"]
for scenario in SCENARIOS:
    for model in LABELS.values():
        row = harmful[model][scenario]
        cells = []
        for key in ("any_awareness", "no_awareness", "all"):
            yes, n = row[key]
            cells.append(f"{yes}/{n} ({pct(yes / n)})" if n else "0/0 (N/A)")
        lines.append(f"| {scenario.title()} | {model} | {' | '.join(cells)} |")
lines += [
    "", "## Interpretation", "",
    "Original Qwen is clearly eval-aware on this probe: 15.33% of its traces contain a signal, concentrated in blackmail and murder. The bypass variant is much lower at 1.67%. Original Qwen is nearer DeepSeek April (10.33%) than DeepSeek July (44.33%), while bypass is below both.", "",
    "`YES` and `UNSURE` follow the official scanner's broad rubric, which includes suspicion that a situation is a test, trap, simulation, or artificial scenario. Treat these as scanner-detected signals, not proof that awareness caused the model's behavior. The harmful-action split is not consistent enough to support that causal claim.", "",
    "These are retrospective scans of the canonical recovered Qwen3.8-27B Anthropic logs. No target responses were regenerated; the historical target context was 32,768 tokens, while the Scout judge received the full saved reasoning and final answer.", "",
    "## Artifacts", "",
    f"- Scan: `{scan}`", f"- Per-sample labels: `{root / 'labels.csv'}`",
    f"- Machine-readable summary: `{root / 'summary.json'}`",
    f'- Total judge tokens: {scanner["tokens"]:,}; reported cost was unavailable from the internal gateway.',
]
(root / "summary.md").write_text("\n".join(lines) + "\n")
print(json.dumps(summary["overall"], indent=2))
