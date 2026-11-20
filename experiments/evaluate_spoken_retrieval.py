"""Compare retrieval at a fixed six-candidate inference budget."""
from collections import Counter
import json
from pathlib import Path

from benchmark_spoken_relations import CORPUS, DEVELOPMENT, extract
from argument_models import vector, words
from moderation_session import load_resources


def run(output):
    encoder=load_resources()[2]
    manifest=json.loads((CORPUS/'manifest.json').read_text())
    variants={'baseline':(0,0),'recent':(.10,0),'detail':(0,.15),'both':(.10,.15),'strong_recent':(.22,.10)}
    metrics={split:{key:Counter() for key in variants} for split in ('development','test')}
    for episode, ident, _, _ in manifest['maps']:
        turns, edges, _=extract(json.loads((CORPUS/f'{ident}.json').read_text()))
        references={}
        for source,target,_ in edges:
            references.setdefault(source,set()).add(target)
        split='development' if episode in DEVELOPMENT else 'test'
        for j,turn in enumerate(turns):
            want=references.get(turn['number'])
            if not want:
                continue
            src=vector(encoder,turn['text'])
            detail=words(turn['text'])
            pool=[(t['number'],float(src@vector(encoder,t['text'])),len(words(t['text'])&detail)/max(1,len(detail))) for t in turns[:j]]
            for key,(recency,overlap) in variants.items():
                top=sorted(pool,key=lambda p:(p[1]+recency/(turn['number']-p[0])+overlap*p[2],p[0]),reverse=True)[:6]
                metric=metrics[split][key]
                metric['turns']+=1
                metric['reachable']+=any(p[0] in want and p[1]>=.20 for p in top)
    for variants in metrics.values():
        for metric in variants.values():
            metric['recall_at_6']=metric['reachable']/metric['turns']
    output.write_text(json.dumps(metrics,indent=2)+'\n')
    print(json.dumps(metrics,indent=2))


if __name__=='__main__':
    import sys
    run(Path(sys.argv[1]))
