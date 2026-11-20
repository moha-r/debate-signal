"""Select a topic-monitor rule on development sessions and evaluate reserved topics."""

import json
from importlib.metadata import version
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

from topic_relevance import MODEL_ID, MODEL_REVISION, TopicMonitor


DATA_PATH = Path("data/topic_dialogues.json")
OUTPUT = Path("results")


class EmbeddingCache:
    """Reuse deterministic embeddings while comparing development thresholds."""

    def __init__(self):
        self.model = SentenceTransformer(MODEL_ID, revision=MODEL_REVISION, device="cpu")
        self.vectors = {}

    def encode(self, text, normalize_embeddings=True):
        if text not in self.vectors:
            self.vectors[text] = self.model.encode(text, normalize_embeddings=normalize_embeddings)
        return self.vectors[text]


def score_sessions(sessions, threshold, backend, use_context, encoder):
    rows, events = [], []
    for session in sessions:
        monitor = TopicMonitor(session["topic"], threshold, backend, use_context, encoder)
        episode = 0
        pending = []
        for turn, (speaker, text, reference) in enumerate(session["turns"], 1):
            if reference == "off_topic":
                if not pending:
                    episode += 1
                pending.append(turn)
            elif reference == "on_topic":
                if len(pending) >= 2:
                    events.append((session["id"], episode, pending[0], pending[-1]))
                pending = []
            result = monitor.process(text)
            rows.append({
                "session": session["id"], "split": session["split"], "turn": turn,
                "speaker": speaker, "text": text, "reference": reference,
                "episode": episode if reference == "off_topic" else None,
                **result,
            })
        if len(pending) >= 2:
            events.append((session["id"], episode, pending[0], pending[-1]))
    return pd.DataFrame(rows), events


def event_metrics(rows, events):
    predicted = rows[rows["alert"]]
    detected = set()
    delays = []
    false_alerts = 0
    for row in predicted.itertuples():
        matches = [
            event for event in events
            if event[0] == row.session and event[2] <= row.turn <= event[3]
        ]
        if not matches or matches[0][:2] in detected:
            false_alerts += 1
        else:
            event = matches[0]
            detected.add(event[:2])
            delays.append(row.turn - event[2])
    precision = len(detected) / len(predicted) if len(predicted) else 0.0
    recall = len(detected) / len(events) if events else 0.0
    return {
        "event_precision": precision,
        "event_recall": recall,
        "event_f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "false_alerts": false_alerts,
        "events": len(events),
        "detected": len(detected),
        "median_delay_turns": float(np.median(delays)) if delays else None,
        "false_alerts_per_session": false_alerts / rows["session"].nunique(),
    }


def main():
    data = json.loads(DATA_PATH.read_text())
    sessions = data["sessions"]
    development = [s for s in sessions if s["split"] == "development"]
    test = [s for s in sessions if s["split"] == "test"]
    assert {s["topic"] for s in development}.isdisjoint(s["topic"] for s in test)
    assert len({s["id"] for s in sessions}) == len(sessions)
    print(f'{len(sessions)} authored sessions; {sum(len(s["turns"]) for s in sessions)} turns.', flush=True)
    encoder = EmbeddingCache()
    encoder.encode("Warm up the sentence encoder.")
    # Threshold candidates are fixed before opening test results.
    settings = [
        (backend, context, float(threshold))
        for backend in ("tfidf", "minilm")
        for context in (False, True)
        for threshold in np.arange(0.10, 0.51, 0.05)
    ]
    candidates = []
    for backend, context, threshold in settings:
        rows, events = score_sessions(development, threshold, backend, context, encoder)
        candidates.append({
            "backend": backend, "use_context": context, "threshold": threshold,
            **event_metrics(rows, events),
        })
    scores = pd.DataFrame(candidates).sort_values(
        ["event_f1", "event_precision", "event_recall", "use_context", "threshold", "backend"],
        ascending=[False, False, False, False, True, True],
        kind="stable",
    )
    selected = scores.iloc[0]
    policy = {
        "backend": str(selected["backend"]),
        "use_context": bool(selected["use_context"]),
        "threshold": float(selected["threshold"]),
        "consecutive_off_topic": 2,
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "packages": {name: version(name) for name in ("sentence-transformers", "torch", "scikit-learn", "numpy")},
        "provenance": data["provenance"],
        "evaluation_scope": "Small authored diagnostic; natural dialogue validation remains pending.",
    }
    OUTPUT.mkdir(exist_ok=True)
    (OUTPUT / "topic_policy.json").write_text(json.dumps(policy, indent=2) + "\n")
    scores.to_csv(OUTPUT / "topic_development_grid.csv", index=False)
    print("Locked topic-monitor policy:", policy["backend"], policy["threshold"], policy["use_context"], flush=True)
    rows, events = score_sessions(test, policy["threshold"], policy["backend"], policy["use_context"], encoder)
    report = event_metrics(rows, events)
    (OUTPUT / "topic_test_metrics.json").write_text(json.dumps(report, indent=2) + "\n")
    rows.to_csv(OUTPUT / "topic_test_turns.csv", index=False)
    print("Reserved-topic diagnostic:", json.dumps(report), flush=True)
    timings = []
    monitor = TopicMonitor(test[0]["topic"], policy["threshold"], policy["backend"], policy["use_context"], encoder.model)
    for _, text, _ in test[0]["turns"]:
        start = perf_counter()
        monitor.process(text)
        timings.append(1000 * (perf_counter() - start))
    latency = {
        "device": "cpu",
        "median_ms": float(np.median(timings)),
        "p95_ms": float(np.percentile(timings, 95)),
        "measured_turns": len(timings),
        "embedding_cache": False,
    }
    (OUTPUT / "topic_latency.json").write_text(json.dumps(latency, indent=2) + "\n")
    print(f"Warm CPU per-turn median {latency['median_ms']:.1f} ms, P95 {latency['p95_ms']:.1f} ms", flush=True)


if __name__ == "__main__":
    main()
