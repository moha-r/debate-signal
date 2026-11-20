"""Fit on Part 2 only, with whole-document development/test splits and no audit fitting."""
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score

from argument_models import role_matrix,pair_matrix,vector
from evaluate_argument_quality import corpus_units
from moderation_session import load_resources

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results/argument_repair/training'


def precision_thresholds(model, x, rows, target=.8):
    """Choose conservative per-class gates using development documents only."""
    probabilities=model.predict_proba(x); predictions=model.predict(x)
    labels=np.array([r['label'] for r in rows]); result={}
    for index,label in enumerate(model.classes_):
        candidates=[]
        for threshold in sorted(set(probabilities[:,index])):
            selected=(predictions==label)&(probabilities[:,index]>=threshold)
            n=int(selected.sum())
            if n>=5 and float((labels[selected]==label).mean())>=target:
                candidates.append(float(threshold))
        result[str(label)]=min(candidates) if candidates else 1.0
    return result


def main():
    import xml.etree.ElementTree as ET
    OUT.mkdir(parents=True,exist_ok=True)
    files=sorted((ROOT/'data/raw/arg-microtexts-part2').glob('*.xml'))
    if len(files)!=171: raise ValueError('Prepare the pinned Part 2 corpus first.')
    ordered=sorted(files,key=lambda p:hashlib.sha256(('argument-v2-split:'+p.stem).encode()).hexdigest())
    splits={p.stem:('test' if i<26 else 'development' if i<52 else 'train') for i,p in enumerate(ordered)}
    roles={k:[] for k in ('train','development','test')};pairs={k:[] for k in roles}
    excluded=0
    # Exact-text and normalized-text exclusions protect both old and newly frozen challenges.
    from nlp_pipeline import preprocess_text
    protected={preprocess_text(t['text']) for name in ('argument_quality_audit.json','argument_repair_holdout.json')
               for case in json.loads((ROOT/'data'/name).read_text())['cases'] for t in case['turns']}
    excluded_overlap=0
    for path in files:
        meta,units=corpus_units(path)
        xml=ET.parse(path).getroot()
        implicit_edus={n.get('id') for n in xml.findall('edu') if n.get('implicit')=='true'}
        implicit_adus={n.get('id') for n in xml.findall('adu') if n.get('implicit')=='true'}
        for e in xml.findall('edge'):
            if e.get('type')=='seg' and e.get('src') in implicit_edus: implicit_adus.add(e.get('trg'))
        units=[u for u in units if u['id'] not in implicit_adus]
        group=splits[path.stem];byid={u['id']:u for u in units}
        for index,u in enumerate(units):
            if preprocess_text(u['text']) in protected:
                excluded_overlap+=1;continue
            if u['role'] is not None:
                roles[group].append({'document':path.stem,'text':u['text'],'context':' '.join(t['text'] for t in units[max(0,index-2):index]),'label':u['role']})
            else: excluded+=1
            direct={e['trg']:('support' if e['type'] in ('sup','exa') else 'attack') for e in u['outgoing'] if e['type'] in ('sup','exa','reb') and e['trg'] in byid}
            # Relation-targeting undercuts/additional premises do not create fabricated direct labels.
            if any(e['type'] in ('und','add') for e in u['outgoing']): continue
            for j,target in enumerate(units):
                if j==index or preprocess_text(target['text']) in protected: continue
                pairs[group].append({'document':path.stem,'text':u['text'],'target':target['text'],
                                     'distance':abs(index-j),'label':direct.get(target['id'],'none')})
    original_train_counts={'roles':len(roles['train']),'pairs':len(pairs['train'])}
    # Train-only discourse-prefix augmentation; development/test remain original human texts.
    roles['train'] += [{**row,'text':{'claim':'My position is that ','reason':'For example, ','rebuttal':'I disagree. '}[row['label']]+row['text']} for row in list(roles['train'])]
    pairs['train'] += [{**row,'text':('I disagree. ' if row['label']=='attack' else 'For example, ')+row['text']} for row in list(pairs['train'])]
    encoder=load_resources()[2]
    word=TfidfVectorizer(ngram_range=(1,2),sublinear_tf=True,min_df=1,max_features=10000)
    char=TfidfVectorizer(analyzer='char_wb',ngram_range=(3,5),sublinear_tf=True,min_df=2,max_features=12000)
    relation_word=TfidfVectorizer(ngram_range=(1,2),sublinear_tf=True,min_df=1,max_features=10000)
    word.fit([r['text'] for r in roles['train']]);char.fit([r['text'] for r in roles['train']])
    relation_word.fit([r['text'] for r in pairs['train']]+[r['target'] for r in pairs['train']])
    role_x={k:role_matrix(v,encoder,word,char) for k,v in roles.items()}
    pair_x={k:pair_matrix(v,encoder,relation_word) for k,v in pairs.items()}
    trials=[];best={};gates={}
    for task,rows,x in [('role',roles,role_x),('relation',pairs,pair_x)]:
        choices=[]
        for c in (.5,2.,8.):
            for weight in (None,'balanced'):
                model=LogisticRegression(C=c,class_weight=weight,max_iter=1200,solver='lbfgs',random_state=42)
                model.fit(x['train'],[r['label'] for r in rows['train']])
                p=model.predict(x['development']);y=[r['label'] for r in rows['development']]
                score=float(f1_score(y,p,average='macro',zero_division=0))
                trial={'task':task,'C':c,'class_weight':weight,'development_macro_f1':score,'development_accuracy':float(accuracy_score(y,p))}
                trials.append(trial);choices.append((score,-c,model,trial))
                print(json.dumps(trial),flush=True)
        _,_,model,trial=max(choices,key=lambda v:(v[0],v[1]))
        best[task]=model
        gates[task]=precision_thresholds(model,x['development'],rows['development'])
        testp=model.predict(x['test']);testy=[r['label'] for r in rows['test']]
        trial['test_macro_f1']=float(f1_score(testy,testp,average='macro',zero_division=0))
        trial['test_accuracy']=float(accuracy_score(testy,testp))
    bundle={'role_model':best['role'],'relation_model':best['relation'],'role_word':word,'role_char':char,
            'relation_word':relation_word,'dimension':len(vector(encoder,'A short discussion.')),
            'version':'argument-models-v2','data_license':'CC BY-NC-SA 4.0','confidence_gates':gates}
    artifact=ROOT/'artifacts/argument_models_v2.joblib';joblib.dump(bundle,artifact)
    report={'source':json.loads((ROOT/'data/raw/arg-microtexts-part2/manifest.json').read_text()),
            'scope':'Original English written microtexts. Whole-document split; source roles/relations mapped as in the audit. No dialogue-audit fitting. This is not independent natural-conversation validation.',
            'documents':{k:sum(s==k for s in splits.values()) for k in roles},'document_splits':splits,
            'role_rows':{k:len(v) for k,v in roles.items()},'pair_rows':{k:len(v) for k,v in pairs.items()},
            'excluded_unmapped_roles':excluded,'excluded_audit_overlaps':excluded_overlap,'trials':trials,
            'train_only_prefix_augmentation':original_train_counts,
            'confidence_gates':gates,'gate_policy':'Development-only class precision >= .80, minimum 5 selected examples; otherwise abstain. Not calibrated probabilities or a production precision guarantee.',
            'artifact_sha256':hashlib.sha256(artifact.read_bytes()).hexdigest(),
            'protected_sha256':{name:hashlib.sha256((ROOT/'data'/name).read_bytes()).hexdigest() for name in ('argument_quality_audit.json','argument_repair_holdout.json')}}
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Saved',artifact,flush=True)


if __name__=='__main__':main()
