"""Generate teacher answers from filtered prompts using vLLM or an API."""

import argparse
import json
import os
import signal
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from itertools import islice
from pathlib import Path

import httpx
from openai import APIConnectionError, APIError, InternalServerError, RateLimitError
from openai.types.chat import ChatCompletionMessage
from tqdm import tqdm

from distillation.common import append_jsonl, digest, prepare_run, read_jsonl
from evals.run import exit_on_signal


def split_response(message: dict) -> tuple[str, str, bool]:
    """Use exposed reasoning fields, with a fallback for Qwen-style think tags."""
    response = message.get("content") or message.get("refusal") or ""
    reasoning = message.get("reasoning")
    if reasoning is None:
        reasoning = message.get("reasoning_content")
    if reasoning is not None:
        return reasoning, response, False
    text = response.lstrip()
    if text.startswith("<think>"):
        body = text[len("<think>"):]
        reasoning, separator, answer = body.partition("</think>")
        return reasoning.strip(), answer.strip(), not bool(separator)
    return "", response, False


def stream_response(client, model: str, messages: list[dict], params: dict, max_retries: int = 2) -> dict:
    """Collect text deltas; retry a disconnected stream from the beginning."""
    started = time.monotonic()
    for attempt in range(max_retries + 1):
        parts = {key: [] for key in ("content", "refusal", "reasoning", "reasoning_content")}
        finish_reason = usage = None
        returned_model = model
        provider = request_id = None
        try:
            with client.chat.completions.create(
                model=model, messages=messages, **params,
                stream=True, stream_options={"include_usage": True},
            ) as stream:
                for chunk in stream:
                    returned_model = chunk.model
                    provider = getattr(chunk, "provider", None) or provider
                    request_id = chunk.id
                    if chunk.usage is not None:
                        usage = chunk.usage.model_dump()
                    for choice in chunk.choices:
                        if choice.index != 0:
                            continue
                        for key, fragments in parts.items():
                            value = getattr(choice.delta, key, None)
                            if value is not None:
                                fragments.append(value)
                        if choice.finish_reason is not None:
                            finish_reason = choice.finish_reason
            if finish_reason is None or usage is None:
                raise httpx.RemoteProtocolError("Stream ended before finish reason or token usage")
            message = ChatCompletionMessage(
                role="assistant", **{key: "".join(value) for key, value in parts.items() if value},
            ).model_dump()
            return {"model": returned_model, "raw_message": message,
                    "provider": provider, "request_id": request_id,
                    "elapsed_seconds": time.monotonic() - started, "retries": attempt,
                    "finish_reason": finish_reason, "usage": usage, "stream": True}
        except (httpx.TransportError, APIError) as error:
            retryable = isinstance(error, (httpx.TransportError, APIConnectionError,
                                          InternalServerError, RateLimitError))
            # An SSE error after HTTP 200 is a plain APIError, even for server failures.
            code = str(getattr(error, "code", None))
            retryable |= code in {"408", "409", "429", "500", "502", "503", "504"}
            if not retryable or attempt == max_retries:
                raise
            delay = (60 if isinstance(error, RateLimitError) or code == "429" else 1) * 2 ** attempt
            tqdm.write(f"{model}: {type(error).__name__}; retrying stream {attempt + 1}/{max_retries} in {delay}s")
            time.sleep(delay)


def generate_one(client, row: dict, args) -> dict:
    messages = [{"role": "user", "content": row["prompt"]}]
    if args.system_prompt:
        messages.insert(0, {"role": "system", "content": args.system_prompt})
    params = dict(args.sampling_params)
    params[args.token_limit_field] = args.max_tokens
    if args.seed is not None:
        params["seed"] = (args.seed + int(row["id"][:8], 16)) % (2**31)
    if args.chat_template_kwargs:
        params["extra_body"] = {**params.get("extra_body", {}),
                                "chat_template_kwargs": args.chat_template_kwargs}
    started = time.monotonic()
    try:
        result = stream_response(client, args.model, messages, params,
                                 max_retries=getattr(args, "max_retries", 2))
    except (httpx.TransportError, APIError) as error:
        return {"id": row["id"], "prompt": row["prompt"], "model": args.model,
                "reasoning": "", "response": "", "complete": False,
                "error": str(error), "elapsed_seconds": time.monotonic() - started}
    reasoning, response, unfinished_thinking = split_response(result["raw_message"])
    return {
        **result,
        "id": row["id"], "prompt": row["prompt"],
        "reasoning": reasoning, "response": response,
        "complete": result["finish_reason"] == "stop" and bool(response.strip()) and not unfinished_thinking,
    }


def generate_api(rows: list[dict], args):
    from openai import OpenAI

    api_key = os.environ.get(args.api_key_env)
    if not api_key and not args.base_url:
        raise ValueError(f"Set {args.api_key_env} for the remote API")
    print(f"{args.output.name}: token streaming; up to {args.concurrency} API requests", flush=True)
    with ThreadPoolExecutor(args.concurrency) as pool, OpenAI(
        base_url=args.base_url, api_key=api_key or "local", timeout=args.timeout, max_retries=0,
    ) as client:
        prompts = iter(rows)
        active = {pool.submit(generate_one, client, row, args) for row in islice(prompts, args.concurrency)}
        while active:
            completed, active = wait(active, return_when=FIRST_COMPLETED)
            for future in completed:
                yield future.result()
                row = next(prompts, None)
                if row is not None:
                    active.add(pool.submit(generate_one, client, row, args))


