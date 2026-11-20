"""Contextual verification of directed argument links proposed by the pair model."""

from functools import lru_cache
import math
from pathlib import Path

import joblib

from argument_models import words
from relation_context import has_reply_cue


SELECTOR_PATH = Path(__file__).resolve().parent / 'artifacts' / 'contextual_link_selector.joblib'
VERSION = 'contextual-link-selector-v1'
RELATIONS = ('support', 'attack')
PAIR_LABELS = (*RELATIONS, 'none', 'rephrase')


@lru_cache(maxsize=1)
def load_link_selector():
    return joblib.load(SELECTOR_PATH) if SELECTOR_PATH.is_file() else None


def contextual_features(turn, candidates):
    """Measure the pair alongside salient alternatives and the nearest candidate."""
    if not candidates:
        return []
    source_words = words(turn['text'])
    nearest = max(candidates, key=lambda target: target['number'])
    nearby_words = words(nearest['text'])
    nearby_overlap = len(source_words & nearby_words) / max(1, len(source_words | nearby_words))
    has_cue = has_reply_cue(turn['text'])
    rows = []
    for position, target in enumerate(candidates):
        scores = target['raw']
        target_words = words(target['text'])
        shared = len(source_words & target_words)
        distance = turn['number'] - target['number']
        speaker = turn.get('speaker')
        alternatives = [other for other in candidates if other is not target]
        max_similarity = max((other['similarity'] for other in alternatives), default=0.)
        score_gaps = [
            scores[label] - max((other['raw'][label] for other in alternatives), default=0.)
            for label in (*RELATIONS, 'none')
        ]
        rows.append([
            *(scores[label] for label in PAIR_LABELS),
            target['similarity'], math.log1p(distance), float(distance == 1),
            float(speaker is not None and speaker != 'Unknown' and speaker == target.get('speaker')),
            shared / max(1, len(source_words)), shared / max(1, len(target_words)),
            shared / max(1, len(source_words | target_words)),
            math.log1p(len(source_words)), math.log1p(len(target_words)), float(has_cue),
            position, float(target is nearest), len(candidates), target['similarity'] - max_similarity,
            *score_gaps, nearby_overlap,
        ])
    return rows


def rank_links(model, turn, candidates):
    if not candidates:
        return []
    rows = model.predict_proba(contextual_features(turn, candidates))
    positions = {label: list(model.classes_).index(label) for label in RELATIONS}
    return sorted((
        (float(scores[positions[label]]), target['number'], label)
        for target, scores in zip(candidates, rows)
        for label in RELATIONS
    ), reverse=True)


def choose_link(ranked, *, threshold, margin):
    if not ranked or ranked[0][0] < threshold:
        return None
    if len(ranked) > 1 and ranked[0][0] - ranked[1][0] < margin:
        return None
    return ranked[0]
