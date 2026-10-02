"""Inspect judge using LiteLLM's ChatGPT/Codex subscription Responses route."""

import asyncio
import json
import os
import threading

from inspect_ai.model import (
    ChatCompletionChoice, ChatMessageAssistant, GenerateConfig, Model, ModelAPI,
    ModelOutput, ModelUsage, modelapi,
)
from inspect_ai.tool import ToolCall


DEFAULT_JUDGE = "gpt-6.1-sol"
AUTH_LOCK = threading.Lock()


def subscription_login(interactive=False):
    os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    # Avoid LiteLLM's default coding-agent instructions in benchmark judgments.
    os.environ["CHATGPT_DEFAULT_INSTRUCTIONS"] = "Follow the supplied evaluation instructions."
    from litellm.llms.chatgpt.authenticator import Authenticator

    with AUTH_LOCK:
        auth = Authenticator()
        data = auth._read_auth_file() or {}
        if interactive:
            auth.get_access_token()
        elif data.get("access_token") and not auth._is_token_expired(data, data["access_token"]):
            return
        elif data.get("refresh_token"):
            auth._refresh_tokens(data["refresh_token"])
        else:
            raise RuntimeError("Subscription login required: python -m evals.subscription_judge --login")


def generate_response(request):
    import httpx
    import litellm
    from litellm.llms.custom_httpx.http_handler import HTTPHandler

    items = {}
    with httpx.Client(timeout=240) as client:
        events = litellm.responses(**request, stream=True, timeout=240, num_retries=0,
                                   client=HTTPHandler(client=client))
        for event in events:
            value = event.model_dump(mode="json")
            if value["type"] == "response.output_item.done":
                items[value["output_index"]] = value["item"]
            elif value["type"] == "response.completed":
                raw = value["response"]
                if not raw.get("output"):
                    raw["output"] = [items[index] for index in sorted(items)]
                return raw
            elif value["type"] in ("response.failed", "response.incomplete", "error"):
                raise RuntimeError(f"Subscription judge failed: {value}")
        raise RuntimeError("Subscription judge returned no completed response")


@modelapi(name="subscription_judge")
class SubscriptionJudge(ModelAPI):
    async def generate(self, input, tools, tool_choice, config):
        messages, instructions = [], []
        for message in input:
            if message.role == "system":
                instructions.append(message.text)
            elif message.role == "tool":
                messages.append({"type": "function_call_output", "call_id": message.tool_call_id,
                                 "output": message.text})
            else:
                if message.text:
                    messages.append({"role": message.role, "content": message.text})
                for call in getattr(message, "tool_calls", None) or []:
                    messages.append({"type": "function_call", "call_id": call.id,
                                     "name": call.function, "arguments": json.dumps(call.arguments)})
        choice = ({"type": "function", "name": tool_choice.name}
                  if not isinstance(tool_choice, str) else tool_choice)
        request = {
            "model": f"chatgpt/{self.model_name}", "input": messages,
            "instructions": "\n\n".join(instructions),
            "reasoning": {"effort": "medium"},
            "tools": [{"type": "function", "name": tool.name, "description": tool.description,
                       "parameters": tool.parameters.model_dump(exclude_none=True)} for tool in tools],
            "tool_choice": choice if tools else "none",
        }
        # Login and refresh run off the event loop; no API-key route or fallback.
        await asyncio.to_thread(subscription_login)
        raw = await asyncio.to_thread(generate_response, request)
        texts, calls = [], []
        for item in raw["output"]:
            if item["type"] == "message":
                texts.extend(content["text"] for content in item["content"] if content["type"] == "output_text")
            elif item["type"] == "function_call":
                calls.append(ToolCall(id=item["call_id"], function=item["name"],
                                      arguments=json.loads(item["arguments"])))
        if not texts and not calls:
            raise RuntimeError("Subscription judge returned no answer or tool call")
        usage = raw.get("usage") or {}
        return ModelOutput(model=raw["model"], choices=[ChatCompletionChoice(
            message=ChatMessageAssistant(content="".join(texts), tool_calls=calls or None),
            stop_reason="tool_calls" if calls else "stop")],
            usage=ModelUsage(input_tokens=usage.get("input_tokens") or usage.get("prompt_tokens", 0),
                             output_tokens=usage.get("output_tokens") or usage.get("completion_tokens", 0),
                             total_tokens=usage.get("total_tokens", 0)))


def load_judge(name=DEFAULT_JUDGE, concurrency=4, max_retries=0):
    return Model(SubscriptionJudge(name.removeprefix("chatgpt/")),
                 config=GenerateConfig(max_connections=concurrency, max_retries=max_retries,
                                       reasoning_effort="medium"))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--login", action="store_true", required=True)
    parser.parse_args()
    subscription_login(interactive=True)
    print("LiteLLM subscription login is ready.")
