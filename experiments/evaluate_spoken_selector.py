"""Compare target selectors on development and held-out radio episodes."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path

from evaluate_dialogue_relations import ROOT
from relation_context import action_verb, has_reply_cue, relation_rank
from argument_models import words


def measure(groups, selector, errors=None):
    totals = Counter()
    for group in groups:
        turn = group['turn']
        expected={(n,label) for n,label in group['gold']}
        totals['turns'] += 1
        totals['targets'] += bool(expected)
        totals['reachable'] += any(t['number']==n and t['similarity']>=.20
                                  for t in group['targets'] for n,_ in expected)
        ranked = []
        for target in group['targets']:
            scores=target['raw']
            label=max(('support','attack'),key=scores.get)
            if target['similarity']<.20 or scores[label]<.50 or scores[label]<=scores['none']:
                continue
            value=selector(turn,target,label)
            if value is not None:
                ranked.append((value,target['number'],label))
        ranked.sort(reverse=True)
        prediction=None
        if ranked and (len(ranked)==1 or ranked[0][0]-ranked[1][0]>=.015):
            _, source, label=ranked[0]
            prediction=(source,label)
            totals['predicted'] += 1
            totals['target_correct'] += any(n==source for n,_ in expected)
            totals['correct'] += (source,label) in expected
            totals['spurious'] += not expected
        if errors is not None and (prediction is not None or expected) and prediction not in expected:
            reachable=any(t['number']==n and t['similarity']>=.20
                          for t in group['targets'] for n,_ in expected)
            if not expected:
                cause='false_link'
            elif not reachable:
                cause='target_not_retrieved'
            elif prediction is None:
                cause='abstained'
            elif any(n==prediction[0] for n,_ in expected):
                cause='wrong_relation_type'
            else:
                cause='wrong_target'
            errors.append({'episode':group['episode'],'map':group['map'],'turn':turn['number'],
                           'type':cause,'reference':json.dumps(sorted(expected)),
                           'prediction':json.dumps(prediction),
                           'retrieved':json.dumps([t['number'] for t in group['targets']])})
    p, n = totals['predicted'], totals['targets']
    return {**totals, 'precision': totals['correct']/max(1,p),
            'recall': totals['correct']/max(1,n), 'f1': 2*totals['correct']/max(1,p+n),
            'target_f1':2*totals['target_correct']/max(1,p+n)}


def baseline(turn,target,label):
    return relation_rank(target['raw'][label],target['similarity'],turn['number']-target['number'])


def independent_proposal(turn,target,label):
    source, prior = action_verb(turn['text']),action_verb(target['text'])
    if label=='support' and source and prior and source!=prior and not has_reply_cue(turn['text']):
        return None
    return baseline(turn,target,label)


def context_rank(turn,target,label):
    base=independent_proposal(turn,target,label)
    if base is None:
        return None
    detail=words(turn['text'])
    overlap=len(detail&words(target['text']))/max(1,len(detail))
    return .77*base+.15*overlap+.08/(turn['number']-target['number'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('--errors',type=Path)
    args=parser.parse_args()
    data=json.loads(args.input.read_text())
    metrics={'exclusions':data['exclusions'],'scope':'Oracle earlier locutions in annotated radio debates. Separately held-out episodes. Relations directed later source to earlier target. Use only for local academic evaluation.'}
    errors=[]
    for split in ('development','test'):
        groups=[g for g in data['groups'] if g['split']==split]
        metrics[split]={'episodes':sorted({g['episode'] for g in groups})}
        for name,selector in [('baseline',baseline),('independent_proposal',independent_proposal),('context_rank',context_rank)]:
            capture=errors if split=='test' and name=='context_rank' and args.errors else None
            metrics[split][name]=measure(groups,selector,capture)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(metrics,indent=2)+'\n')
    if args.errors and errors:
        with args.errors.open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=errors[0])
            writer.writeheader()
            writer.writerows(errors)
    print(json.dumps(metrics,indent=2))


if __name__=='__main__':
    main()
