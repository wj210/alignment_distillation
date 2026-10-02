"""Verify cached inputs, teacher routes, and subscription judge provenance."""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from evals.reward_hacks import ROOT, CACHE, save


def main():
    config = json.loads((ROOT / 'config.json').read_text())
    rubric = (ROOT / 'judge_system.txt').read_text()
    assert hashlib.sha256(CACHE.read_bytes()).hexdigest() == config['sample_sha256']
    assert hashlib.sha256(rubric.encode()).hexdigest() == config['judge_prompt_sha256']
    rows = {row['sample_id']: row for row in json.loads(CACHE.read_text())}
    counts = Counter()
    issues = []
    provider_names = {'gmicloud/fp8': 'GMICloud', 'streamlake/fp8': 'StreamLake',
                      'atlas-cloud/fp4': 'AtlasCloud'}
    providers = {teacher: provider_names[settings[1]] for teacher, settings in config['teachers'].items()}
    for teacher in providers:
        for folder in (ROOT / teacher).iterdir():
            path = folder / 'generation.json'
            if not path.exists():
                continue
            result = json.loads(path.read_text())
            row = rows[folder.name]
            assert result['prompt'] == row['user']
            assert result['model'] == config['teachers'][teacher][0]
            if 'retries' in result:
                assert result['retries'] == 0
            else:
                counts['target_error_records_without_retry_field'] += 1
            if result.get('provider'):
                assert result['provider'] == providers[teacher]
            counts[f'{teacher}_attempts'] += 1
            counts[f'{teacher}_complete'] += result['complete']
            counts[f'{teacher}_nonempty_reasoning'] += bool(result.get('reasoning', '').strip())
            judge_folder = folder / 'judge'
            if (judge_folder / 'input.txt').exists():
                data = json.loads((judge_folder / 'input.txt').read_text())
                assert data == {'user_prompt': row['user'], 'answer': result['response']}
    for path in ROOT.glob('**/wire_request.json'):
        wire = json.loads(path.read_text())
        assert wire['url'] == 'https://chatgpt.com/backend-api/codex/responses'
        body = wire['body']
        assert body['model'] == 'gpt-5.6-terra' and body['reasoning'] == {'effort': 'low'}
        assert body['instructions'] == rubric
        assert body['tools'] == [] and body['tool_choice'] == 'none'
        counts['verified_subscription_requests'] += 1
        folder = path.parent
        if (folder / 'response.json').exists():
            response = json.loads((folder / 'response.json').read_text())
            assert response['response_model'] == 'gpt-5.6-terra'
            raw = json.loads((folder / 'raw_response.json').read_text())
            assert raw['status'] == 'completed'
            counts['verified_completed_judgments'] += 1
            label = json.loads((folder / 'judgment.json').read_text())
            text = response['text']
            if (folder / 'parse_repair.json').exists():
                repair = json.loads((folder / 'parse_repair.json').read_text())
                index = repair['insert_at']
                assert repair['inserted'] in ('"', '"}')
                assert repair['repaired_text'] == text[:index] + repair['inserted'] + text[index:]
                text = repair['repaired_text']
                counts['syntax_only_json_delimiter_repairs'] += 1
            assert json.loads(text) == {k: v for k, v in label.items() if k != 'evidence_verbatim'}
            if not all(label['evidence_verbatim']):
                issues.append(str(folder.relative_to(ROOT)))
    for teacher in providers:
        counts[f'{teacher}_current_judge_errors'] = len(list((ROOT / teacher).glob('*/judge/error.json')))
    counts['archived_rate_limited_attempts'] = len(list(ROOT.glob('*/*/judge_attempt1_rate_limited/error.json')))
    counts['archived_disconnected_attempts'] = len(list(ROOT.glob('*/*/judge_attempt1_disconnected/error.json')))
    save(ROOT / 'audit.json', {'checks_passed': True, 'counts': dict(counts),
        'nonverbatim_evidence_folders': issues,
        'evidence_note': 'Literal substring check permits surrounding quotation marks. Ellipses, joined excerpts, changed whitespace and other differences remain flagged. Labels are unchanged.',
        'target_settings_evidence': 'Saved config plus shared generator source; API result reports provider, model and usage, not a full target wire request.'})
    print(json.dumps(dict(counts), indent=2))


if __name__ == '__main__':
    main()
