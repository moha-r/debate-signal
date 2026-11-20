"""Small NumPy helpers for bounded padding and transparent binary metrics."""

import numpy as np
from sklearn.metrics import accuracy_score, brier_score_loss, confusion_matrix, precision_recall_fscore_support


def length_bucket_order(lengths, batch_size, seed):
    """Shuffle complete examples, group similar lengths, then shuffle complete batches."""
    lengths = np.asarray(lengths)
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(lengths))
    block_size = batch_size * 128
    for first in range(0,len(order),block_size):
        block = order[first:first+block_size]
        order[first:first+block_size] = block[np.argsort(lengths[block],kind="stable")]
    full_count = len(order) // batch_size * batch_size
    full = order[:full_count].reshape(-1,batch_size)
    full = full[rng.permutation(len(full))].reshape(-1)
    return np.concatenate([full,order[full_count:]])


def batch_arrays(input_ids, attention_mask, labels, indices):
    indices = np.asarray(indices, dtype=int)
    mask = attention_mask[indices]
    longest = max(1, int(mask.sum(axis=1).max()))
    width = min(input_ids.shape[1], max(32, ((longest + 31) // 32) * 32))
    return {
        "input_ids": input_ids[indices, :width].astype(np.int64),
        "attention_mask": mask[:, :width].astype(np.int64),
        "labels": labels[indices].astype(np.int64),
    }


def binary_scores(labels, probabilities, threshold=.5):
    actual = np.asarray(labels, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)
    predicted = probabilities >= threshold
    tn, fp, fn, tp = map(int, confusion_matrix(actual, predicted, labels=[0,1]).ravel())
    result = {
        "n": len(actual), "threshold": float(threshold), "accuracy": float(accuracy_score(actual, predicted)),
        "attack_precision": tp / max(1, tp+fp), "attack_recall": tp / max(1, tp+fn),
        "tn": tn, "fp": fp, "fn": fn, "tp": tp,
        "brier": float(brier_score_loss(actual, probabilities)),
    }
    for average in ("macro", "weighted"):
        precision, recall, f1, _ = precision_recall_fscore_support(actual, predicted, labels=[0,1], average=average, zero_division=0)
        result.update({f"{average}_precision": float(precision), f"{average}_recall": float(recall), f"{average}_f1": float(f1)})
    return result
