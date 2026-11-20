"""Train and inspect the English debate relationship selector on local radio data."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

import joblib
from sklearn.ensemble import ExtraTreesClassifier

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from argument_link_selector import VERSION, choose_link, contextual_features, rank_links
from evaluate_spoken_selector import context_rank, measure


def fit(groups):
    features, labels = [], []
    for group in groups:
        targets = group['targets']
        expected = dict(group['gold'])
        features.extend(contextual_features(group['turn'], targets))
        labels.extend(expected.get(target['number'], 'none') for target in targets)
    return ExtraTreesClassifier(
        n_estimators=120, max_depth=7, min_samples_leaf=6, class_weight='balanced',
        n_jobs=2, random_state=42,
    ).fit(features, labels)


def predictions(model, groups):
    return [(group, rank_links(model, group['turn'], group['targets'])) for group in groups]


def evaluate(ranked_groups, threshold, margin):
    totals = Counter(turns=0, targets=0, predicted=0, correct=0, target_correct=0, spurious=0)
    for group, ranked in ranked_groups:
        gold = {tuple(edge) for edge in group['gold']}
        totals['turns'] += 1
        totals['targets'] += bool(gold)
        choice = choose_link(ranked, threshold=threshold, margin=margin)
        if choice is None:
            continue
        _, number, label = choice
        totals['predicted'] += 1
        totals['correct'] += (number, label) in gold
        totals['target_correct'] += any(number == target for target, _ in gold)
        totals['spurious'] += not gold
    predicted, reference, correct = (totals[key] for key in ('predicted', 'targets', 'correct'))
    return {**totals, 'precision': correct / max(1, predicted), 'recall': correct / max(1, reference),
            'f1': 2 * correct / max(1, predicted + reference)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cache', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--artifact', type=Path, required=True)
    args = parser.parse_args()
    cache = args.cache.read_bytes()
    groups = json.loads(cache)['groups']
    development = [group for group in groups if group['split'] == 'development']
    test = [group for group in groups if group['split'] == 'test']
    episodes = sorted({group['episode'] for group in development})
    calibration = []
    for episode in episodes:
        left_out = [group for group in development if group['episode'] == episode]
        fitted = fit([group for group in development if group['episode'] != episode])
        calibration.extend(predictions(fitted, left_out))
    trials = [
        {'threshold': threshold, 'margin': margin, **evaluate(calibration, threshold, margin)}
        for threshold in (round(.28 + i * .035, 3) for i in range(18))
        for margin in (.0, .03, .08, .14)
    ]
    selected = max(trials, key=lambda row: (row['f1'], row['precision'], row['margin']))
    model = fit(development)
    model.n_jobs = 1  # A live request scores at most six candidates.
    bundle = {'version': VERSION, 'model': model, 'threshold': selected['threshold'],
              'margin': selected['margin'], 'training_episodes': episodes}
    joblib.dump(bundle, args.artifact, compress=3)
    report = {
        'scope': 'Causal support/attack link selection with pre-grounded broadcast turns and fixed retrieval. '
                 'Development threshold fitted by episode. Test episodes were reused during model exploration.',
        'input_sha256': hashlib.sha256(cache).hexdigest(),
        'artifact_sha256': hashlib.sha256(args.artifact.read_bytes()).hexdigest(),
        'development_episodes': episodes,
        'test_episodes': sorted({group['episode'] for group in test}),
        'selected_on_development': selected,
        'test_before': measure(test, context_rank),
        'test_after': evaluate(predictions(model, test), selected['threshold'], selected['margin']),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
