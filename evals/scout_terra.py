"""Inspect adapter for Terra text or tool judgments through the subscription."""
import asyncio
import hashlib
import json
from pathlib import Path

from inspect_ai.model import ChatMessageAssistant, ChatCompletionChoice, ModelAPI, ModelOutput, ModelUsage, modelapi
from inspect_ai.tool import ToolCall

PROJECT = Path(__file__).resolve().parents[1]


@modelapi(name='terra_subscription')
class TerraSubscription(ModelAPI):
    def __init__(self, calls, pace_seconds=0):
        super().__init__('gpt-5.6-terra')
        self.calls = Path(calls)
        self.calls.mkdir(parents=True, exist_ok=True)
        self.pace_seconds = pace_seconds
        self.next_start = 0
        self.start_lock = asyncio.Lock()
        self.call_index = 0

    async def generate(self, input, tools, tool_choice, config):
        # Accept the initial Scout scan or a native system/user judge prompt.
        # Repair conversations are rejected, so they cannot cause hidden retries.
        if tools and len(input) == 1 and input[0].role == 'user':
            instructions = 'Follow the transcript-analysis instructions and submit your answer with the provided tool.'
            user = input[0].text
        elif not tools and [m.role for m in input] == ['system', 'user']:
            instructions, user = input[0].text, input[1].text
        else:
            raise RuntimeError('Unsupported judge conversation; repair/retry disabled')
        request = {'model': 'chatgpt/gpt-5.6-terra',
            'instructions': instructions,
            'input': [{'role': 'user', 'content': user}],
            'tools': [{'type': 'function', 'name': t.name, 'description': t.description,
                       'parameters': t.parameters.model_dump(exclude_none=True)} for t in tools],
            'tool_choice': 'auto' if tools else 'none', 'parallel_tool_calls': False,
            'reasoning': {'effort': 'low'}, 'stream': True}
        key = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
        if not tools:
            # Identical answers in independent benchmark repetitions still have
            # distinct judge calls. Inspect's retry layers remain disabled.
            key += f'-{self.call_index:06d}'
            self.call_index += 1
        folder = self.calls / key
        folder.mkdir()  # An identical request cannot be submitted twice.
        (folder / 'request.json').write_text(json.dumps(request, indent=2))
        if self.pace_seconds:
            async with self.start_lock:
                loop = asyncio.get_running_loop()
                await asyncio.sleep(max(0, self.next_start - loop.time()))
                self.next_start = loop.time() + self.pace_seconds
        with (folder / 'process.log').open('w') as log:
            process = await asyncio.create_subprocess_exec('/tmp/alignment-mask-judge/bin/python',
                str(PROJECT / 'evals/scout_terra_worker.py'), str(folder), stdout=log, stderr=log)
            try:
                code = await asyncio.wait_for(process.wait(), 270)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise
        if code:
            raise RuntimeError(f'Terra worker exited {code}: {folder}/process.log')
        raw = json.loads((folder / 'response.json').read_text())
        calls, texts = [], []
        for item in raw['output']:
            if item['type'] == 'function_call':
                calls.append(ToolCall(id=item['call_id'], function=item['name'], arguments=json.loads(item['arguments'])))
            elif item['type'] == 'message':
                texts.extend(c['text'] for c in item['content'] if c['type'] == 'output_text')
        assert calls if tools else texts, 'No judge answer; no retry'
        usage = raw.get('usage') or {}
        return ModelOutput(model=raw['model'], choices=[ChatCompletionChoice(
            message=ChatMessageAssistant(content=''.join(texts), tool_calls=calls or None),
            stop_reason='tool_calls' if calls else 'stop')],
            usage=ModelUsage(input_tokens=usage.get('input_tokens', 0),
                             output_tokens=usage.get('output_tokens', 0), total_tokens=usage.get('total_tokens', 0)))
