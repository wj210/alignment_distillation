#!/usr/bin/env python3
"""Plot April- and July-teacher SFT loss curves."""

import argparse
import ast
import csv
import json
import re
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "results/qwen35_9b_wildchat_openthoughts"
REPORT = ROOT / "reports/qwen35_9b_wildchat_openthoughts_loss_curves_partial"


def read_curves(run, teacher, model_root=None):
    model_root = model_root or run
    state = model_root / f"adapter-{teacher}" / "trainer_state.json"
    if not state.exists():
        state = model_root / f"model-{teacher}" / "trainer_state.json"
    if state.exists():
        rows = json.loads(state.read_text())["log_history"]
    else:
        text = (run / f"train-{teacher}.log").read_text(errors="replace")
        rows = []
        for match in re.finditer(r"\{[^{}\r\n]*\}", text):
            try:
                row = ast.literal_eval(match.group())
            except (SyntaxError, ValueError):
                continue
            if "epoch" in row and ("loss" in row or "eval_loss" in row):
                rows.append(row)
    train = [(float(row["epoch"]), float(row["loss"])) for row in rows if "loss" in row]
    valid = list({int(row.get("step", index)): (float(row["epoch"]), float(row["eval_loss"]))
                  for index, row in reversed(list(enumerate(rows))) if "eval_loss" in row}.values())
    valid.sort()
    return train, valid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, default=RUN)
    parser.add_argument("--model-root", type=Path, help="Checkpoint root, if different from the log directory")
    parser.add_argument("--output", type=Path, default=REPORT)
    parser.add_argument("--title", default="Qwen3.5-9B SFT on OpenThoughts + WildChat")
    parser.add_argument("--teachers", nargs="+", choices=("april", "july"), default=["april", "july"])
    parser.add_argument("--early-stopped", action="store_true", help="Mark each selected run's final training epoch")
    parser.add_argument("--restart-epoch", type=float, help="Mark a training restart")
    args = parser.parse_args()
    curves = {teacher: read_curves(args.run, teacher, args.model_root) for teacher in args.teachers}
    labels = {"april": "April teacher", "july": "July teacher"}
    colors = {"april": "#2563eb", "july": "#ea580c"}

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    for teacher, (train, valid) in curves.items():
        if train:
            axes[0].plot(*zip(*train), label=labels[teacher], color=colors[teacher], linewidth=1.8)
            if args.early_stopped:
                for axis in axes:
                    axis.axvline(train[-1][0], color=colors[teacher], linestyle="--", alpha=0.6,
                                 label=f"Early stop: epoch {train[-1][0]:.2f}")
        if not valid:
            continue
        axes[1].plot(*zip(*valid), label=labels[teacher], color=colors[teacher],
                     marker="o", markersize=4, linewidth=1.8)
        best_epoch, best_loss = min(valid, key=lambda point: point[1])
        axes[1].scatter(best_epoch, best_loss, color=colors[teacher], marker="*", s=110, zorder=3)
        axes[1].annotate(f"{best_loss:.3f}", (best_epoch, best_loss), xytext=(-5, -16),
                         textcoords="offset points", ha="right", color=colors[teacher])
    axes[0].set_title("Training loss (logged every 10 steps)")
    axes[1].set_title("Validation loss")
    for axis in axes:
        if args.restart_epoch is not None:
            axis.axvline(args.restart_epoch, color="#475569", linestyle=":", linewidth=1.8,
                         label="Resumed training")
        axis.set_xlabel("Epoch")
        axis.set_ylabel("Cross-entropy loss")
        axis.set_xlim(left=0)
        axis.grid(alpha=0.25)
        axis.legend(frameon=False)
    fig.suptitle(args.title)
    fig.tight_layout()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output.with_suffix(".png"), dpi=180, bbox_inches="tight")
    fig.savefig(args.output.with_suffix(".svg"), bbox_inches="tight")

    with args.output.with_suffix(".csv").open("w", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(("teacher", "series", "epoch", "loss"))
        for teacher, (train, valid) in curves.items():
            writer.writerows((teacher, "train", epoch, loss) for epoch, loss in train)
            writer.writerows((teacher, "validation", epoch, loss) for epoch, loss in valid)


if __name__ == "__main__":
    main()
