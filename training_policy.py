"""Validation-only operating-point selection shared by training and evaluation."""

import numpy as np
from sklearn.metrics import f1_score


def select_alert_threshold(labels, probabilities, target_precision=.8, minimum_alerts=10):
    labels = np.asarray(labels, dtype=int)
    scores = np.asarray(probabilities, dtype=float)
    if labels.ndim != 1 or scores.shape != labels.shape or not len(labels):
        raise ValueError("Labels and probabilities must have matching nonempty one-dimensional shapes")
    if not np.isin(labels, [0, 1]).all() or not labels.sum():
        raise ValueError("Binary references including positive examples are required")
    if not np.isfinite(scores).all() or ((scores < 0) | (scores > 1)).any():
        raise ValueError("Probabilities must be finite and between zero and one")
    if not 0 < target_precision <= 1 or minimum_alerts < 1:
        raise ValueError("Invalid precision target or minimum alert count")
    candidates = []
    for threshold in np.arange(1, 100) / 100:
        predicted = scores >= threshold
        alerts = int(predicted.sum())
        if alerts < minimum_alerts:
            continue
        tp = int((predicted & (labels == 1)).sum())
        candidates.append({
            "threshold": float(threshold), "precision": tp / alerts,
            "recall": tp / int(labels.sum()), "alerts": alerts,
            "macro_f1": float(f1_score(labels, predicted, average="macro", zero_division=0)),
        })
    if not candidates:
        raise ValueError("No validation threshold has the required number of alerts")
    eligible = [c for c in candidates if c["precision"] >= target_precision]
    if eligible:
        best = max(eligible, key=lambda c: (c["recall"], c["precision"], c["threshold"]))
    else:
        best = max(candidates, key=lambda c: (c["macro_f1"], c["precision"], c["threshold"]))
    return {**best, "precision_target_met": bool(eligible), "target_precision": target_precision,
            "minimum_alerts": minimum_alerts, "selection_data": "training-only validation"}
