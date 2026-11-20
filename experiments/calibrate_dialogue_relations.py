"""Select a fixed operating point on Part 2 development documents only."""
import json
import math
import resource
from time import perf_counter

from evaluate_dialogue_relations import ROOT, MODEL, REVISION, TransformerPairs


def main():
    import numpy as np
    from argument_models import vector
    from evaluate_argument_quality import corpus_units
    from moderation_session import load_resources

    artifact=json.loads((ROOT/'results/argument_repair/training/manifest.json').read_text())
    sources=[name for name,split in artifact['document_splits'].items() if split=='development']
    encoder=load_resources()[2]
    transformer=TransformerPairs()
    rows=[]
    for name in sources:
        _, units=corpus_units(ROOT/'data/raw/arg-microtexts-part2'/f'{name}.xml')
        for position,unit in enumerate(units):
            outgoing=unit['outgoing']
            if len(outgoing)>1 or any(e['type'] not in ('sup','exa','reb') for e in outgoing):
                continue
            earlier=units[:position]
            gold={(e['trg'],'attack' if e['type']=='reb' else 'support') for e in outgoing if any(t['id']==e['trg'] for t in earlier)}
            # A forward-only gold connection produces no eligible earlier target.
            sims=[float(vector(encoder,unit['text'])@vector(encoder,t['text'])) for t in earlier]
            candidates=sorted(enumerate(earlier),key=lambda x:(sims[x[0]],x[0]),reverse=True)[:6]
            if not candidates:continue
            probabilities=transformer.score([(unit['text'],t['text']) for _,t in candidates])
            scored=[(target['id'],sims[i],position-i,scores) for (i,target),scores in zip(candidates,probabilities)]
            rows.append((gold,scored))
    trials=[]
    for threshold in (.50,.60,.70,.80,.90):
        for margin in (.015,.05,.10):
            predicted=correct=0
            for gold,candidates in rows:
                ranked=[]
                for target,sim,distance,scores in candidates:
                    label=max(('support','attack'),key=scores.get)
                    probability=scores[label]
                    if sim<.20 or probability<threshold or probability<=scores['none']:continue
                    rank=.7*probability+.25*sim+.05*math.exp(-distance/8)
                    ranked.append((rank,target,label))
                ranked.sort(reverse=True)
                if ranked and (len(ranked)==1 or ranked[0][0]-ranked[1][0]>=margin):
                    predicted+=1
                    correct+=(ranked[0][1],ranked[0][2]) in gold
            total=sum(len(gold) for gold,_ in rows)
            trials.append({'threshold':threshold,'margin':margin,'predicted':predicted,'correct':correct,'reference':total,
                           'precision':correct/max(1,predicted),'recall':correct/max(1,total),'f1':2*correct/max(1,predicted+total)})
    eligible=[t for t in trials if t['precision']>=.60 and t['predicted']>=10]
    selected=max(eligible,key=lambda t:(t['f1'],t['precision'])) if eligible else None
    result={'scope':'Part 2 development documents only. Exact earlier target AND relation label. Search a fixed grid for highest F1 with precision >= .60 and at least 10 predictions. None if infeasible.',
            'model':MODEL,'revision':REVISION,'documents':sources,'rows':len(rows),'trials':trials,'selected':selected}
    out=ROOT/'results/dialogue_followup/transformer/calibration.json'
    out.write_text(json.dumps(result,indent=2)+'\n')
    print('selected',selected,flush=True)
    print('trials',trials,flush=True)

    # Separately measure CPU serving cost on representative four- and six-candidate batches.
    transformer.model=transformer.model.to(device='cpu',dtype=transformer.torch.float32)
    transformer.device='cpu'
    transformer.torch.set_num_threads(2)
    examples=json.loads((ROOT/'data/marg_relation_diagnostic.json').read_text())['sets']['proportional'][:60]
    pairs=[(e['later'],e['earlier']) for e in examples]
    transformer.score(pairs[:6])
    batches={}
    for size in (1,4,6):
        times=[]
        for start in range(0,min(60,size*10),size):
            tick=perf_counter();transformer.score(pairs[start:start+size]);times.append((perf_counter()-tick)*1000)
        batches[str(size)]={'median_ms':float(np.median(times)),'p95_ms':float(np.percentile(times,95))}
    speed={'scope':'Warm CPU pair inference including tokenization. 2 Torch threads, 256-token cap; excludes ASR and HTTP. RSS platform units from getrusage.',
           'batches':batches,'peak_rss':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    (out.parent/'cpu_latency.json').write_text(json.dumps(speed,indent=2)+'\n')
    print('CPU',speed,flush=True)


if __name__=='__main__':main()
