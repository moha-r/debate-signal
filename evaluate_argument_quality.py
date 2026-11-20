"""Frozen argument diagnostics, external role mapping, source links and full-wrapper latency.

This script never fits models or changes policies. Corpus source text stays in ignored data/raw.
"""
import argparse
import csv
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
from time import perf_counter
import xml.etree.ElementTree as ET

import numpy as np
from sklearn.metrics import classification_report, confusion_matrix, f1_score

from conversation_insights import argument_for, session_insights
from moderation_session import analyze_turn, load_resources, new_session

ROOT = Path(__file__).resolve().parent
ROLES = ['claim','reason','rebuttal','question','agreement','unclassified']


def save_json(path, value):
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n')


def save_csv(path, rows):
    if not rows:
        return
    with path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)


def role_metrics(rows, labels=ROLES):
    y=[r['reference_role'] for r in rows]
    p=[r['predicted_role'] for r in rows]
    return {'n':len(rows),'accuracy':sum(a==b for a,b in zip(y,p))/len(y),
            'macro_f1':float(f1_score(y,p,labels=labels,average='macro',zero_division=0)),
            'classes':classification_report(y,p,labels=labels,output_dict=True,zero_division=0),
            'confusion_labels':ROLES,'confusion':confusion_matrix(y,p,labels=ROLES).tolist()}


def link_metrics(rows):
    gold=sum(bool(r['reference_links']) for r in rows)
    predictions=sum(r['predicted_link'] is not None for r in rows)
    correct=sum(r['predicted_link'] is not None and r['predicted_link'] in r['reference_links'] for r in rows)
    no_link=[r for r in rows if not r['reference_links']]
    false_on_empty=sum(r['predicted_link'] is not None for r in no_link)
    precision=correct/predictions if predictions else 0
    recall=correct/gold if gold else 0
    return {'turns':len(rows),'gold_linked_turns':gold,'predicted_links':predictions,'correct_links':correct,
            'precision':precision,'recall':recall,'f1':2*precision*recall/(precision+recall) if precision+recall else 0,
            'no_link_turns':len(no_link),'false_links_on_no_link_turns':false_on_empty,
            'false_link_rate':false_on_empty/len(no_link) if no_link else 0}


def pair_metrics(reference, predicted):
    good=len(reference & predicted)
    precision=good/len(predicted) if predicted else 0
    recall=good/len(reference) if reference else 0
    return {'reference_pairs':len(reference),'predicted_pairs':len(predicted),'correct_pairs':good,
            'precision':precision,'recall':recall,'f1':2*precision*recall/(precision+recall) if precision+recall else 0}


class CachedEncoder:
    def __init__(self, model): self.model,self.values=model,{}
    def encode(self,text,normalize_embeddings=True):
        if text not in self.values:
            self.values[text]=self.model.encode(text,normalize_embeddings=normalize_embeddings)
        return self.values[text]


def dialogue_audit(cases, resources, isolated=False):
    rows=[];reference_answers=set();predicted_answers=set();source_errors=[]
    for case in cases:
        state=new_session(case['topic'],resources)
        for number, gold in enumerate(case['turns'],1):
            if isolated:
                turn={'number':number,'speaker':gold['speaker'],'text':gold['text'],
                      'topic':{'state':'off_topic' if gold['role']=='unclassified' else 'on_topic'},'personal_attack':False}
                turn['argument']=argument_for(turn,state['turns'],resources[2])
                state['turns'].append(turn)
            else:
                state=analyze_turn(state,gold['speaker'],gold['text'],resources)
                turn=state['turns'][-1]
            prediction=turn['argument']
            link=prediction.get('link')
            rows.append({'session':case['id'],'turn':number,'speaker':gold['speaker'],'text':gold['text'],
                         'reference_role':gold['role'],'predicted_role':prediction['role'],
                         'reference_links':gold['links'],'predicted_link':link['turn'] if link else None,
                         'reference_evidence_request':gold['evidence_requested'],
                         'predicted_evidence_request':prediction['evidence_requested'],
                         'topic_state':turn['topic']['state'],'personal_attack':turn['personal_attack'],
                         'cue':prediction['cue']})
            reference_answers.update((case['id'],q,number) for q in gold['answer_to'])
        insights=session_insights(state)
        predicted_answers.update((case['id'],q['turn'],answer) for q in insights['report']['questions'] for answer in q['answer_turns'])
        source={t['number']:t for t in state['turns']}
        for node in insights['arguments']:
            if node['turn'] not in source or node['text']!=source[node['turn']]['text']:
                source_errors.append({'session':case['id'],'node':node['turn']})
            if node['link'] and not 0<node['link']['turn']<node['turn']:
                source_errors.append({'session':case['id'],'invalid_link':node['turn']})
            for response in node.get('answers',[]):
                span=response.get('answer_span')
                if span and (not 0<=span['start']<span['end']<=len(node['text'])
                             or node['text'][span['start']:span['end']]!=span['text']):
                    source_errors.append({'session':case['id'],'invalid_answer_span':node['turn']})
    evidence_reference={ (r['session'],r['turn']) for r in rows if r['reference_evidence_request'] }
    evidence_predicted={ (r['session'],r['turn']) for r in rows if r['predicted_evidence_request'] }
    result={'roles':role_metrics(rows),'links':link_metrics(rows),'question_answers':pair_metrics(reference_answers,predicted_answers),
            'evidence_requests':pair_metrics(evidence_reference,evidence_predicted),'source_integrity_errors':source_errors,
            'beyond_link_window':sum(bool(r['reference_links']) and all(r['turn']-n>6 for n in r['reference_links']) for r in rows)}
    return result,rows


