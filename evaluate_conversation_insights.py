"""Replay existing diagnostics through the upgraded wrapper; no training or tuning."""
import json
from pathlib import Path
from time import perf_counter
import numpy as np
import pandas as pd
from sklearn.metrics import f1_score

from conversation_insights import quotation_context
from evaluate_expanded_audit import binary_metrics
from evaluate_topic_relevance import event_metrics, score_sessions
from moderation_session import analyze_turn, load_resources, new_session

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results/conversation_insights'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    bundle,policy,model=load_resources()
    class Cache:
        def __init__(self): self.vectors={}
        def encode(self,text,normalize_embeddings=True):
            if text not in self.vectors:
                self.vectors[text]=model.encode(text,normalize_embeddings=normalize_embeddings)
            return self.vectors[text]
    encoder=Cache()
    resources=(bundle,policy,encoder)
    cases=json.loads((ROOT/'data/topic_dialogues.json').read_text())['sessions']
    partitions={
        'original_reserved':[s for s in cases if s['split']=='test'],
        'challenge':json.loads((ROOT/'data/topic_challenge.json').read_text())['sessions'],
        'expanded':json.loads((ROOT/'data/topic_stress.json').read_text())['sessions'],
    }
    summary={'scope':'Previously inspected assistant-authored diagnostics. Regression evidence, not independent accuracy validation.',
             'argument_extraction':'Rules with tentative semantic links; no independent argument annotation benchmark yet.',
             'topic':{}}
    for name,sessions in partitions.items():
        baseline,events=score_sessions(sessions,policy['threshold'],policy['backend'],policy['use_context'],encoder)
        records=[]
        for case in sessions:
            state=new_session(case['topic'],resources)
            for speaker,text,reference in case['turns']:
                state=analyze_turn(state,speaker,text,resources)
                records.append(state['turns'][-1]['topic'])
        revised=baseline.copy()
        for field in ('state','alert','used_context','score'):
            revised[field]=[r[field] for r in records]
        def metrics(rows):
            return {**event_metrics(rows,events),
                    'turn_macro_f1':float(f1_score(rows.reference,rows.state,labels=['on_topic','off_topic','unclear'],average='macro',zero_division=0))}
        summary['topic'][name]={'before':metrics(baseline),'after':metrics(revised),
                                'changed_turns':int((baseline.state != revised.state).sum())}
        revised.assign(previous_state=baseline.state,previous_alert=baseline.alert).to_csv(OUT/f'{name}_topic.csv',index=False)
        print(name,summary['topic'][name],flush=True)
    attacks=[c for c in json.loads((ROOT/'data/attack_stress.json').read_text())['cases'] if not c['ambiguous']]
    margins=bundle['pipeline'].decision_function([c['text'] for c in attacks])
    probs=bundle['sigmoid'].predict_proba(margins[:,None])[:,1]
    before=probs>=bundle['threshold']
    after=np.array([prediction and not quotation_context(c['text'],[])['suppressed'] for c,prediction in zip(attacks,before)])
    summary['attack']={'before':binary_metrics([c['attack'] for c in attacks],before),
                       'after':binary_metrics([c['attack'] for c in attacks],after),
                       'changed_cases':int((before!=after).sum())}
    timings=[]
    state=new_session('Should schools require students to wear uniforms?',(bundle,policy,model))
    for speaker,text in [('A','Uniform policies can reduce pressure to buy expensive clothes.'),
                         ('B','I disagree because uniforms can be expensive for families.'),
                         ('A','What evidence supports the claim about uniform costs?'),
                         ('B','For example, a uniform supplier charges more for school clothing.'),
                         ('A','I agree that the uniform cost should be considered.')]*3:
        start=perf_counter()
        state=analyze_turn(state,speaker,text,(bundle,policy,model))
        timings.append((perf_counter()-start)*1000)
    summary['latency']={'scope':'Warm CPU, 15 scripted turns including graph extraction, encoder cache disabled.',
                        'median_ms':float(np.median(timings)),'p95_ms':float(np.percentile(timings,95))}
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    print('attack',summary['attack'],flush=True)
    print('latency',summary['latency'],flush=True)


if __name__=='__main__': main()
