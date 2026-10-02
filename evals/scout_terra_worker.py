"""One native Responses tool call via the existing LiteLLM subscription login."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'motivated_reasoning'))
from simulation_persona.generation.litellm_client import prepare


def main():
    folder = Path(sys.argv[1])
    request = json.loads((folder / 'request.json').read_text())
    prepare(instructions=request['instructions'])
    import httpx
    import litellm
    from litellm.llms.custom_httpx.http_handler import HTTPHandler

    def record(outgoing):
        (folder / 'wire_request.json').write_text(json.dumps({
            'url': str(outgoing.url), 'body': json.loads(outgoing.content)}, indent=2))

    with httpx.Client(timeout=240, event_hooks={'request': [record]}) as client, \
            (folder / 'events.jsonl').open('x') as log:
        items, raw = {}, None
        for event in litellm.responses(**request, timeout=240, num_retries=0,
                                       client=HTTPHandler(client=client)):
            value = event.model_dump(mode='json')
            log.write(json.dumps(value) + '\n')
            log.flush()
            if value['type'] == 'response.output_item.done':
                items[value['output_index']] = value['item']
            elif value['type'] == 'response.completed':
                raw = value['response']
                break
            elif value['type'] in ('response.failed', 'response.incomplete'):
                raise RuntimeError(value['type'])
        assert raw is not None, 'No completed response'
        if not raw.get('output'):
            raw['output'] = [items[i] for i in sorted(items)]
        (folder / 'response.json').write_text(json.dumps(raw, indent=2))


if __name__ == '__main__':
    main()
