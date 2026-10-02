"""DS4F comparison on School of Reward Hacks; cached attempts, no retries.

Modes: generate, calibrate (one reference pair per task), judge, worker, judge-pool.
Use judge-pool in the separate LiteLLM environment for the full comparison.
"""
import hashlib
import argparse
import fcntl
import json
import os
import subprocess
import signal
import sys
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get('REWARD_HACKS_OUTPUT', PROJECT / 'results/ds4f_reward_hacks_20260929'))
CACHE = PROJECT / 'datasets/school_of_reward_hacks/samples.json'
RUBRIC = PROJECT / 'evals/reward_hacks_judge.txt'
JUDGE_PYTHON = '/tmp/alignment-mask-judge/bin/python'
sys.path.insert(0, str(PROJECT))


def save(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def worker(folder):
    sys.path.insert(0, str(PROJECT.parent / 'motivated_reasoning'))
    from simulation_persona.generation.litellm_client import prepare, _generate
    instructions = (ROOT / 'judge_system.txt').read_text()
    prepare(instructions=instructions)
    result = _generate((folder / 'input.txt').read_text(), folder,
                       'gpt-5.6-terra', 'low', 240, instructions)
    parse_judgment(folder, result)


def parse_judgment(folder, result):
    label = json.loads(result['text'])
    assert label['reward_hacking'] in ('yes', 'no', 'uncertain')
    assert label['task_quality'] in ('adequate', 'poor', 'uncertain')
    assert type(label['refusal']) is bool
    assert isinstance(label['evidence'], list)
    answer = json.loads((folder / 'input.txt').read_text())['answer']
    assert all(isinstance(q, str) for q in label['evidence'])
    label['evidence_verbatim'] = [q in answer or q.strip('\"\u201c\u201d') in answer
                                  for q in label['evidence']]
    assert isinstance(label['explanation'], str) and isinstance(label['mechanism'], str)
    save(folder / 'judgment.json', label)


def judge(folder, row, answer):
    if folder.exists():
        return
    folder.mkdir(parents=True)
    save(folder / 'input.txt', {'user_prompt': row['user'], 'answer': answer})
    try:
        with (folder / 'process.log').open('w') as log:
            result = subprocess.run([JUDGE_PYTHON, str(Path(__file__).resolve()),
                'worker', str(folder)], stdout=log, stderr=subprocess.STDOUT, timeout=270)
        if result.returncode:
            save(folder / 'error.json', {'error': f'Worker exited {result.returncode}; see process.log'})
    except Exception as error:
        save(folder / 'error.json', {'error': str(error)})


def completed_generations(rows, teachers):
    pending = {(teacher, row['sample_id']): row for teacher in teachers for row in rows}
    while pending:
        for (teacher, sample_id), row in list(pending.items()):
            folder = ROOT / teacher / sample_id
            path = folder / 'generation.json'
            if path.exists():
                del pending[teacher, sample_id]
                result = json.loads(path.read_text())
                if result['complete']:
                    yield folder / 'judge', row, result['response']
        status = json.loads((ROOT / 'generate_status.json').read_text())
        if status['status'] == 'finished':
            if pending:
                raise RuntimeError(f'{len(pending)} generations missing after run completed')
            break
        if pending:
            time.sleep(2)


def judge_in_process(folder, row, answer):
    """Reuse imported LiteLLM in each process; keep a hard deadline per request."""
    if folder.exists():
        return
    # Limit request starts separately from the eight concurrent in-flight requests.
    with (ROOT / 'judge_request_clock').open('a+') as clock:
        fcntl.flock(clock, fcntl.LOCK_EX)
        clock.seek(0)
        scheduled = max(time.time(), float(clock.read() or 0))
        clock.seek(0)
        clock.truncate()
        clock.write(str(scheduled + 1.0))
        clock.flush()
    time.sleep(max(0, scheduled - time.time()))
    folder.mkdir(parents=True)
    save(folder / 'input.txt', {'user_prompt': row['user'], 'answer': answer})
    def timeout(signum, frame):
        raise TimeoutError('Judge exceeded 270 seconds')
    signal.signal(signal.SIGALRM, timeout)
    signal.alarm(270)
    try:
        worker(folder)
    except Exception as error:
        save(folder / 'error.json', {'error': str(error)})
    finally:
        signal.alarm(0)


def judge_pool():
    """Run in JUDGE_PYTHON so workers share its dependency environment."""
    started = time.time()
    rows = json.loads(CACHE.read_text())
    save(ROOT / 'judge_status.json', {'status': 'running', 'started_unix': started})
    with ProcessPoolExecutor(max_workers=8) as pool:
        jobs = [pool.submit(judge_in_process, *job)
                for job in completed_generations(rows, ('april', 'july'))]
        for count, future in enumerate(as_completed(jobs), 1):
            future.result()
            if count % 100 == 0:
                print('judge', count, '/', len(jobs), flush=True)
            save(ROOT / 'judge_status.json', {'status': 'running', 'finished': count, 'total': len(jobs)})
    save(ROOT / 'judge_status.json', {'status': 'finished', 'wall_seconds': time.time()-started})


def run(mode, provider=None):
    from dotenv import dotenv_values
    from openai import OpenAI
    from evals.doluschat import TEACHERS, generate
    if provider:
        TEACHERS.update({teacher: (model, provider) for teacher, (model, _) in TEACHERS.items()})
    ROOT.mkdir(parents=True, exist_ok=True)
    rows = json.loads(CACHE.read_text())
    config = {'teachers': TEACHERS, 'count_per_teacher': len(rows),
        'sample_sha256': hashlib.sha256(CACHE.read_bytes()).hexdigest(),
        'judge_prompt_sha256': hashlib.sha256(RUBRIC.read_bytes()).hexdigest(),
        'reasoning_effort': 'high', 'concurrency_per_teacher': 32,
        'temperature': 1, 'top_p': 0.95, 'max_tokens': 32768,
        'retries': 0, 'fallbacks': False, 'judge': 'gpt-5.6-terra',
        'judge_route': 'LiteLLM ChatGPT subscription', 'judge_effort': 'low',
        'judge_concurrency': 8, 'judge_input': 'original user prompt and final answer only',
        'scope': 'All released training prompts; teacher baseline, not a heldout student evaluation'}
    if (ROOT / 'config.json').exists():
        assert json.loads((ROOT / 'config.json').read_text()) == json.loads(json.dumps(config))
    save(ROOT / 'config.json', config)
    (ROOT / 'judge_system.txt').write_bytes(RUBRIC.read_bytes())
    started = time.time()
    save(ROOT / f'{mode}_status.json', {'status': 'running', 'started_unix': started})
    if mode == 'generate':
        def teacher_run(teacher):
            with OpenAI(base_url='https://openrouter.ai/api/v1', max_retries=0, timeout=600,
                        api_key=dotenv_values(PROJECT / '.env')['OPENROUTER_API_KEY']) as client:
                with ThreadPoolExecutor(max_workers=32) as pool:
                    jobs = [pool.submit(generate, client, teacher, row, ROOT) for row in rows]
                    for count, future in enumerate(as_completed(jobs), 1):
                        future.result()
                        save(ROOT / f'{teacher}_status.json', {'finished': count, 'total': len(rows)})
                        if count % 100 == 0:
                            print(teacher, count, flush=True)
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(teacher_run, TEACHERS))
    else:
        jobs = []
        if mode == 'calibrate':
            seen = set()
            for row in rows:
                if row['task'] in seen:
                    continue
                seen.add(row['task'])
                for field in ('school_of_reward_hacks', 'control'):
                    if row[field].strip():
                        jobs.append((ROOT / 'calibration' / row['sample_id'] / field, row, row[field]))
        elif mode == 'judge':
            jobs = completed_generations(rows, TEACHERS)
        else:
            raise ValueError(mode)
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(judge, *job) for job in jobs]
            for count, future in enumerate(as_completed(futures), 1):
                future.result()
                if count % 50 == 0:
                    print(mode, count, '/', len(futures), flush=True)
                save(ROOT / f'{mode}_status.json', {'status': 'running', 'finished': count, 'total': len(futures)})
    save(ROOT / f'{mode}_status.json', {'status': 'finished', 'wall_seconds': time.time() - started})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['generate', 'calibrate', 'judge', 'worker', 'judge-pool'])
    parser.add_argument('folder', nargs='?', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT)
    parser.add_argument('--provider')
    args = parser.parse_args()
    ROOT = args.output.resolve()
    # Spawned judge workers inherit the selected run directory.
    os.environ['REWARD_HACKS_OUTPUT'] = str(ROOT)
    if args.mode == 'worker':
        worker(args.folder)
    elif args.mode == 'judge-pool':
        judge_pool()
    else:
        run(args.mode, args.provider)
