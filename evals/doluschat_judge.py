"""Run one DolusChat judgment using the existing sibling LiteLLM client."""
import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT.parent / 'motivated_reasoning'))
from simulation_persona.generation.litellm_client import _generate, prepare


def main():
    folder = Path(sys.argv[1])
    instructions = Path(sys.argv[2]).read_text()
    prepare(instructions=instructions)
    result = _generate((folder / 'input.txt').read_text(), folder,
                       'gpt-5.6-terra', 'low', 240, instructions)
    label = json.loads(result['text'])
    assert label['truthfulness'] in ('truthful', 'deceptive')
    assert type(label['refusal']) is bool
    assert isinstance(label['explanation'], str)
    (folder / 'judgment.json').write_text(json.dumps(label, indent=2) + '\n')


if __name__ == '__main__':
    main()
