"""Fit the directed relation selector on whole Part 2 training documents."""
import hashlib
import json
import math
import xml.etree.ElementTree as ET

import joblib
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression

from evaluate_dialogue_relations import ROOT, MODEL, REVISION, TransformerPairs
from argument_models import vector, words
from evaluate_argument_quality import corpus_units
from moderation_session import load_resources

OUT = ROOT / 'results/relation_ranker'


def pair_features(source, target, probability, similarity, distance):
    shared = len(source & target)
    return [
        probability['support'], probability['attack'], probability['none'],
        probability.get('rephrase', 0.0), similarity,
        shared / max(1, len(source)), shared / max(1, len(target)),
        shared / max(1, len(source | target)), math.log1p(distance),
        float(distance == 1), math.log1p(len(source)), math.log1p(len(target)),
    ]


def samples():
    manifest = json.loads((ROOT/'results/argument_repair/training/manifest.json').read_text())
    encoder = load_resources()[2]
    from nlp_pipeline import preprocess_text
    protected = {preprocess_text(turn['text'])
                 for name in ('argument_quality_audit.json', 'argument_repair_holdout.json', 'dialogue_quality_challenge_v3.json')
                 for case in json.loads((ROOT/'data'/name).read_text())['cases'] for turn in case['turns']}
    results = []
    for doc, split in manifest['document_splits'].items():
        path = ROOT/'data/raw/arg-microtexts-part2'/f'{doc}.xml'
        _, units = corpus_units(path)
        xml = ET.parse(path).getroot()
        implicit = {node.get('id') for node in xml.findall('edu') if node.get('implicit') == 'true'}
        excluded = {e.get('trg') for e in xml.findall('edge') if e.get('type') == 'seg' and e.get('src') in implicit}
        excluded |= {n.get('id') for n in xml.findall('adu') if n.get('implicit') == 'true'}
        units = [u for u in units if u['id'] not in excluded and preprocess_text(u['text']) not in protected]
        for i, unit in enumerate(units):
            edges = unit['outgoing']
            if len(edges) > 1 or any(e['type'] not in ('sup','exa','reb') for e in edges):
                continue
            label = {'sup':'support','exa':'support','reb':'attack'}
            gold = {e['trg']:label[e['type']] for e in edges}
            group = []
            for j, target in enumerate(units[:i]):
                sim = float(vector(encoder,unit['text']) @ vector(encoder,target['text']))
                group.append({'group':f"{doc}:{unit['id']}",'split':split,'source':unit['text'],
                              'target':target['text'],'distance':i-j,'similarity':sim,
                              'label':gold.get(target['id'],'none')})
            group.sort(key=lambda row:(row['similarity'],-row['distance']),reverse=True)
            results.extend(group[:6])
    return results


def score_groups(rows, scores, threshold, margin, *, baseline=False):
    groups = {}
    for row, probabilities in zip(rows, scores):
        groups.setdefault(row['group'], []).append((row, probabilities))
    predicted = correct = reference = wrong_target = false_links = 0
    for candidates in groups.values():
        has_link = any(row['label'] != 'none' for row,_ in candidates)
        reference += has_link
        ranked = []
        for row, prob in candidates:
            label = max(('support','attack'), key=prob.get)
            confidence = prob[label]
            if row['similarity'] < .20 or confidence < threshold or confidence <= prob['none']:
                continue
            rank = confidence
            if baseline:
                rank = .7*confidence + .25*row['similarity'] + .05*math.exp(-row['distance']/8)
            ranked.append((rank, label, row))
        ranked.sort(key=lambda p:(p[0],-p[2]['distance']), reverse=True)
        if not ranked or len(ranked)>1 and ranked[0][0]-ranked[1][0]<margin:
            continue
        _, label, row = ranked[0]
        predicted += 1
        correct += row['label'] == label
        wrong_target += has_link and row['label'] == 'none'
        false_links += not has_link
    return {'predicted':predicted,'correct':correct,'reference':reference,'wrong_target':wrong_target,
            'spurious':false_links,'precision':correct/max(1,predicted),'recall':correct/max(1,reference),
            'f1':2*correct/max(1,predicted+reference)}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cache = OUT/'causal_features.json'
    if cache.exists():
        rows = json.loads(cache.read_text())
    else:
        rows = samples()
        model = TransformerPairs()
        for start in range(0,len(rows),12):
            batch = rows[start:start+12]
            scores = model.score([(r['source'],r['target']) for r in batch])
            for row, probability in zip(batch,scores):
                row['scores'] = probability
                row['features'] = pair_features(words(row['source']),words(row['target']),probability,
                                                row['similarity'],row['distance'])
            if start % 240 == 0:
                print(f'Scored {start+len(batch)} / {len(rows)} pairs',flush=True)
        # Store only features, split membership, and the labels needed for replication.
        for row in rows:
            del row['source'], row['target']
        cache.write_text(json.dumps(rows)+'\n')
    data = {split:[r for r in rows if r['split']==split] for split in ('train','development','test')}
    train, dev, test = (data[k] for k in ('train','development','test'))
    X = [r['features'] for r in train]
    y = [r['label'] for r in train]
    models = {
        **{f'logistic-c{c}':LogisticRegression(C=c,class_weight='balanced',max_iter=500,random_state=42) for c in (.1,1,10)},
        **{f'boosting-depth{d}':HistGradientBoostingClassifier(max_depth=d,max_iter=100,l2_regularization=2,
                                                             class_weight='balanced',random_state=42) for d in (2,3)},
    }
    trials = []
    for name, model in models.items():
        model.fit(X,y)
        scores = predict(model,dev)
        for threshold in (.33,.40,.50,.60,.70,.80):
            for margin in (0.,.03,.07,.12):
                result = score_groups(dev,scores,threshold,margin)
                trials.append({'model':name,'threshold':threshold,'margin':margin,**result})
    best = max(trials,key=lambda row:(row['f1'],row['precision']))
    model = models[best['model']]
    result = {'source':'Arg-Microtexts Part 2, existing document-level train/development/test partitions, causal candidate sets',
              'checkpoint':MODEL,'revision':REVISION,'features_sha256':hashlib.sha256(cache.read_bytes()).hexdigest(),
              'pairs':{k:len(v) for k,v in data.items()},'selected':best,
              'test_baseline':score_groups(test,[r['scores'] for r in test],.50,.015,baseline=True),
              'test_ranker':score_groups(test,predict(model,test),best['threshold'],best['margin']),
              'trials':trials}
    candidate = OUT/'candidate.joblib'
    joblib.dump({'model':model,'threshold':best['threshold'],'margin':best['margin'],
                 'version':'dialogue-ranker-v1','checkpoint_revision':REVISION},candidate)
    result['candidate_sha256'] = hashlib.sha256(candidate.read_bytes()).hexdigest()
    (OUT/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('pairs','selected','test_baseline','test_ranker')},indent=2))


def predict(model, rows):
    return [dict(zip(model.classes_,map(float,value))) for value in model.predict_proba([r['features'] for r in rows])]


if __name__ == '__main__':
    main()
