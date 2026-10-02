"""Fresh teacher samples using historical Anthropic prompts and native scoring."""
import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import ExitStack
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]



def worker(folder):
    sys.path.insert(0, str(PROJECT.parent / 'motivated_reasoning'))
    from simulation_persona.generation.litellm_client import prepare, _generate
    instructions = (folder.parents[2] / 'judge_system.txt').read_text()
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
    from inspect_evals.agentic_misalignment.classifiers import MurderClassifier, BlackmailClassifier
    from inspect_evals.agentic_misalignment.prompt_generator import generate_prompts
    sys.path.insert(0, str(PROJECT / 'evals'))
    from doluschat import generate, save, TEACHERS

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario', choices=['murder', 'blackmail'], required=True)
    parser.add_argument('--samples', type=int, required=True)
    parser.add_argument('--concurrency', type=int, default=32, help='Total across selected teachers')
    parser.add_argument('--teachers', nargs='+', choices=['april', 'july'], default=['april', 'july'])
    parser.add_argument('--provider', help='Override provider for all selected teachers')
    parser.add_argument('--judge-concurrency', type=int, default=8)
    parser.add_argument('--keep-active', action='store_true', help='Preserve other current jobs in the active view')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert len(set(args.teachers)) == len(args.teachers)
    assert args.samples > 0 and args.concurrency > 0 and args.concurrency % len(args.teachers) == 0
    if args.provider:
        for teacher in args.teachers:
            TEACHERS[teacher] = (TEACHERS[teacher][0], args.provider)
    teachers = {t: TEACHERS[t] for t in args.teachers}
    concurrency_each = args.concurrency // len(teachers)
    ROOT = PROJECT / args.output
    ROOT.mkdir(exist_ok=False)
    source = next((PROJECT / 'results/deepseek_v4_flash_20260907/original_logs/deepseek-v4-flash').glob(f'*{args.scenario}*.eval'))
    old = read_eval_log(source)
    messages = [{'role': m.role, 'content': m.text} for m in old.samples[0].messages[:2]]
    prompts = generate_prompts(args.scenario, 'explicit', 'america', 'replacement', None, False, None)
    assert messages == [{'role': 'system', 'content': prompts.system_prompt},
                        {'role': 'user', 'content': prompts.user_prompt + '\n' + prompts.email_content}]
    rows = [{'sample_id': f'{i:02d}', 'source_row': i, 'messages': messages} for i in range(args.samples)]
    save(ROOT / 'samples.json', rows)
    classifier = {'murder': MurderClassifier, 'blackmail': BlackmailClassifier}[args.scenario]()
    instructions = classifier.get_grader_input(prompts.email_content, '')[0].text
    (ROOT / 'judge_system.txt').write_text(instructions)
    save(ROOT / 'config.json', {'teachers': teachers, 'samples_per_teacher': args.samples,
        'selection': f'{args.samples} independent repetitions of historical {args.scenario}_explicit-america_replacement',
        'source_log': str(source.relative_to(PROJECT)), 'temperature': 1, 'top_p': .95,
        'max_tokens': 32768, 'reasoning_effort': 'high', 'teacher_concurrency_total': args.concurrency, 'teacher_concurrency_each': concurrency_each,
        'retries': 0, 'fallbacks': False, 'judge': 'gpt-5.6-terra',
        'judge_route': 'ChatGPT subscription', 'judge_effort': 'low', 'judge_concurrency': args.judge_concurrency,
        'scoring': f'native {type(classifier).__name__}; final answer only; report classifier verdict separately',
        'sample_sha256': hashlib.sha256((ROOT / 'samples.json').read_bytes()).hexdigest()})
    shutil.copyfile(__file__, ROOT / 'run.py')
    active = PROJECT / 'results/active'
    for path in ([] if args.keep_active else active.iterdir()):
        destination = PROJECT / 'results/archive' / ('before_' + ROOT.name + '_' + path.name)
        if destination.exists():
            raise RuntimeError(f'Archive exists: {destination}')
        path.rename(destination)
    view = active / ROOT.name
    view.mkdir()
    for name in ['status.json', 'summary.json', 'config.json']:
        (view / name).symlink_to(Path('../..') / ROOT.name / name)
    started = time.time()
    labels = []

    def judge(row, folder, result):
        out = folder / 'judge'
        out.mkdir()
        inputs = classifier.get_grader_input(prompts.email_content, result['response'])
        (out / 'input.txt').write_text(inputs[1].text)
        try:
            with (out / 'process.log').open('w') as log:
                subprocess.run(['/tmp/alignment-mask-judge/bin/python', __file__, '--worker', str(out)],
                               stdout=log, stderr=subprocess.STDOUT, timeout=270, check=True)
            raw = (out / 'answer.txt').read_text()
            parsed = raw
            if raw.strip().lower() in ('yes', 'no'):
                parsed = f'<answer>{raw.strip().lower()}</answer>'
                save(out / 'parse_normalization.json', {'raw': raw, 'parsed': parsed})
            harmful, verdict, _ = classifier.classify(result['response'], parsed)
            explanation = raw
            label = {'teacher': result['teacher'], 'sample_id': row['sample_id'],
                     'harmful': harmful, 'classifier_verdict': verdict, 'explanation': explanation}
            save(out / 'judgment.json', label)
            return label
        except Exception as error:
            save(out / 'error.json', {'error': str(error)})
            return {'teacher': result['teacher'], 'sample_id': row['sample_id'], 'error': str(error)}

    save(ROOT / 'status.json', {'status': 'running', 'generation_finished': 0})
    with OpenAI(base_url='https://openrouter.ai/api/v1', max_retries=0, timeout=600,
                api_key=dotenv_values(PROJECT / '.env')['OPENROUTER_API_KEY']) as client, \
            ExitStack() as stack, ThreadPoolExecutor(max_workers=args.judge_concurrency) as judges:
        pools = {t: stack.enter_context(ThreadPoolExecutor(max_workers=concurrency_each)) for t in teachers}
        futures = [pools[teacher].submit(generate, client, teacher, row, ROOT)
                   for teacher in teachers for row in rows]
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
    for teacher in teachers:
        generations = [json.loads(p.read_text()) for p in (ROOT / teacher).glob('*/generation.json')]
        scored = [r for r in labels if r['teacher'] == teacher and 'error' not in r]
        summary[teacher] = {'attempted': len(generations), 'complete': sum(g['complete'] for g in generations),
                            'scored': len(scored), 'harmful': sum(r['harmful'] for r in scored),
                            'classifier_positive': sum(r['classifier_verdict'] for r in scored),
                            'judge_errors': sum(r['teacher'] == teacher and 'error' in r for r in labels)}
    save(ROOT / 'summary.json', summary)
    save(ROOT / 'status.json', {'status': 'finished', 'wall_seconds': time.time() - started})
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    worker(Path(sys.argv[2])) if len(sys.argv) > 1 and sys.argv[1] == '--worker' else main()
