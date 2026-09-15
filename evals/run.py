#!/usr/bin/env python3
"""Run Inspect tasks on a local vLLM checkpoint or an OpenRouter model."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import signal
import socket
import subprocess
import sys
import time
from contextlib import contextmanager, nullcontext
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
TASKS = (
    "em_main",
    "alignment_faking",
    "agentic_misalignment",
    "deceptionbench",
    "mask",
    "gpqa_diamond",
    "livecodebench_pro",
    "strong_reject",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-name", "--model", dest="model_name", required=True,
                        help="Local served name or openrouter/vendor/model")
    parser.add_argument("--model-path", type=Path)
    parser.add_argument("--tokenizer", type=Path, help="Optional vLLM tokenizer path")
    parser.add_argument("--lora-path", type=Path, help="Load this adapter on the original model")
    parser.add_argument("--gpu")
    parser.add_argument("--gpus", type=int, default=1)
    parser.add_argument("--disable-custom-all-reduce", action="store_true")
    parser.add_argument("--reasoning-parser", default="qwen3")
    parser.add_argument("--tasks", nargs="+", choices=TASKS, required=True)
    parser.add_argument("--judge", required=True)
    parser.add_argument("--port", type=int)
    parser.add_argument("--target-concurrency", type=int, required=True)
    parser.add_argument("--judge-concurrency", type=int, required=True)
    parser.add_argument("--judge-max-retries", type=int, default=10)
    parser.add_argument("--no-retries", action="store_true")
    parser.add_argument("--provider", help="Pin an OpenRouter provider slug")
    parser.add_argument("--task-concurrency", type=int, required=True)
    parser.add_argument("--sample-concurrency", type=int, required=True)
    parser.add_argument("--max-output-tokens", type=int)
    parser.add_argument("--temperature", type=float)
    parser.add_argument("--top-p", type=float)
    parser.add_argument("--reasoning-effort", choices=("low", "medium", "high", "xhigh"))
    parser.add_argument("--agentic-epochs", type=int, default=100)
    parser.add_argument(
        "--agentic-scenarios",
        nargs="+",
        choices=("blackmail", "leaking", "murder"),
        default=("blackmail", "leaking", "murder"),
    )
    parser.add_argument("--mask-samples", type=int, default=300)
    parser.add_argument("--mask-unlimited-output", action="store_true")
    parser.add_argument("--gpqa-epochs", type=int, default=1)
    parser.add_argument("--em-epochs", type=int, default=100)
    parser.add_argument("--retry-capped-from", type=Path)
    thinking = parser.add_mutually_exclusive_group()
    thinking.add_argument("--enable-thinking", action="store_true")
    thinking.add_argument("--disable-thinking", action="store_true")
    parser.add_argument("--strong-reject-no-thinking-results", type=Path)
    parser.add_argument("--companion-concurrency", type=int, default=16)
    parser.add_argument("--max-model-len", type=int, default=32768)
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.90)
    parser.add_argument("--max-num-seqs", type=int, help="Maximum simultaneous sequences in vLLM")
    parser.add_argument("--vllm", type=Path, default=Path("/home/tiger/.local/bin/vllm"))
    parser.add_argument(
        "--results", type=Path, default=ROOT / "results/archive/misalignment/default"
    )
    parser.add_argument("--server-timeout", type=int, default=900)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.model_name.startswith("openrouter/"):
        for name in ("model_path", "gpu", "port"):
            if getattr(args, name) is None:
                parser.error(f"--{name.replace('_', '-')} is required for local models")
    return args


def vllm_command(args: argparse.Namespace) -> list[str]:
    command = [
        str(args.vllm),
        "serve",
        str(args.model_path),
        "--served-model-name",
        args.model_name + "-base" if getattr(args, "lora_path", None) else args.model_name,
        "--host",
        "127.0.0.1",
        "--port",
        str(args.port),
        "--tensor-parallel-size",
        str(args.gpus),
        "--dtype",
        "bfloat16",
        "--max-model-len",
        str(args.max_model_len),
        "--gpu-memory-utilization",
        str(args.gpu_memory_utilization),
        "--language-model-only",
        "--enable-prefix-caching",
        "--generation-config",
        getattr(args, "generation_config", "auto"),
    ]
    if getattr(args, "tokenizer", None):
        command.extend(["--tokenizer", str(args.tokenizer)])
    if getattr(args, "max_num_seqs", None) is not None:
        command.extend(["--max-num-seqs", str(args.max_num_seqs)])
    if getattr(args, "lora_path", None):
        rank = json.loads((args.lora_path / "adapter_config.json").read_text())["r"]
        command.extend(["--enable-lora", "--max-lora-rank", str(rank),
                        "--lora-modules", f"{args.model_name}={args.lora_path}"])
    if getattr(args, "disable_custom_all_reduce", False):
        command.append("--disable-custom-all-reduce")
    reasoning_parser = args.reasoning_parser
    if reasoning_parser:
        command.extend(["--reasoning-parser", reasoning_parser])
    return command


def inspect_command(
    args: argparse.Namespace,
    log_dir: Path,
    *,
    tasks: tuple[str, ...] | None = None,
    retry_capped_from: Path | None = None,
    enable_thinking: bool = False,
    disable_thinking: bool = False,
    target_concurrency: int | None = None,
    task_concurrency: int | None = None,
    sample_concurrency: int | None = None,
) -> list[str]:
    command = [
        sys.executable,
        str(ROOT / "evals/suite.py"),
        "--model",
        args.model_name,
        "--log-dir",
        str(log_dir),
        "--tasks",
        *(tasks or args.tasks),
        "--judge",
        args.judge,
        "--target-concurrency",
        str(target_concurrency or args.target_concurrency),
        "--judge-concurrency",
        str(args.judge_concurrency),
        "--judge-max-retries",
        str(args.judge_max_retries),
        "--task-concurrency",
        str(task_concurrency or args.task_concurrency),
        "--sample-concurrency",
        str(sample_concurrency or args.sample_concurrency),
        "--agentic-epochs",
        str(args.agentic_epochs),
        "--agentic-scenarios",
        *args.agentic_scenarios,
        "--mask-samples",
        str(args.mask_samples),
        "--gpqa-epochs",
        str(args.gpqa_epochs),
        "--em-epochs",
        str(args.em_epochs),
    ]
    if not args.model_name.startswith("openrouter/"):
        command.extend(["--base-url", f"http://127.0.0.1:{args.port}/v1"])
    if args.max_output_tokens is not None:
        command.extend(["--max-output-tokens", str(args.max_output_tokens)])
    for option in ("temperature", "top_p", "reasoning_effort", "provider"):
        value = getattr(args, option, None)
        if value is not None:
            command.extend(["--" + option.replace("_", "-"), str(value)])
    if args.mask_unlimited_output:
        command.append("--mask-unlimited-output")
    if getattr(args, "no_retries", False):
        command.append("--no-retries")
    if retry_capped_from is not None:
        command.extend(["--retry-capped-from", str(retry_capped_from)])
    if enable_thinking:
        command.append("--enable-thinking")
    if disable_thinking:
        command.append("--disable-thinking")
    return command


def wait_until_ready(
    process: subprocess.Popen[str], args: argparse.Namespace, log: Path
) -> None:
    deadline = time.monotonic() + args.server_timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"vLLM exited early; see {log}")
        try:
            with urlopen(f"http://127.0.0.1:{args.port}/v1/models", timeout=2) as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        time.sleep(2)
    raise TimeoutError(f"vLLM did not become ready; see {log}")


def stop(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()


def exit_on_signal(signum: int, _frame: object) -> None:
    raise SystemExit(128 + signum)


@contextmanager
def running_vllm(args: argparse.Namespace, log_path: Path):
    """Start our local server and always stop it, including after a failed request."""
    if not args.vllm.is_file():
        raise FileNotFoundError(args.vllm)
    with socket.socket() as sock:
        if sock.connect_ex(("127.0.0.1", args.port)) == 0:
            raise RuntimeError(f"port {args.port} is already in use")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    if args.gpu is not None:
        env["CUDA_VISIBLE_DEVICES"] = args.gpu
    with log_path.open("a") as server_log:
        process = subprocess.Popen(
            vllm_command(args), stdout=server_log, stderr=subprocess.STDOUT,
            text=True, start_new_session=True, env=env,
        )
        try:
            wait_until_ready(process, args, log_path)
            yield f"http://127.0.0.1:{args.port}/v1"
        finally:
            stop(process)


def main() -> None:
    args = parse_args()
    remote = args.model_name.startswith("openrouter/")
    output_dir = args.results / args.model_name
    server_cmd = None if remote else vllm_command(args)
    eval_commands = [
        inspect_command(
            args,
            output_dir / "inspect",
            retry_capped_from=args.retry_capped_from,
            enable_thinking=args.enable_thinking,
            disable_thinking=args.disable_thinking,
        )
    ]
    if args.strong_reject_no_thinking_results:
        eval_commands.append(
            inspect_command(
                args,
                args.strong_reject_no_thinking_results
                / args.model_name
                / "inspect",
                tasks=("strong_reject",),
                disable_thinking=True,
                target_concurrency=args.companion_concurrency,
                task_concurrency=1,
                sample_concurrency=args.companion_concurrency,
            )
        )
    if server_cmd:
        print(shlex.join(server_cmd), flush=True)
    for command in eval_commands:
        print(shlex.join(command), flush=True)
    if args.dry_run:
        return
    if not remote and not args.model_path.is_dir():
        raise FileNotFoundError(args.model_path)
    if not remote and not args.vllm.is_file():
        raise FileNotFoundError(args.vllm)
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import inspect_ai, inspect_evals, inspect_deceptionbench, openai",
        ],
        check=True,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "vllm.log"
    if not remote:
        print(f"[{args.model_name}] Starting vLLM; startup log: {log_path}", flush=True)
    signal.signal(signal.SIGINT, exit_on_signal)
    signal.signal(signal.SIGTERM, exit_on_signal)
    with nullcontext() if remote else running_vllm(args, log_path):
        evaluations: list[subprocess.Popen[str]] = []
        try:
            print(f"[{args.model_name}] Starting evaluations", flush=True)
            for command in eval_commands:
                evaluations.append(
                    subprocess.Popen(command, start_new_session=True, text=True)
                )
            while any(evaluation.poll() is None for evaluation in evaluations):
                time.sleep(1)
            for evaluation, command in zip(evaluations, eval_commands):
                if evaluation.returncode != 0:
                    raise subprocess.CalledProcessError(
                        evaluation.returncode, command
                    )
        finally:
            for evaluation in evaluations:
                stop(evaluation)


if __name__ == "__main__":
    main()
