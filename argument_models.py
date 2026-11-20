"""Local learned role/relation scores on frozen MiniLM features; no remote inference."""
from functools import lru_cache
from pathlib import Path
import hashlib

import joblib
import numpy as np
from scipy.sparse import csr_matrix, hstack
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

ARTIFACT=Path(__file__).resolve().parent/'artifacts/argument_models_v2.joblib'
STOP=set(ENGLISH_STOP_WORDS)|{'claim','claims','evidence','source','sources','question','according','example','supports','support','expected','would','could','should','also','please','provide','show','say','said'}


def words(text):
    from nlp_pipeline import tokenize, stem_word
    return {stem_word(t) for t in tokenize(text) if t not in STOP and len(t)>2}


@lru_cache(maxsize=8192)
def vector(encoder,text):
    value=np.asarray(encoder.encode(text,normalize_embeddings=True),dtype=np.float32)
    value.setflags(write=False)
    return value


def role_numeric(rows,encoder):
    result=[]
    for row in rows:
        current=vector(encoder,row['text'])
        context=vector(encoder,row['context']) if row.get('context') else np.zeros_like(current)
        result.append(np.concatenate([current,context,current-context,current*context,
            [min(len(row['text'].split())/50,1),float(bool(row.get('context'))),float(current@context)]]))
    return csr_matrix(np.asarray(result,dtype=np.float32))


def pair_numeric(rows,encoder):
    result=[]
    for row in rows:
        source,target=vector(encoder,row['text']),vector(encoder,row['target'])
        a,b=words(row['text']),words(row['target'])
        result.append(np.concatenate([source,target,source-target,source*target,
            [float(source@target),len(a&b)/max(1,len(a|b)),min(abs(row.get('distance',1))/12,1)]]))
    return csr_matrix(np.asarray(result,dtype=np.float32))


def role_matrix(rows,encoder,word,char):
    texts=[r['text'] for r in rows]
    return hstack([word.transform(texts),char.transform(texts)*.6,role_numeric(rows,encoder)],format='csr')


def pair_matrix(rows,encoder,word):
    return hstack([word.transform([r['text'] for r in rows])*.4,
                   word.transform([r['target'] for r in rows])*.4,pair_numeric(rows,encoder)],format='csr')


@lru_cache(maxsize=1)
def load_models():
    return joblib.load(ARTIFACT) if ARTIFACT.exists() else None


def available(encoder):
    bundle=load_models()
    return bundle if bundle and len(vector(encoder,'A short discussion.'))==bundle['dimension'] else None


@lru_cache(maxsize=1)
def artifact_sha256():
    return hashlib.sha256(ARTIFACT.read_bytes()).hexdigest() if ARTIFACT.exists() else None


def role_scores(text,previous,encoder):
    bundle=available(encoder)
    if not bundle: return None
    row={'text':text,'context':' '.join(t['text'] for t in previous[-2:])}
    probabilities=bundle['role_model'].predict_proba(role_matrix([row],encoder,bundle['role_word'],bundle['role_char']))[0]
    return dict(zip(bundle['role_model'].classes_,map(float,probabilities)))


def relation_scores(text,candidates,number,encoder):
    bundle=available(encoder)
    if not bundle or not candidates: return None
    from dialogue_relations import load_cross_encoder, relation_backend, score_candidates
    backend=relation_backend()
    if backend['backend']=='dialogue-roberta':
        return score_candidates(load_cross_encoder(),text,candidates)
    rows=[{'text':text,'target':t['text'],'distance':number-t['number']} for t in candidates]
    probs=bundle['relation_model'].predict_proba(pair_matrix(rows,encoder,bundle['relation_word']))
    return [dict(zip(bundle['relation_model'].classes_,map(float,row))) for row in probs]
