#!/usr/bin/env python3
"""Maintain a small live results view without changing running jobs."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shlex
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
ACTIVE = ROOT / 'results/active'


def argument(argv, name):
    return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else None


def absolute(value, cwd):
    path = Path(value)
    return path if path.is_absolute() else cwd / path


def processes():
    found = []
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            cwd = (proc / 'cwd').resolve(strict=True)
            if not cwd.is_relative_to(ROOT):
                continue
            argv = (proc / 'cmdline').read_bytes().decode().strip('\0').split('\0')
            names = [Path(part).name for part in argv]
            executable = names[0]
            python = executable.startswith('python')
            bash = executable == 'bash'
            insecure = any(script in argv for script in ('training/train_insecure.py', 'training/run_insecure.sh'))
            if python and 'torchrun' in names and ('training/train.py' in argv or insecure):
                phase = 'training'
            elif bash and len(argv) > 1 and argv[1] in ('training/run.sh', 'training/run_insecure.sh'):
                phase = 'training'
            elif python and any(script in argv for script in ('evals/run.py', 'evals/evaluate_student.py', 'evals.evaluate_student')):
                phase = 'evaluation'
            elif python and any(module in argv for module in ('evals.evalaware', 'evals.scout_eval_logs')):
                phase = 'evaluation'
            elif bash and len(argv) > 1 and argv[1].endswith(('qwen35_9b_study/run.sh', 'qwen35_9b_evalaware/run.sh',
                                                          'qwen35_9b_insecure_wildchat/run.sh',
                                                          'qwen35_9b_huihui_openthoughts/run.sh',
                                                          'qwen35_2b_wildchat_openthoughts/run.sh',
                                                          'qwen35_2b_combined_followup_20260915/run.sh',
                                                          'qwen35_2b_combined_followup_20260915/recover.sh',
                                                          'qwen35_2b_july_eval_20260916/run.sh',
                                                          'qwen35_9b_huihui_openthoughts/evaluate.sh',
                                                          'qwen38_27b_anthropic_eval_awareness_20260914/run.sh')):
                phase = 'pipeline'
            else:
                continue
            stdout = Path(os.readlink(proc / 'fd/1'))
            log = str(stdout) if stdout.is_absolute() and stdout.is_file() else None
            output = argument(argv, '--output' if phase == 'training' else '--results')
            found.append({'pid': int(proc.name), 'phase': phase, 'command': shlex.join(argv),
                          'log': log, 'artifacts': str(absolute(output, cwd)) if output else None,
                          'teacher': argument(argv, '--teacher') or ('insecure' if insecure else None),
                          'model': argument(argv, '--model-name')})
        except (OSError, UnicodeError):
            continue
    return sorted(found, key=lambda item: item['pid'])


def log_status(path):
    try:
        with open(path, 'rb') as source:
            source.seek(max(0, os.fstat(source.fileno()).st_size - 8192))
            tail = source.read().decode(errors='replace').replace('\r', '\n').splitlines()
        return {'path': path, 'age_seconds': round(time.time() - Path(path).stat().st_mtime, 1),
                'tail': '\n'.join(line for line in tail if line.strip())[-4000:]}
    except OSError:
        return {'path': path, 'unavailable': True}


def update():
    current = processes()
    stages = [item for item in current if item['phase'] != 'pipeline']
    launchers = [item for item in current if item['phase'] == 'pipeline']
    status_path = ACTIVE / 'status.json'
    previous = json.loads(status_path.read_text()) if status_path.exists() else {}
    links = {}
    markers = []
    for item in stages:
        label = item['teacher'] or item['model'] or str(item['pid'])
        if item['log']:
            log = Path(item['log'])
            links['train.log' if item['phase'] == 'training' else f'{label}-{log.name}'] = log
            links[f'results-{label}'] = log.parent
            if item['phase'] == 'training':
                markers.append(str(log.parent / f'train-{label}.complete'))
            elif item['artifacts']:
                command = shlex.split(item['command'])
                if 'evals.evalaware' in command:
                    phase = command[command.index('evals.evalaware') + 1]
                    markers.append(str(log.parent / f'{phase}.complete'))
                elif 'evals.scout_eval_logs' in command:
                    markers.append(str(log.parent / 'scan_status.json'))
                else:
                    phase = Path(item['artifacts']).name
                    markers.append(str(log.parent / f'{phase}.complete'))
        if item['artifacts']:
            artifact = Path(item['artifacts'])
            links[f'artifacts-{label}'] = artifact
            if (artifact / 'vllm.log').exists():
                links[f'{label}-vllm.log'] = artifact / 'vllm.log'
            config = artifact / 'run_config.json'
            if config.exists():
                links[f'config-{label}.json'] = config
    for item in launchers:
        if item['log']:
            pipeline = Path(item['log'])
            links['pipeline.log'] = pipeline
            links['run.sh'] = pipeline.parent / 'run.sh'
    study_marker = next((str(Path(item['log']).parent / 'complete')
                         for item in reversed(launchers) if item['log']), previous.get('study_completion_marker'))
    # The visible pipeline may be a follow-up to an already completed training run.
    if not launchers and (ACTIVE / 'pipeline.log').is_symlink():
        study_marker = str((ACTIVE / 'pipeline.log').resolve().parent / 'complete')
    if stages or launchers:
        for name, target in links.items():
            temporary = ACTIVE / f'.{name}.tmp'
            temporary.unlink(missing_ok=True)
            temporary.symlink_to(target)
            temporary.replace(ACTIVE / name)
        for old in ACTIVE.iterdir():
            if old.is_symlink() and old.name not in links:
                old.unlink()
    else:
        markers = previous.get('completion_markers', [])
    state = 'running' if stages else ('between_stages' if launchers else 'stopped')
    required = markers + ([study_marker] if study_marker else [])
    if not stages and not launchers and required and all(Path(path).exists() for path in required):
        state = 'complete'
    logs = [str(path.resolve()) for path in ACTIVE.iterdir() if path.is_symlink() and path.suffix == '.log']
    status = {'checked_at': datetime.now(timezone.utc).isoformat(), 'state': state,
              'processes': current, 'completion_markers': markers,
              'study_completion_marker': study_marker,
              'last_stage': [{key: item[key] for key in ('phase', 'teacher', 'model', 'artifacts')}
                             for item in stages] or ([] if launchers else previous.get('last_stage', [])),
              'logs': [log_status(path) for path in sorted(set(logs))]}
    temporary = ACTIVE / '.status.json.tmp'
    temporary.write_text(json.dumps(status, indent=2) + '\n')
    temporary.replace(status_path)
    lines = [f"Checked: {status['checked_at']}", f"State: {state}",
             'PIDs: ' + ', '.join(str(item['pid']) for item in current)]
    for stage in status['last_stage']:
        lines.append(f"Stage: {stage['phase']} {stage['teacher'] or stage['model']} ({stage['artifacts']})")
    for log in status['logs']:
        tail = log.get('tail', '').splitlines()
        lines.append(f"{Path(log['path']).name} — age {log.get('age_seconds', '?')}s")
        loss = next((line for line in reversed(tail) if 'loss' in line), None)
        if loss and loss not in tail[-2:]:
            lines.append(loss)
        lines.extend(tail[-2:])
    temporary = ACTIVE / '.status.txt.tmp'
    temporary.write_text('\n'.join(lines) + '\n')
    temporary.replace(ACTIVE / 'status.txt')


def main():
    global ACTIVE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--watch', action='store_true', help='Refresh every 30 seconds')
    parser.add_argument('--active-dir', type=Path, default=ACTIVE,
                        help='Separate status directory for jobs on another host')
    args = parser.parse_args()
    ACTIVE = args.active_dir
    ACTIVE.mkdir(parents=True, exist_ok=True)
    with (ACTIVE / '.updater.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        while True:
            update()
            if not args.watch:
                break
            time.sleep(30)


if __name__ == '__main__':
    main()