def corpus_units(path):
    graph=ET.parse(path).getroot()
    edus={node.get('id'):(position,''.join(node.itertext()).strip()) for position,node in enumerate(graph.findall('edu'))}
    edges=[node.attrib for node in graph.findall('edge')]
    segmentation={}
    for edge in edges:
        if edge['type']=='seg': segmentation.setdefault(edge['trg'],[]).append(edge['src'])
    def grounded(node,visited=()):
        if node in visited: raise ValueError('Cycle in segmentation graph')
        if node in edus: return [edus[node]]
        return [item for src in segmentation.get(node,[]) for item in grounded(src,(*visited,node))]
    units=[]
    for adu in graph.findall('adu'):
        spans=sorted(set(grounded(adu.get('id'))))
        outgoing=[e for e in edges if e['type']!='seg' and e['src']==adu.get('id')]
        role=None
        if not outgoing: role='claim'
        elif len(outgoing)==1:
            if outgoing[0]['type'] in ('sup','exa'): role='reason'
            elif outgoing[0]['type'] in ('reb','und'): role='rebuttal'
        if spans:
            units.append({'id':adu.get('id'),'position':spans[0][0],'text':' '.join(t for _,t in spans),
                          'speaker':'A' if adu.get('type')=='pro' else 'B','role':role,
                          'outgoing':outgoing})
    return graph.attrib,sorted(units,key=lambda u:u['position'])


def external_audit(root,encoder):
    rows=[];link_rows=[];excluded=[]
    for path in sorted(root.glob('*.xml')):
        meta,units=corpus_units(path)
        previous=[];by_id={u['id']:n for n,u in enumerate(units,1)}
        for number,unit in enumerate(units,1):
            turn={'number':number,'text':unit['text'],'speaker':unit['speaker'],
                  'topic':{'state':'on_topic'},'personal_attack':False}
            prediction=argument_for(turn,previous,encoder);turn['argument']=prediction
            previous.append(turn)
            if unit['role'] is None:
                excluded.append({'file':path.stem,'adu':unit['id'],'reason':'Additional-premise or multi-edge role not mapped.'})
                continue
            row={'document':path.stem,'adu':unit['id'],'text_sha256':hashlib.sha256(unit['text'].encode()).hexdigest(),
                 'reference_role':unit['role'],'predicted_role':prediction['role']}
            rows.append(row)
            direct=[e for e in unit['outgoing'] if e['type'] in ('sup','exa','reb') and e['trg'] in by_id]
            if len(direct)==1:
                target=by_id[direct[0]['trg']]
                if 0<number-target<=6:
                    link=prediction.get('link')
                    link_rows.append({**row,'reference_links':[target],'predicted_link':link['turn'] if link else None})
    result={'corpus_manifest':json.loads((root/'manifest.json').read_text()),'documents':len(list(root.glob('*.xml'))),
            'mapping':'No outgoing argumentative edge -> claim; sup/exa -> reason; reb/und -> rebuttal. Additional-premise and multi-edge nodes excluded. Topic/attack states are oracle inputs. Pro/opp roles are mapped to synthetic A/B labels solely for this diagnostic, not actual speaker identification.',
            'scope':'Externally annotated translated written microtexts, not natural spoken dialogues. This coarse role mapping is not the original corpus task.',
            'roles':role_metrics(rows,labels=['claim','reason','rebuttal']),
            'sequential_direct_links':link_metrics(link_rows),'excluded_count':len(excluded),
            'link_scope':'Only direct sup/exa/reb targets already present within six units. Future targets and relation-targeting undercuts excluded; this selected subset cannot establish whole-corpus link accuracy.'}
    return result,rows,link_rows,excluded


