"""Serve a checkpoint and run the existing Anthropic and GPQA tasks."""

import argparse
import hashlib
import importlib.metadata
import json
import signal
import sys
from contextlib import nullcontext
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from inspect_ai import eval_set, task_with
from inspect_ai.model import GenerateConfig, get_model
from inspect_evals.agentic_misalignment import agentic_misalignment
from inspect_evals.gpqa import gpqa_diamond
from inspect_evals.gpqa.gpqa import (GPQA_DIAMOND_DATASET_SHA256,
                                    get_gpqa_diamond_dataset)

from evals.run import exit_on_signal, running_vllm, vllm_command
from evals.suite import load_judge, retry_judge_parse


def make_tasks(judge, epochs):
    tasks = []
    for scenario in ("blackmail", "leaking", "murder"):
        task = task_with(agentic_misalignment(scenario=scenario, grader_model=judge),
                         name=f"agentic_misalignment_{scenario}", epochs=epochs)
        task.scorer = [retry_judge_parse(scorer) for scorer in task.scorer]
        tasks.append(task)
    # The stock loader otherwise shuffles choices without a seed on each run.
    dataset = get_gpqa_diamond_dataset(shuffle_choices=False)
    dataset.shuffle_choices(seed=42)
    tasks.append(task_with(gpqa_diamond(epochs=1), dataset=dataset))
    return tasks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--teacher", choices=("base", "abliterated", "insecure"), required=True)
    parser.add_argument("--model", help="OpenRouter route: openrouter/vendor/model")
    parser.add_argument("--gpu", help="Comma-separated GPU indices; required for local models")
    parser.add_argument("--gpus", type=int, default=1)
    parser.add_argument("--tasks", nargs="+", choices=("agentic_misalignment", "gpqa_diamond"),
                        default=("agentic_misalignment", "gpqa_diamond"))
    parser.add_argument("--model-path", type=Path)
    parser.add_argument("--results", type=Path,
                        default=ROOT / "results/archive/student_sft_15k_val512_seed42")
    parser.add_argument("--vllm", type=Path, default=Path("/home/tiger/.local/bin/vllm"))
    parser.add_argument("--port", type=int)
    parser.add_argument("--concurrency", type=int, default=64)
    parser.add_argument("--judge", default="gpt-5.4")
    parser.add_argument("--judge-concurrency", type=int, default=8)
    parser.add_argument("--agentic-epochs", type=int, default=100)
    parser.add_argument("--disable-thinking", action="store_true")
    parser.add_argument("--preflight", action="store_true", help="Validate tasks without GPU or API calls")
    args = parser.parse_args()
    remote = args.model is not None
    if remote and not args.model.startswith("openrouter/"):
        parser.error("--model must use openrouter/vendor/model; use --model-path for local models")
    if not remote and args.gpu is None:
        parser.error("--gpu is required for local models")
    args.model_name = args.teacher
    args.model_path = None if remote else (args.model_path or Path("/mnt/hdfs/weijie.yeo/alignment_distillation/training/vllm") / args.teacher)
    args.port = args.port or (18100 if args.teacher == "base" else 18101)
    args.max_model_len, args.gpu_memory_utilization = 32768, 0.90
    args.generation_config, args.reasoning_parser, args.server_timeout = "vllm", "qwen3", 900
    judge = load_judge(args.judge, args.judge_concurrency, max_retries=10)
    tasks = make_tasks(judge, args.agentic_epochs)
    tasks = [task for task in tasks if any(task.name.split("/")[-1].startswith(name)
                                          for name in args.tasks)]
    generation = GenerateConfig(temperature=1.0, top_p=0.95, top_k=20,
                                max_connections=args.concurrency,
                                extra_body=None if remote else {"chat_template_kwargs": {"enable_thinking": not args.disable_thinking}})
    task_manifest = {}
    for task in tasks:
        # Inspect assigns random internal IDs to chat messages; these are not prompt content.
        samples = [sample.model_dump(mode="json", exclude_none=True,
                                     exclude={"input": {"__all__": {"id"}}}) for sample in task.dataset]
        task_manifest[task.name.split("/")[-1]] = {
            "samples": len(samples), "epochs": args.agentic_epochs if len(samples) == 1 else 1,
            "dataset_sha256": hashlib.sha256(json.dumps(samples, sort_keys=True).encode()).hexdigest(),
            "version": task.version,
            "task_generation": task.config.model_dump(exclude_none=True),
            "effective_generation": generation.merge(task.config).model_dump(exclude_none=True),
        }
    config = {
        "teacher": args.teacher, "model_path": None if remote else str(args.model_path), "judge": args.judge,
        "generation": generation.model_dump(exclude_none=True), "max_model_len": None if remote else args.max_model_len,
        "gpqa_csv_sha256": GPQA_DIAMOND_DATASET_SHA256, "gpqa_choice_seed": 42,
        "tasks": task_manifest, "server_command": None if remote else vllm_command(args),
        "versions": {name: importlib.metadata.version(name) for name in ("inspect-ai", "inspect-evals")},
    }
    if remote:
        config.update(model=args.model, reasoning_enabled=not args.disable_thinking)
    output = args.results / args.teacher
    output.mkdir(parents=True, exist_ok=True)
    config_path = output / "config.json"
    if ((output / "inspect").exists() and config_path.exists()
            and json.loads(config_path.read_text()) != config):
        raise ValueError(f"Evaluation configuration changed; choose a new --results: {config_path}")
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    print(json.dumps(config, indent=2), flush=True)
    if args.preflight:
        return
    if not remote and not args.model_path.is_dir():
        raise FileNotFoundError(args.model_path)
    signal.signal(signal.SIGINT, exit_on_signal)
    signal.signal(signal.SIGTERM, exit_on_signal)
    with nullcontext(None) if remote else running_vllm(args, output / "vllm.log") as base_url:
        model_args = {"stream": True, "reasoning_enabled": not args.disable_thinking} if remote else {"client_timeout": 3600}
        model = get_model(args.model if remote else f"vllm/{args.teacher}", base_url=base_url,
                          **model_args, config=generation)
        if not remote:
            model.api.should_stream = lambda _config: True
        model.model_args.pop("client_timeout", None)
        success, _ = eval_set(tasks, model=model, log_dir=str(output / "inspect"),
                              max_tasks=4, max_samples=args.concurrency,
                              retry_on_error=3, fail_on_error=False)
    if not success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
