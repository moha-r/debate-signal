"""Evaluate fixed model candidates; this does not change the serving model or fit anything."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from time import perf_counter

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
MODEL='raruidol/ArgumentMining-EN-ARI-AIF-RoBERTa_L'
REVISION='7e7747dcc124d85e704edb11355fae452edada9c'


class TransformerPairs:
    def __init__(self):
        import torch
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        from huggingface_hub import snapshot_download

        path=snapshot_download(MODEL,revision=REVISION,local_files_only=True,
                               allow_patterns=['config.json','tokenizer.json','tokenizer_config.json','pytorch_model.bin'])
        self.device='mps' if torch.backends.mps.is_available() else 'cpu'
        self.torch=torch
        self.tokenizer=AutoTokenizer.from_pretrained(path,local_files_only=True)
        dtype=torch.float16 if self.device=='mps' else torch.float32
        self.model=AutoModelForSequenceClassification.from_pretrained(path,local_files_only=True,dtype=dtype).to(self.device).eval()
        if self.model.config.id2label!={0:'No-Relation',1:'Inference',2:'Conflict',3:'Rephrase'}:
            raise ValueError('Unexpected relation checkpoint label mapping')

    def score(self,pairs):
        inputs=self.tokenizer([source for source,_ in pairs],[target for _,target in pairs],
                              padding=True,truncation=True,max_length=256,return_tensors='pt').to(self.device)
        with self.torch.inference_mode():
            values=self.model(**inputs).logits.float().softmax(-1).cpu().numpy()
        return [{'support':float(v[1]),'attack':float(v[2]),'none':float(v[0]+v[3]),'rephrase':float(v[3])} for v in values]


def metrics(rows,predictions):
    from sklearn.metrics import classification_report,confusion_matrix,accuracy_score,f1_score
    labels=['support','attack','none'];y=[r['label'] for r in rows]
    return {'n':len(y),'accuracy':float(accuracy_score(y,predictions)),
            'macro_f1':float(f1_score(y,predictions,labels=labels,average='macro',zero_division=0)),
            'classes':classification_report(y,predictions,labels=labels,output_dict=True,zero_division=0),
            'confusion_labels':labels,'confusion':confusion_matrix(y,predictions,labels=labels).tolist()}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--model',choices=['local','transformer'],required=True)
    parser.add_argument('--dialogue',action='store_true',help='Also replay both project regressions with the fixed transformer selection policy.')
    args=parser.parse_args()
    fixture=ROOT/'data/marg_relation_diagnostic.json';data=json.loads(fixture.read_text())
    out=ROOT/'results/dialogue_followup'/args.model
    if (out/'summary.json').exists():raise SystemExit('Preserve this completed diagnostic; use a new candidate version.')
    out.mkdir(parents=True,exist_ok=True)
    unique={r['id']:r for rows in data['sets'].values() for r in rows}
    allrows=list(unique.values());scores={};timings=[]
    started=perf_counter()
    if args.model=='local':
        from argument_models import load_models,pair_matrix
        from moderation_session import load_resources
        encoder=load_resources()[2];bundle=load_models()
        matrix=pair_matrix([{'text':r['later'],'target':r['earlier'],'distance':1} for r in allrows],encoder,bundle['relation_word'])
        values=bundle['relation_model'].predict_proba(matrix)
        for r,value in zip(allrows,values):scores[r['id']]=dict(zip(bundle['relation_model'].classes_,map(float,value)))
        provenance={'model':'local-part2-logistic-v2','scope':'Raw directed source=later, target=earlier classifier, no serving gates. Distance set to 1 for pair diagnostic; no model fitting.'}
    else:
        transformer=TransformerPairs()
        # Use one predeclared ordering; do not pick whichever direction scores best on test labels.
        for at in range(0,len(allrows),4):
            batch=allrows[at:at+4]
            tick=perf_counter()
            values=transformer.score([(r['later'],r['earlier']) for r in batch])
            timings.append((perf_counter()-tick)*1000)
            for r,v in zip(batch,values):scores[r['id']]=v
            if at%80==0:print('scored',at+len(batch),'/',len(allrows),flush=True)
        provenance={'model':MODEL,'revision':REVISION,'device':transformer.device,'license':'CC BY-NC-SA 4.0','ordering':'later source, earlier target; pair diagnostic does not validate direction','max_tokens':256,'batch':4,'mapping':'Inference->support; Conflict->attack; No-Relation and Rephrase->none. Rephrase is not proof of argumentative support.'}
    summary={'scope':data['scope'],'fixture_sha256':hashlib.sha256(fixture.read_bytes()).hexdigest(),
             'provenance':provenance,'total_wall_seconds':perf_counter()-started,'inference_batch_ms':timings,'sets':{}}
    for key,rows in data['sets'].items():
        predictions=[max(('support','attack','none'),key=lambda k:scores[r['id']][k]) for r in rows]
        summary['sets'][key]=metrics(rows,predictions)
    if args.dialogue and args.model=='transformer':
        summary['dialogue_regressions']=dialogue_regressions(transformer)
    (out/'scores.json').write_text(json.dumps(scores,indent=2)+'\n')
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:{m:v[m] for m in ('n','accuracy','macro_f1')} for k,v in summary['sets'].items()}),flush=True)


def dialogue_regressions(transformer):
    from unittest.mock import patch
    import argument_models
    from evaluate_argument_quality import dialogue_audit
    from moderation_session import load_resources

    resources=load_resources()
    original=argument_models.load_models()
    artifact={**original,'confidence_gates':{**original['confidence_gates'],'relation':{'support':.5,'attack':.5}}}
    turn_timings=[]

    def score(text,candidates,number,encoder):
        tick=perf_counter()
        results=transformer.score([(text,target['text']) for target in candidates[:6]])
        turn_timings.append((perf_counter()-tick)*1000)
        return results+[{'support':0.,'attack':0.,'none':1.}]*(len(candidates)-len(results))

    measurements={}
    with patch('argument_models.load_models',return_value=artifact),patch('argument_models.relation_scores',side_effect=score):
        for fixture in ('argument_quality_audit.json','argument_repair_holdout.json'):
            data=json.loads((ROOT/'data'/fixture).read_text())
            result,_=dialogue_audit(data['cases'],resources)
            measurements[fixture]=result
            print('dialogue',fixture,json.dumps(result['links']),flush=True)
    return {'scope':'Inspected authored regressions. Fixed 0.5 support/attack gate, top 6 candidates, existing role and target ranking policy. Scores reflect experimentation on MPS, not a CPU deployment benchmark.',
            'results':measurements,'turn_relation_ms':turn_timings}


if __name__=='__main__':main()
