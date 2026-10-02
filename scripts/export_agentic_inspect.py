"""Export cached agentic responses and Scout labels for Inspect View; no API calls."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from inspect_ai.log import (
    EvalConfig, EvalDataset, EvalLog, EvalMetric, EvalResults, EvalSample,
    EvalScore, EvalSpec, write_eval_log,
)
from inspect_ai.model import (
    ChatMessageAssistant, ChatMessageSystem, ChatMessageUser,
    ContentReasoning, ContentText, GenerateConfig, ModelOutput,
)
from inspect_ai.scorer import Score


def read(path):
    return json.loads(path.read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--scout', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    config = read(args.source / 'config.json')
    prompts = {r['sample_id']: r['messages'] for r in read(args.source / 'samples.json')}
    awareness = {(r['teacher'], r['sample_id']): r for r in read(args.scout / 'labels.json')}
    args.output.mkdir(parents=True, exist_ok=True)
    for teacher in config['teachers']:
        samples = []
        for path in sorted((args.source / teacher).glob('*/generation.json')):
            generation = read(path)
            if not generation['complete']:
                continue
            sample_id = generation['sample_id']
            judgment = read(path.parent / 'judge/judgment.json')
            scan = awareness[teacher, sample_id]
            messages = [ChatMessageSystem(content=prompts[sample_id][0]['content']),
                        ChatMessageUser(content=prompts[sample_id][1]['content'])]
            content = [ContentReasoning(reasoning=generation['reasoning'])] if generation['reasoning'] else []
            content.append(ContentText(text=generation['response']))
            answer = ChatMessageAssistant(content=content, model=generation['model'])
            scores = {
                'native_harmful': Score(value=int(judgment['harmful']), explanation=judgment['explanation']),
                'semantic_harmful': Score(value=int(judgment['classifier_verdict']), explanation=judgment['explanation']),
                'eval_awareness': Score(value={'YES': 1, 'UNSURE': 0.5, 'NO': 0}[scan['awareness']],
                    answer=scan['awareness'], explanation=scan['explanation'],
                    metadata={'only_in_thinking': scan.get('only_in_thinking')}),
            }
            samples.append(EvalSample(id=sample_id, epoch=1, input=messages, target='',
                messages=[*messages, answer], output=ModelOutput.from_message(answer), scores=scores,
                metadata={'provider': generation['provider'], 'request_id': generation['request_id'],
                          'source': str(path), 'scout_source': str(args.scout), 'cached_export': True}))
        metrics = [EvalScore(name=name, scorer=name, scored_samples=len(samples),
            metrics={'mean': EvalMetric(name='mean', value=sum(s.scores[name].value for s in samples) / len(samples))})
            for name in samples[0].scores]
        log = EvalLog(status='success', eval=EvalSpec(
            created=datetime.now(timezone.utc).isoformat(), task=args.source.name + '_' + teacher,
            dataset=EvalDataset(name='Repeated frozen agentic scenario', samples=len(samples)),
            model=samples[0].messages[-1].model, config=EvalConfig(),
            model_generate_config=GenerateConfig(temperature=1, top_p=0.95, max_tokens=32768, reasoning_effort='high'),
            metadata={'cached_export': True, 'source': str(args.source), 'scout': str(args.scout)}),
            results=EvalResults(total_samples=len(samples), completed_samples=len(samples), scores=metrics), samples=samples)
        destination = args.output / f'{args.source.name}_{teacher}.eval'
        write_eval_log(log, destination)
        print(destination)


if __name__ == '__main__':
    main()