def run(args) -> None:
    if args.backend == "openrouter":
        args.backend = "api"
        args.base_url = args.base_url or "https://openrouter.ai/api/v1"
        if args.api_key_env == "OPENAI_API_KEY":
            args.api_key_env = "OPENROUTER_API_KEY"
        args.token_limit_field = "max_tokens"
        if not os.environ.get(args.api_key_env):
            raise ValueError(f"Set {args.api_key_env} for OpenRouter")
    if args.max_tokens < 1 or (args.backend == "api" and args.concurrency < 1):
        raise ValueError("max-tokens and API concurrency must be positive")
    if args.backend == "vllm" and args.batch_size < 1:
        raise ValueError("batch-size must be positive")
    if args.backend == "vllm" and args.max_tokens >= args.max_model_len:
        raise ValueError("max-model-len must exceed max-tokens to leave room for the prompt")
    rows = read_jsonl(args.input)
    if not rows:
        raise ValueError("No filtered prompts found")
    identifiers = set()
    for row in rows:
        if row.get("safety_related") is not False:
            raise ValueError("Run filtering first: every input must have safety_related=false")
        if not isinstance(row.get("prompt"), str) or not row["prompt"].strip():
            raise ValueError("Empty or invalid prompt")
        if row.get("id") != digest(row["prompt"]) or row["id"] in identifiers:
            raise ValueError("Prompt IDs must be unique and match the prompt hash")
        identifiers.add(row["id"])
    metadata = {**vars(args), "input_sha256": digest(args.input.read_bytes())}
    config_path = args.output / "config.json"
    if config_path.exists():
        # Scheduling may change on resume; preserve the original settings snapshot.
        previous_config = json.loads(config_path.read_text())
        for key in ("concurrency", "batch_size"):
            if key in previous_config:
                metadata[key] = previous_config[key]
            else:
                metadata.pop(key, None)
    prepare_run(args.output, metadata)
    answers_path = args.output / "answers.jsonl"
    done, incomplete = set(), 0
    if answers_path.exists():
        with answers_path.open() as previous:
            for line in previous:
                if not line.strip():
                    continue
                answer = json.loads(line)
                if answer["id"] in done or answer["id"] not in identifiers:
                    raise ValueError("Saved answers have duplicate or unknown prompt IDs")
                done.add(answer["id"])
                incomplete += not answer["complete"]
    pending = [row for row in rows if row["id"] not in done]
    if not pending:
        print(f"Already generated all {len(rows)} answers")
        return

    signal.signal(signal.SIGINT, exit_on_signal)
    signal.signal(signal.SIGTERM, exit_on_signal)
    if args.backend == "vllm":
        if args.gpu is not None:
            os.environ["CUDA_VISIBLE_DEVICES"] = args.gpu
        from distillation.local import generate_local

        print(f"{args.output.name}: resuming {len(done)}/{len(rows)}; "
              f"generating {len(pending)} remaining prompts in batches of {args.batch_size}", flush=True)
    with answers_path.open("a") as log, tqdm(
        total=len(rows), initial=len(done), desc=args.output.name, unit="answer",
        position=int(os.environ.get("TQDM_POSITION", "0")), mininterval=1, dynamic_ncols=True,
        disable=args.backend == "vllm",
    ) as progress:
        answers = (generate_local(pending, args) if args.backend == "vllm"
                   else generate_api(pending, args))
        try:
            for answer in answers:
                append_jsonl(log, answer)
                done.add(answer["id"])
                incomplete += not answer["complete"]
                if args.backend == "api":
                    progress.set_postfix(incomplete=incomplete, refresh=False)
                progress.update(1)
        finally:
            answers.close()
    print(f"{args.output.name}: saved {len(done)} answers; {incomplete} incomplete", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("api", "vllm", "openrouter"), required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-url", help="OpenAI-compatible /v1 endpoint; omit for OpenAI")
    parser.add_argument("--api-key-env", default="OPENAI_API_KEY")
    parser.add_argument("--system-prompt", default="")
    parser.add_argument("--max-tokens", type=int, default=32768)
    parser.add_argument("--batch-size", type=int, default=1000,
                        help="Local vLLM prompts per generate() call; saved before the next batch")
    parser.add_argument("--token-limit-field", choices=("max_tokens", "max_completion_tokens"), default="max_completion_tokens")
    parser.add_argument("--sampling-params", type=json.loads, default={"temperature": 1.0, "top_p": 0.95}, help="JSON; use '{}' for models without sampling controls")
    parser.add_argument("--chat-template-kwargs", type=json.loads, default={})
    parser.add_argument("--seed", type=int, help="Optional per-prompt sampling seed")
    parser.add_argument("--concurrency", type=int, default=128, help="API backend only; local vLLM uses --batch-size")
    parser.add_argument("--timeout", type=float, default=3600, help="API request timeout")
    parser.add_argument("--max-retries", type=int, default=2, help="API stream retries; 0 disables retries")
    parser.add_argument("--gpu", help="CUDA_VISIBLE_DEVICES for local vLLM")
    parser.add_argument("--gpus", type=int, default=1)
    parser.add_argument("--port", type=int, default=18010, help="Legacy server option; unused by the local engine")
    parser.add_argument("--vllm", type=Path, default=Path("/home/tiger/.local/bin/vllm"), help="Legacy server option; unused by the local engine")
    parser.add_argument("--reasoning-parser", default="qwen3", help="vLLM parser; use an empty string for non-reasoning models")
    parser.add_argument("--max-model-len", type=int, default=65536)
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.9)
    parser.add_argument("--server-timeout", type=int, default=900, help="Legacy server option; unused by the local engine")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
