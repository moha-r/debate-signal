"""Pinned dialogue relation cross-encoder with bounded, local CPU inference."""
from functools import lru_cache
import json
import logging
import os
from pathlib import Path
from threading import RLock

MODEL_ID = 'raruidol/ArgumentMining-EN-ARI-AIF-RoBERTa_L'
MODEL_REVISION = '7e7747dcc124d85e704edb11355fae452edada9c'
MAX_CANDIDATES = 6
MAX_TOKENS = 256
POLICY_PATH = Path(__file__).resolve().parent / 'artifacts/dialogue_relation_policy.json'
_inference_lock = RLock()


def validate_labels(labels):
    expected = {0: 'No-Relation', 1: 'Inference', 2: 'Conflict', 3: 'Rephrase'}
    if labels != expected:
        raise ValueError('The dialogue relation checkpoint has an unexpected label mapping.')


def map_probabilities(values):
    return {
        'support': float(values[1]),
        'attack': float(values[2]),
        'none': float(values[0] + values[3]),
        'rephrase': float(values[3]),
    }


class DialogueCrossEncoder:
    def __init__(self, path):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.torch = torch
        # Limit oversubscription when the small encoder and web service share a CPU.
        torch.set_num_threads(2)
        self.tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)
        self.model = AutoModelForSequenceClassification.from_pretrained(
            path, local_files_only=True, dtype=torch.float32,
        ).to('cpu').eval()
        validate_labels(self.model.config.id2label)
        # Finish lazy weight loading before the first recorded contribution arrives.
        self.score([('The proposal could reduce costs.', 'We should consider the proposal.')])

    def score(self, pairs):
        if not pairs:
            return []
        with _inference_lock:
            inputs = self.tokenizer(
                [source for source, _ in pairs], [target for _, target in pairs],
                padding=True, truncation=True, max_length=MAX_TOKENS, return_tensors='pt',
            )
            with self.torch.inference_mode():
                values = self.model(**inputs).logits.float().softmax(-1).numpy()
            return [map_probabilities(value) for value in values]


@lru_cache(maxsize=1)
def load_cross_encoder():
    from huggingface_hub import snapshot_download
    from huggingface_hub.errors import LocalEntryNotFoundError

    requested = os.getenv('ARGUMENT_RELATION_BACKEND', 'auto')
    if requested not in ('auto', 'transformer', 'local'):
        raise ValueError('ARGUMENT_RELATION_BACKEND must be auto, transformer or local.')
    if requested == 'local':
        return None
    try:
        path = snapshot_download(
            MODEL_ID, revision=MODEL_REVISION, local_files_only=True,
            allow_patterns=['config.json', 'tokenizer.json', 'tokenizer_config.json', 'pytorch_model.bin'],
        )
    except LocalEntryNotFoundError:
        if requested == 'transformer':
            raise RuntimeError('Prepare the pinned dialogue checkpoint with prepare_dialogue_relation_model.py.') from None
        logging.getLogger(__name__).warning('Dialogue checkpoint is unavailable. Using the local logistic relation model.')
        return None
    with _inference_lock:
        return DialogueCrossEncoder(path)


def relation_backend():
    # Serialize first load as well as inference to prevent duplicate model allocation.
    with _inference_lock:
        model = load_cross_encoder()
    if model is None:
        return {'backend': 'local-logistic'}
    policy = json.loads(POLICY_PATH.read_text())
    metadata = {
        'backend': 'dialogue-roberta', 'model': MODEL_ID, 'revision': MODEL_REVISION,
        'device': 'cpu', 'max_candidates': MAX_CANDIDATES, 'max_tokens': MAX_TOKENS,
        'threshold': policy['threshold'], 'margin': policy['margin'],
        'license': 'CC BY-NC-SA 4.0',
    }
    from argument_link_selector import load_link_selector
    selector = load_link_selector()
    if selector is not None:
        metadata['link_selector'] = {key: selector[key] for key in ('version', 'threshold', 'margin')}
    return metadata


def score_candidates(model, text, candidates):
    chosen = candidates[:MAX_CANDIDATES]
    from relation_context import is_explicit_agreement, strip_speech_act
    if is_explicit_agreement(text):
        pairs = [(strip_speech_act(text), strip_speech_act(target['text'])) for target in chosen]
    else:
        pairs = [(text, target['text']) for target in chosen]
    scores = model.score(pairs)
    withheld = [{'support': 0., 'attack': 0., 'none': 1.} for _ in candidates[len(chosen):]]
    return scores + withheld
