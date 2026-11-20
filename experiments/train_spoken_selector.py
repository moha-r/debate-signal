"""Fit relation selection on radio development episodes with episode-held-out calibration."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path

from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression

from evaluate_dialogue_relations import ROOT
from argument_models import words
from relation_context import has_reply_cue


def features(turn, target):
    scores=target['raw']
    a,b=words(turn['text']),words(target['text'])
    shared=len(a&b)
    distance=turn['number']-target['number']
    same=turn.get('speaker') is not None and turn.get('speaker')==target.get('speaker')
    return [scores['support'],scores['attack'],scores['none'],scores['rephrase'],target['similarity'],
            math.log1p(distance),float(distance==1),float(same),
            shared/max(1,len(a)),shared/max(1,len(b)),shared/max(1,len(a|b)),
            math.log1p(len(a)),math.log1p(len(b)),float(has_reply_cue(turn['text']))]


def fit(model, groups):
    X,y=[],[]
    for group in groups:
        gold=dict(group['gold'])
        for target in group['targets']:
            X.append(features(group['turn'],target))
            y.append(gold.get(target['number'],'none'))
    model.fit(X,y)
    return model


def score(model, groups):
    results=[]
    for group in groups:
        raw=model.predict_proba([features(group['turn'],t) for t in group['targets']])
        ranked=[]
        for target, values in zip(group['targets'],raw):
            scores=dict(zip(model.classes_,values))
            label=max(('support','attack'),key=scores.get)
            ranked.append((float(scores[label]),target['number'],label))
        ranked.sort(reverse=True)
        results.append((group,ranked))
    return results


def evaluate(scored, minimum, margin):
    totals=Counter()
    for group,ranked in scored:
        totals['turns']+=1
        gold={tuple(edge) for edge in group['gold']}
        totals['reference']+=bool(gold)
        if ranked[0][0]<minimum or len(ranked)>1 and ranked[0][0]-ranked[1][0]<margin:
            continue
        _,target,label=ranked[0]
        totals['predicted']+=1
        totals['correct']+=(target,label) in gold
        totals['target_correct']+=any(number==target for number,_ in gold)
        totals['spurious']+=not gold
    p,r,c=totals['predicted'],totals['reference'],totals['correct']
    return {**totals,'precision':c/max(1,p),'recall':c/max(1,r),'f1':2*c/max(1,p+r)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cache',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    groups=json.loads(args.cache.read_text())['groups']
    dev=[g for g in groups if g['split']=='development']
    test=[g for g in groups if g['split']=='test']
    episodes=sorted({g['episode'] for g in dev})
    factories={**{f'logistic-{c}':lambda c=c:LogisticRegression(C=c,class_weight='balanced',max_iter=300) for c in (.1,1,10)},
               **{f'boost-{depth}':lambda depth=depth:HistGradientBoostingClassifier(max_depth=depth,max_iter=80,
                   l2_regularization=4,class_weight='balanced',random_state=42) for depth in (2,3)}}
    trials=[]
    for key, factory in factories.items():
        crossfold=[]
        for episode in episodes:
            model=fit(factory(),[g for g in dev if g['episode']!=episode])
            crossfold.extend(score(model,[g for g in dev if g['episode']==episode]))
        for threshold in (.30,.40,.50,.60,.70,.80,.90):
            for margin in (0.,.03,.08,.12):
                trials.append({'model':key,'threshold':threshold,'margin':margin,**evaluate(crossfold,threshold,margin)})
    selected=max(trials,key=lambda row:(row['f1'],row['precision']))
    trained=fit(factories[selected['model']](),dev)
    result={'selected_on_development':selected,'test':evaluate(score(trained,test),selected['threshold'],selected['margin']),
            'scope':'Local academic experiment. Whole 4 development episodes, calibration leave-one-episode-out, evaluated once on 4 other episodes.',
            'trials':trials}
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='trials'},indent=2))


if __name__=='__main__':
    main()