def latency_audit(resources):
    # Keep the actual encoder uncached here; cache speed is not serving speed.
    state=new_session('Should public museums offer free admission?',resources)
    pattern=[('A','Public museums should offer free admission.'),('B','I disagree because admission fees pay for maintaining museum collections.'),
             ('A','What evidence supports the expected museum budget shortfall?'),('B','For example, museum admission fees pay for conservation materials.'),
             ('A','I agree that museum collections need protection.')]
    wall=[];reported=[];sources=[]
    for n in range(250):
        speaker,text=pattern[n%len(pattern)]
        text=f'{text} This is contribution number {n+1}.'
        start=perf_counter(); state=analyze_turn(state,speaker,text,resources);insights=session_insights(state)
        wall.append((perf_counter()-start)*1000);reported.append(state['turns'][-1]['latency_ms'])
        if n in (0,49,249): sources.append({'turns':n+1,'snapshot_bytes':len(json.dumps(insights)),'wall_ms':wall[-1]})
    return {'scope':'One 250-turn scripted discussion with unique incoming texts on the actual CPU encoder. Serving caches may reuse historical embeddings; includes analysis, copying state and insight generation, excludes ASR, HTTP and browser rendering.',
            'cold_first_ms':wall[0],'warm_median_ms':float(np.median(wall[1:])),
            'warm_p95_ms':float(np.percentile(wall[1:],95)),'last_50_median_ms':float(np.median(wall[-50:])),
            'reported_median_ms':float(np.median(reported[1:])),
            'median_unreported_ms':float(np.median(np.array(wall[1:])-np.array(reported[1:]))),'checkpoints':sources}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='results/predeploy_audit/baseline');parser.add_argument('--skip-latency',action='store_true');parser.add_argument('--fixtures',default='data/argument_quality_audit.json');parser.add_argument('--skip-external',action='store_true')
    args=parser.parse_args();out=ROOT/args.output
    if (out/'summary.json').exists(): raise SystemExit('Use a new output directory to preserve this audit run.')
    out.mkdir(parents=True,exist_ok=True)
    source=ROOT/args.fixtures;fixture=json.loads(source.read_text())
    resources=load_resources();cached=(resources[0],resources[1],CachedEncoder(resources[2]))
    summary={'scope':fixture['provenance'],'fixture_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
             'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ('answer_extraction.py','argument_models.py','dialogue_relations.py','question_tracker.py','conversation_insights.py','moderation_session.py','local_dashboard.py','auth_store.py','session_store.py','voice_gateway.py')},
             'relation_policy':json.loads((ROOT/'artifacts/dialogue_relation_policy.json').read_text()),
             'model_sha256':hashlib.sha256((ROOT/'artifacts/argument_models_v2.joblib').read_bytes()).hexdigest() if (ROOT/'artifacts/argument_models_v2.joblib').exists() else None,
             'runtime':{'python':platform.python_version(),'platform':platform.platform(),'packages':{name:version(name) for name in ('numpy','scikit-learn','sentence-transformers','torch','fastapi','starlette','websockets')}}}
    for mode,isolated in [('isolated',True),('end_to_end',False)]:
        result,rows=dialogue_audit(fixture['cases'],cached,isolated)
        summary[mode]=result;save_csv(out/f'{mode}_turns.csv',rows)
        save_csv(out/f'{mode}_errors.csv',[r for r in rows if r['reference_role']!=r['predicted_role'] or (r['predicted_link'] not in r['reference_links'] if r['reference_links'] else r['predicted_link'] is not None)])
        print(mode,json.dumps({key:result[key] for key in ('links','question_answers','evidence_requests')}),'role_accuracy',result['roles']['accuracy'],flush=True)
    corpus=ROOT/'data/raw/arg-microtexts'
    if not args.skip_external and (corpus/'manifest.json').exists():
        result,rows,links,excluded=external_audit(corpus,cached[2]);summary['external']=result
        save_csv(out/'external_roles.csv',rows);save_csv(out/'external_links.csv',links);save_csv(out/'external_excluded.csv',excluded)
        print('external',result['roles']['n'],'role_accuracy',result['roles']['accuracy'],'role_macro_f1',result['roles']['macro_f1'],'links',result['sequential_direct_links'],flush=True)
    else: summary['external']={'status':'not_run','reason':'Pinned corpus not present; no external accuracy claim.'}
    if not args.skip_latency:
        summary['latency']=latency_audit(resources);print('latency',json.dumps(summary['latency']),flush=True)
    save_json(out/'summary.json',summary)


if __name__=='__main__': main()
