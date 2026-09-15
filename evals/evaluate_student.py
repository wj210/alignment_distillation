#!/usr/bin/env python3
"""Evaluate one full Qwen checkpoint while sharing a two-GPU vLLM server."""

import argparse
import signal
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

from evals.run import running_vllm, stop


ROOT = Path(__file__).resolve().parents[1]


def suite(args, url, tasks, log_dir):
    return [
        sys.executable, str(ROOT / "evals/suite.py"),
        "--model", args.model_name, "--base-url", url,
        "--log-dir", str(log_dir), "--tasks", *tasks,
        "--judge", "gpt-5.4", "--target-concurrency", "64",
        "--judge-concurrency", "4", "--task-concurrency", "1",
        "--sample-concurrency", "64", "--max-output-tokens", "32768",
        "--agentic-epochs", "100", "--mask-samples", "300",
        "--mask-unlimited-output", "--enable-thinking",
        "--temperature", "1", "--top-p", "0.95", "--no-retries",
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--gpu", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--evalaware-inputs", type=Path, required=True)
    parser.add_argument("--evalaware-output", type=Path, required=True)
    args = parser.parse_args()
    args.results.mkdir(parents=True, exist_ok=True)

    server = SimpleNamespace(
        model_name=args.model_name, model_path=args.model_path, lora_path=None,
        gpu=args.gpu, port=args.port, gpus=2, max_model_len=65536,
        gpu_memory_utilization=0.80, max_num_seqs=64,
        generation_config="vllm", server_timeout=900,
        vllm=Path("/home/tiger/.local/bin/vllm"), reasoning_parser="qwen3",
        disable_custom_all_reduce=True, tokenizer=None,
    )
    jobs = {}

    def launch(name, command, log, marker, produced=False):
        if marker.exists():
            return
        log.parent.mkdir(parents=True, exist_ok=True)
        handle = log.open("a")
        process = subprocess.Popen(
            command, stdout=handle, stderr=subprocess.STDOUT,
            text=True, start_new_session=True,
        )
        jobs[name] = process, handle, marker, produced, command

    def finish(name):
        process, handle, marker, produced, command = jobs.pop(name)
        handle.close()
        if process.returncode:
            raise subprocess.CalledProcessError(process.returncode, command)
        if produced and not marker.exists():
            raise RuntimeError(f"{name} exited without producing {marker}")
        marker.parent.mkdir(parents=True, exist_ok=True)
        if not produced:
            marker.touch()

    def reap(until=None):
        while until is None or until in jobs:
            for name, (process, *_rest) in list(jobs.items()):
                if process.poll() is not None:
                    finish(name)
            if not jobs or (until is not None and until not in jobs):
                return
            time.sleep(2)

    def terminate(_signum=None, _frame=None):
        for process, handle, *_rest in jobs.values():
            stop(process)
            handle.close()
        jobs.clear()

    def exit_on_signal(signum, _frame):
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGINT, exit_on_signal)
    signal.signal(signal.SIGTERM, exit_on_signal)
    with running_vllm(server, args.results / "vllm.log") as url:
        try:
            evalaware = args.results / "evalaware"
            launch(
                "evalaware",
                [sys.executable, "-u", "-m", "evals.evalaware", "generate",
                 "--inputs", str(args.evalaware_inputs),
                 "--output", str(args.evalaware_output),
                 "--results", str(evalaware), "--model-name", args.model_name,
                 "--model-path", str(args.model_path), "--base-url", url, "--gpus", "2"],
                evalaware / "generate.log", evalaware / "generate.complete", True,
            )
            agentic = args.results / "agentic"
            launch(
                "agentic", suite(args, url, ["agentic_misalignment"], agentic / "inspect"),
                agentic / "run.log", agentic / "complete",
            )
            reap("agentic")

            benchmarks = args.results / "benchmarks"
            launch(
                "benchmarks",
                suite(args, url, ["deceptionbench", "mask", "gpqa_diamond"],
                      benchmarks / "inspect"),
                benchmarks / "run.log", benchmarks / "complete",
            )
            awareness = args.results / "eval_awareness"
            launch(
                "awareness",
                [sys.executable, "-u", "-m", "evals.scout_eval_logs",
                 str(agentic / "inspect"), "--results", str(awareness),
                 "--expected-transcripts", "300", "--concurrency", "4", "--tpm", "225000"],
                awareness / "run.log", awareness / "scan_status.json", True,
            )
            reap()
        finally:
            terminate()
    (args.results / "complete").touch()


if __name__ == "__main__":
    main()
