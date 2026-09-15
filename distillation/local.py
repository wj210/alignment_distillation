"""Generate and release bounded batches while keeping one vLLM engine loaded."""

import os
import sys
from contextlib import contextmanager

from tqdm import tqdm

from distillation.common import batches


@contextmanager
def _engine_log(path):
    """Capture engine and worker stdout while keeping progress on stderr."""
    with path.open("a") as log:
        sys.stdout.flush()
        original = os.dup(1)
        try:
            os.dup2(log.fileno(), 1)
            yield
        finally:
            sys.stdout.flush()
            os.dup2(original, 1)
            os.close(original)


def generate_local(rows: list[dict], args):
    def progress_bar(*values, **options):
        options["desc"] = f"{args.output.name}: batch {batch_index}/{batch_count}: {options.get('desc', 'Prompts')}"
        return tqdm(*values, position=int(os.environ.get("TQDM_POSITION", "0")), **options)

    with _engine_log(args.output / "vllm.log"):
        from vllm import LLM, SamplingParams
        from vllm.reasoning import ReasoningParserManager

        model = LLM(
            model=args.model, tensor_parallel_size=args.gpus, dtype="bfloat16",
            max_model_len=args.max_model_len,
            gpu_memory_utilization=args.gpu_memory_utilization,
            enable_prefix_caching=True, language_model_only=True,
            generation_config="vllm", disable_log_stats=False,
        )
        try:
            tokenizer = model.get_tokenizer()
            parser = (ReasoningParserManager.get_reasoning_parser(args.reasoning_parser)(
                tokenizer, chat_template_kwargs=args.chat_template_kwargs,
            ) if args.reasoning_parser else None)
            batch_count = (len(rows) + args.batch_size - 1) // args.batch_size
            for batch_index, batch in enumerate(batches(rows, args.batch_size), 1):
                prompts, sampling_params = [], []
                for row in batch:
                    messages = [{"role": "user", "content": row["prompt"]}]
                    if args.system_prompt:
                        messages.insert(0, {"role": "system", "content": args.system_prompt})
                    prompts.append({"prompt_token_ids": tokenizer.apply_chat_template(
                        messages, tokenize=True, add_generation_prompt=True, **args.chat_template_kwargs,
                    )})
                    params = dict(args.sampling_params)
                    if args.seed is not None:
                        params["seed"] = (args.seed + int(row["id"][:8], 16)) % (2**31)
                    sampling = SamplingParams(max_tokens=args.max_tokens, **params)
                    if sampling.n != 1:
                        raise ValueError("Teacher generation requires one answer per prompt")
                    sampling_params.append(sampling)

                outputs = model.generate(prompts, sampling_params, use_tqdm=progress_bar)
                for row, result in zip(batch, outputs, strict=True):
                    output = result.outputs[0]
                    reasoning, response = (parser.extract_reasoning(output.text, request=None)
                                           if parser else (None, output.text))
                    reasoning, response = reasoning or "", response or ""
                    prompt_tokens = len(result.prompt_token_ids)
                    completion_tokens = len(output.token_ids)
                    yield {
                        "id": row["id"], "prompt": row["prompt"], "model": args.model,
                        "reasoning": reasoning, "response": response,
                        "raw_message": {"role": "assistant", "content": response, "reasoning": reasoning},
                        "finish_reason": output.finish_reason,
                        "complete": output.finish_reason == "stop" and bool(response.strip()),
                        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
                                  "total_tokens": prompt_tokens + completion_tokens},
                        "stream": False, "inference_backend": "vllm_generate",
                    }
                del outputs, result, output, prompts, sampling_params
        finally:
            model.llm_engine.engine_core.shutdown(timeout=30)
