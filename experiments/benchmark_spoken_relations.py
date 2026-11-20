"""Causal link benchmark from publicly documented AIFdb Moral Maze maps."""
import argparse
from collections import Counter, defaultdict
import json

from evaluate_dialogue_relations import ROOT, TransformerPairs
from argument_models import vector, words
from moderation_session import load_resources

CORPUS = ROOT / 'data/raw/moral_maze'
DEVELOPMENT = {'britishempire', 'Money', 'MM2019DDay', 'bankingsystem'}
RELATION = {'RA': 'support', 'CA': 'attack'}
SPEECH_ACTS = {'asserting', 'arguing', 'disagreeing', 'agreeing', 'restating',
               'popular conceding', 'default illocuting', 'pure questioning',
               'assertive questioning', 'rhetorical questioning', 'assertive challenging'}


def extract(graph):
    """Map proposition edges to locutions and use positions from the locution sequence."""
    nodes = {str(node['nodeID']): node for node in graph['nodes']}
    incoming, outgoing = defaultdict(set), defaultdict(set)
    for edge in graph['edges']:
        source, target = str(edge['fromID']), str(edge['toID'])
        outgoing[source].add(target)
        incoming[target].add(source)
    locutions = {}
    for item in graph.get('locutions', []):
        key = str(item['nodeID'])
        if key in nodes and nodes[key]['type'] == 'L':
            locutions.setdefault(key, item)
    if len(locutions) < 2:
        return [], [], Counter()
    times = [item.get('start') or item.get('timestamp') for item in locutions.values()]
    # Tied old insertion timestamps are common. Keep the published locution-array
    # order in these cases and disclose that chronology is approximate.
    chronological = all(times) and len(set(times)) == len(times)
    order = list(locutions)
    if chronological:
        order.sort(key=lambda key: locutions[key].get('start') or locutions[key]['timestamp'])
    pos = {key: number for number, key in enumerate(order)}
    anchors = defaultdict(set)
    for key, node in nodes.items():
        if node['type'] != 'YA' or node['text'].lower() not in SPEECH_ACTS:
            continue
        for target in outgoing[key]:
            if nodes.get(target, {}).get('type') == 'I':
                anchors[target].update(incoming[key] & locutions.keys())
    propositions = {key: next(iter(values)) for key, values in anchors.items() if len(values) == 1}
    eligible = set(propositions.values())
    turns = [{'key': key, 'number': pos[key]+1, 'text': nodes[key]['text'].partition(': ')[2] or nodes[key]['text'],
              'speaker':locutions[key].get('personID')} for key in order if key in eligible]
    counts = Counter(chronological_maps=int(bool(chronological)), approximate_order_maps=int(not chronological))
    edges = set()
    for key, node in nodes.items():
        if node['type'] not in RELATION:
            continue
        for a in incoming[key]:
            for b in outgoing[key]:
                if a not in propositions or b not in propositions:
                    counts['ungrounded'] += 1
                    continue
                source, target = propositions[a], propositions[b]
                if source == target:
                    counts['within_locution'] += 1
                    continue
                if pos[source] < pos[target]:
                    counts['future_target'] += 1
                    continue
                edges.add((pos[source]+1, pos[target]+1, RELATION[node['type']]))
    return turns, sorted(edges), counts


def make_cache(output, *, reretrieve=False, prior_cache=None, corpus=CORPUS):
    if output.exists():
        return
    manifest = json.loads((corpus/'manifest.json').read_text())
    encoder = load_resources()[2]
    model = TransformerPairs()
    groups, exclusions = [], Counter()
    from relation_context import retrieval_score
    for episode, ident, _, digest in manifest['maps']:
        import hashlib
        raw = (corpus/f'{ident}.json').read_bytes()
        assert hashlib.sha256(raw).hexdigest()==digest
        turns, edges, counts = extract(json.loads(raw))
        exclusions.update(counts)
        gold = defaultdict(list)
        for source, target, label in edges:
            gold[source].append([target,label])
        for i, turn in enumerate(turns):
            if not i:
                continue
            src = vector(encoder,turn['text'])
            retrieved = [{**t,'similarity':float(src@vector(encoder,t['text']))} for t in turns[:i]]
            source_words=words(turn['text'])
            def order(row):
                overlap=len(source_words&words(row['text']))/max(1,len(source_words))
                if reretrieve:
                    return (retrieval_score(row['similarity'],turn['number']-row['number'],overlap),row['number'])
                return (row['similarity'],row['number'])
            retrieved.sort(key=order,reverse=True)
            retrieved = retrieved[:6]
            group = {'episode':episode,'map':ident,'turn':turn,'gold':gold[turn['number']],
                     'targets':retrieved,'split':'development' if episode in DEVELOPMENT else 'test'}
            groups.append(group)
    from relation_context import strip_speech_act
    unique = {}
    existing={}
    if prior_cache:
        for g in json.loads(prior_cache.read_text())['groups']:
            source=g['turn']['text']
            for target in g['targets']:
                existing[(source,target['text'])]=target['raw']
                existing[(strip_speech_act(source),strip_speech_act(target['text']))]=target['clean']
    for g in groups:
        source = g['turn']['text']
        for target in g['targets']:
            pair=(source,target['text'])
            clean=(strip_speech_act(source),strip_speech_act(target['text']))
            unique[pair]=existing.get(pair)
            unique[clean]=existing.get(clean)
    pairs=[key for key,value in unique.items() if value is None]
    for at in range(0,len(pairs),12):
        batch=pairs[at:at+12]
        unique.update(zip(batch,model.score(batch)))
        if at%480==0: print('scored',at+len(batch),'/',len(pairs),flush=True)
    for g in groups:
        src = g['turn']['text']
        for target in g['targets']:
            target['raw']=unique[(src,target['text'])]
            target['clean']=unique[(strip_speech_act(src),strip_speech_act(target['text']))]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({'groups':groups,'exclusions':dict(exclusions)},ensure_ascii=False)+'\n')
    print('cached',len(groups),'groups',exclusions,flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    from pathlib import Path
    parser.add_argument('output',type=Path)
    parser.add_argument('--prior-cache',type=Path)
    parser.add_argument('--corpus',type=Path,default=CORPUS)
    parser.add_argument('--context-retrieval',action='store_true')
    args=parser.parse_args()
    make_cache(args.output,reretrieve=args.context_retrieval,prior_cache=args.prior_cache,corpus=args.corpus)
