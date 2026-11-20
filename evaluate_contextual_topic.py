"""Select bounded topic context on development conversations and replay fixed diagnostics."""

import itertools
import json
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score

from contextual_topic import BoundedTopicMonitor
from evaluate_topic_relevance import EmbeddingCache, event_metrics, score_sessions

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "results/contextual_topic"


def read(name):
    return json.loads((ROOT / name).read_text())


def score(candidate, sessions, baseline, encoder):
    records = []
    for session in sessions:
        monitor = BoundedTopicMonitor(session["topic"], encoder=encoder, **candidate)
        records.extend(monitor.process(text) for _, text, _ in session["turns"])
    states = pd.DataFrame(records)
    assert len(baseline) == len(states)
    return pd.concat([baseline.drop(columns=states.columns), states], axis=1)


def metrics(rows, events):
    result = event_metrics(rows, events)
    result["turn_macro_f1"] = float(f1_score(
        rows["reference"], rows["state"],
        labels=["on_topic", "off_topic", "unclear"], average="macro", zero_division=0,
    ))
    result["related_turns_flagged_off_topic"] = int(((rows.reference == "on_topic") & (rows.state == "off_topic")).sum())
    result["off_topic_turns_labeled_related"] = int(((rows.reference == "off_topic") & (rows.state == "on_topic")).sum())
    result["turns"] = len(rows)
    return result


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    established = read("results/topic_policy.json")
    encoder = EmbeddingCache()
    partitions = read("data/topic_dialogues.json")["sessions"]
    dev = [case for case in partitions if case["split"] == "development"]
    diagnostics = {
        "original_reserved": [case for case in partitions if case["split"] == "test"],
        "challenge": read("data/topic_challenge.json")["sessions"],
        "expanded_regression": read("data/topic_stress.json")["sessions"],
    }

    def baseline(sessions):
        return score_sessions(sessions, established["threshold"], "minilm", True, encoder)

    dev_rows, dev_events = baseline(dev)
    trials = []
    for window, link in itertools.product((2, 3, 4), (.15, .25, .35, .45)):
        policy = {"threshold": established["threshold"], "context_window": window, "link_threshold": link}
        trials.append((policy, metrics(score(policy, dev, dev_rows, encoder), dev_events)))
    policy, dev_candidate = max(trials, key=lambda item: (
        item[1]["event_f1"], item[1]["turn_macro_f1"], -item[0]["context_window"], item[0]["link_threshold"],
    ))
    policy_record = {"settings": policy, "selection": "Development only. Choose event F1, then turn macro F1, then shorter context and higher link cutoff."}
    (OUT / "candidate_policy.json").write_text(json.dumps(policy_record, indent=2) + "\n")
    pd.DataFrame([{**settings, **result} for settings, result in trials]).to_csv(OUT / "development_grid.csv", index=False)
    summary = {"policy": policy_record, "development": {"current": metrics(dev_rows, dev_events), "candidate": dev_candidate}}
    print("Selected on development", policy, flush=True)
    for name, sessions in diagnostics.items():
        original, events = baseline(sessions)
        revised = score(policy, sessions, original, encoder)
        summary[name] = {"current": metrics(original, events), "candidate": metrics(revised, events)}
        revised.assign(current_state=original.state, current_alert=original.alert).to_csv(OUT / f"{name}_turns.csv", index=False)
        print(name, summary[name], flush=True)
    start = perf_counter()
    monitor = BoundedTopicMonitor(dev[0]["topic"], encoder=encoder.model, **policy)
    timings = []
    for _, turn, _ in dev[0]["turns"]:
        start = perf_counter()
        monitor.process(turn)
        timings.append(1000 * (perf_counter() - start))
    summary["warm_cpu_latency"] = {"scope": "One authored development session, encoder cache disabled.",
                                   "median_ms": float(np.median(timings)), "p95_ms": float(np.percentile(timings, 95))}
    summary["scope"] = "Previously inspected authored diagnostics and tiny development partition. A new human-annotated conversation set is needed for independent evaluation."
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    main()
