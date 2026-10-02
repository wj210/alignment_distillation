"""Native leaking and DeceptionBench evaluations, with AtlasCloud and Terra."""
import hashlib
import importlib
import json
import os
import shutil
import sys
from collections import Counter
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
ROOT = PROJECT / 'results/ds4f_atlas_leaking_deceptionbench_20260930'


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    from dotenv import dotenv_values
    import httpx
    from inspect_ai import eval_set, task_with
    from inspect_ai.model import GenerateConfig, Model, get_model
    from inspect_deceptionbench import deceptionbench, deception_solver
    from inspect_evals.agentic_misalignment import agentic_misalignment
    from evals.scout_terra import TerraSubscription
    from evals.suite import capture_deception_reasoning, exclude_cap_hits

    ROOT.mkdir(exist_ok=False)
    os.environ['OPENROUTER_API_KEY'] = dotenv_values(PROJECT / '.env')['OPENROUTER_API_KEY']
    judge = Model(TerraSubscription(ROOT / 'judge_calls', pace_seconds=1),
                  config=GenerateConfig(max_connections=8, max_retries=0, reasoning_effort='low'))
    teachers = {'april': 'deepseek/deepseek-v4-flash', 'july': 'deepseek/deepseek-v4-flash-0731'}
    endpoints = {}
    with httpx.Client(timeout=30) as client:
        for teacher, name in teachers.items():
            response = client.get(f'https://openrouter.ai/api/v1/models/{name}/endpoints')
            response.raise_for_status()
            matches = [e for e in response.json()['data']['endpoints'] if e.get('tag') == 'atlas-cloud/fp4']
            assert len(matches) == 1 and matches[0]['status'] == 0
            endpoints[teacher] = matches[0]
    save(ROOT / 'endpoints.json', endpoints)
    tasks = [task_with(agentic_misalignment(scenario='leaking', grader_model=judge),
                       name='agentic_misalignment_leaking', epochs=40),
             task_with(deceptionbench(judge_model=judge), name='deceptionbench',
                       solver=[deception_solver(), capture_deception_reasoning()])]
    for task in tasks:
        task.scorer = [exclude_cap_hits(scorer, 32768) for scorer in task.scorer]
    data = [{'id': sample.id, **sample.metadata} for sample in tasks[1].dataset]
    assert len(data) == len({row['id'] for row in data}) == 180
    staged = Path('/tmp/deceptionbench_atlas_data.json')
    save(staged, data)
    dataset = PROJECT / 'datasets/deceptionbench'
    dataset.mkdir(exist_ok=True)
    destination = dataset / 'data.json'
    if destination.exists():
        assert destination.read_bytes() == staged.read_bytes()
    else:
        shutil.copy2(staged, destination)
    module = importlib.import_module('inspect_deceptionbench.deceptionbench')
    save(dataset / 'manifest.json', {'dataset': module.DATASET_PATH, 'revision': module.DATASET_REVISION,
        'count': len(data), 'types': dict(Counter(row['type'] for row in data)),
        'sha256': hashlib.sha256(destination.read_bytes()).hexdigest()})
    models = [get_model('openrouter/' + name, stream=True, max_retries=0,
        reasoning_enabled=True,
        provider={'only': ['atlas-cloud/fp4'], 'allow_fallbacks': False, 'require_parameters': True},
        config=GenerateConfig(max_connections=32, max_retries=0, max_tokens=32768,
                              temperature=1, top_p=0.95, reasoning_effort='high'))
        for name in teachers.values()]
    save(ROOT / 'config.json', {'teachers': teachers, 'provider': 'atlas-cloud/fp4',
        'reasoning_effort': 'high', 'temperature': 1, 'top_p': 0.95, 'max_tokens': 32768,
        'teacher_concurrency_per_model': 32, 'sample_concurrency_total': 64,
        'leaking_epochs': 40, 'deceptionbench_samples': 180,
        'deceptionbench_revision': module.DATASET_REVISION,
        'dataset_sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
        'judge': 'gpt-5.6-terra', 'judge_route': 'ChatGPT/Codex subscription',
        'judge_effort': 'low', 'judge_concurrency_total': 8, 'judge_start_interval_seconds': 1,
        'judge_decoding': 'subscription default; native scorer temperature request not forwarded',
        'retries': 0, 'fallbacks': False, 'cap_hits': 'unscored, never regenerated',
        'deceptionbench_protocol': 'native neutral/pressured solver and three consistency judges; existing native-reasoning capture'})
    code = ROOT / 'code'
    code.mkdir()
    sources = [Path(__file__), PROJECT / 'evals/scout_terra.py', PROJECT / 'evals/scout_terra_worker.py',
               PROJECT / 'evals/suite.py', Path(module.__file__)]
    hashes = {}
    for source in sources:
        shutil.copy2(source, code / source.name)
        hashes[source.name] = hashlib.sha256(source.read_bytes()).hexdigest()
    save(ROOT / 'code_manifest.json', hashes)
    active = PROJECT / 'results/active'
    shutil.move(active, PROJECT / 'results/archive/active_before_atlas_leaking_deceptionbench_20260930')
    active.mkdir()
    (active / ROOT.name).symlink_to(Path('..') / ROOT.name)
    save(ROOT / 'status.json', {'status': 'running'})
    success, logs = eval_set(tasks, model=models, log_dir=str(ROOT / 'inspect'),
        max_tasks=4, max_samples=64, retry_on_error=0, retry_attempts=1,
        incomplete_action='error', fail_on_error=False, display='plain', log_buffer=1)
    save(ROOT / 'status.json', {'status': 'finished', 'success': success,
        'logs': [{'task': log.eval.task, 'model': log.eval.model, 'status': log.status,
                  'samples': log.results.total_samples if log.results else 0} for log in logs]})


if __name__ == '__main__':
    main()
