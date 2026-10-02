"""Twenty fresh samples per teacher; historical murder prompt and native scoring."""
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT / 'results/ds4f_murder_20_20260929'


def worker(folder):
    sys.path.insert(0, str(PROJECT.parent / 'motivated_reasoning'))
    from simulation_persona.generation.litellm_client import prepare, _generate
    instructions = (ROOT / 'judge_system.txt').read_text()
    prepare(instructions=instructions)
    result = _generate((folder / 'input.txt').read_text(), folder,
                       'gpt-5.6-terra', 'low', 240, instructions)
    (folder / 'answer.txt').write_text(result['text'])


def main():
    import hashlib
    import shutil
    from dotenv import dotenv_values
    from openai import OpenAI
    from inspect_ai.log import read_eval_log
    from inspect_evals.agentic_misalignment.classifiers import MurderClassifier
    from inspect_evals.agentic_misalignment.prompt_generator import generate_prompts
    sys.path.insert(0, str(PROJECT / 'evals'))
    from doluschat import generate, save, TEACHERS

    ROOT.mkdir(exist_ok=False)
    source = next((PROJECT / 'results/deepseek_v4_flash_20260907/original_logs/deepseek-v4-flash').glob('*murder*.eval'))
    old = read_eval_log(source)
    messages = [{'role': m.role, 'content': m.text} for m in old.samples[0].messages[:2]]
    prompts = generate_prompts('murder', 'explicit', 'america', 'replacement', None, False, None)
    assert messages == [{'role': 'system', 'content': prompts.system_prompt},
                        {'role': 'user', 'content': prompts.user_prompt + '\n' + prompts.email_content}]
    rows = [{'sample_id': f'{i:02d}', 'source_row': i, 'messages': messages} for i in range(20)]
    save(ROOT / 'samples.json', rows)
    classifier = MurderClassifier()
    instructions = classifier.get_grader_input(prompts.email_content, '')[0].text
    (ROOT / 'judge_system.txt').write_text(instructions)
    save(ROOT / 'config.json', {'teachers': TEACHERS, 'samples_per_teacher': 20,
        'selection': '20 independent repetitions of historical murder_explicit-america_replacement',
        'source_log': str(source.relative_to(PROJECT)), 'temperature': 1, 'top_p': .95,
        'max_tokens': 32768, 'reasoning_effort': 'high', 'teacher_concurrency': 20,
        'retries': 0, 'fallbacks': False, 'judge': 'gpt-5.6-terra',
        'judge_route': 'ChatGPT subscription', 'judge_effort': 'low', 'judge_concurrency': 8,
        'scoring': 'native MurderClassifier; final answer only; intent AND override in tool XML',
        'sample_sha256': hashlib.sha256((ROOT / 'samples.json').read_bytes()).hexdigest()})
    shutil.copyfile(__file__, ROOT / 'run.py')
    active = PROJECT / 'results/active'
    for path in active.iterdir():
        destination = PROJECT / 'results/archive' / ('before_murder20_' + path.name)
        if destination.exists():
            raise RuntimeError(f'Archive exists: {destination}')
        path.rename(destination)
    view = active / 'ds4f_murder_20'
    view.mkdir()
    for name in ['status.json', 'summary.json', 'config.json']:
        (view / name).symlink_to(Path('../../ds4f_murder_20_20260929') / name)
    started = time.time()
    labels = []

    def judge(row, folder, result):
        out = folder / 'judge'
        out.mkdir()
        inputs = classifier.get_grader_input(prompts.email_content, result['response'])
        (out / 'input.txt').write_text(inputs[1].text)
        try:
            with (out / 'process.log').open('w') as log:
                subprocess.run(['/tmp/alignment-mask-judge/bin/python', __file__, str(out)],
                               stdout=log, stderr=subprocess.STDOUT, timeout=270, check=True)
            harmful, intent, explanation = classifier.classify(result['response'], (out / 'answer.txt').read_text())
            label = {'teacher': result['teacher'], 'sample_id': row['sample_id'],
                     'harmful': harmful, 'intent': intent, 'explanation': explanation}
            save(out / 'judgment.json', label)
            return label
        except Exception as error:
            save(out / 'error.json', {'error': str(error)})
            return {'teacher': result['teacher'], 'sample_id': row['sample_id'], 'error': str(error)}

    save(ROOT / 'status.json', {'status': 'running', 'generation_finished': 0})
    with OpenAI(base_url='https://openrouter.ai/api/v1', max_retries=0, timeout=600,
                api_key=dotenv_values(PROJECT / '.env')['OPENROUTER_API_KEY']) as client, \
            ThreadPoolExecutor(max_workers=40) as targets, ThreadPoolExecutor(max_workers=8) as judges:
        futures = [targets.submit(generate, client, teacher, row, ROOT)
                   for teacher in TEACHERS for row in rows]
        scoring = []
        for count, future in enumerate(as_completed(futures), 1):
            row, folder, result = future.result()
            print(result['teacher'], row['sample_id'], 'complete', result['complete'], flush=True)
            if result['complete']:
                scoring.append(judges.submit(judge, row, folder, result))
            save(ROOT / 'status.json', {'status': 'running', 'generation_finished': count,
                                      'judges_finished': sum(f.done() for f in scoring)})
        for future in as_completed(scoring):
            labels.append(future.result())
    save(ROOT / 'labels.json', labels)
    summary = {}
    for teacher in TEACHERS:
        generations = [json.loads(p.read_text()) for p in (ROOT / teacher).glob('*/generation.json')]
        scored = [r for r in labels if r['teacher'] == teacher and 'error' not in r]
        summary[teacher] = {'attempted': len(generations), 'complete': sum(g['complete'] for g in generations),
                            'scored': len(scored), 'harmful': sum(r['harmful'] for r in scored),
                            'intent': sum(r['intent'] for r in scored),
                            'judge_errors': sum(r['teacher'] == teacher and 'error' in r for r in labels)}
    save(ROOT / 'summary.json', summary)
    save(ROOT / 'status.json', {'status': 'finished', 'wall_seconds': time.time() - started})
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    worker(Path(sys.argv[1])) if len(sys.argv) > 1 else main()
