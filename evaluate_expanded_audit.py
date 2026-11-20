"""Reproducible frozen-policy stress audit; never trains or changes inference policy."""

from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import re
from time import perf_counter
import urllib.request

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score

from evaluate_topic_relevance import event_metrics, score_sessions
from moderation_session import analyze_turn, load_resources, new_session, review_alert
from nlp_pipeline import preprocess_text


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "results/expanded_audit"
FROZEN = (
    "artifacts/LinearSVC.joblib", "artifacts/LogisticRegression.joblib",
    "artifacts/LinearSVC_alert.joblib", "results/topic_policy.json",
    "moderation_session.py", "topic_relevance.py", "nlp_pipeline.py",
    "data/attack_stress.json", "data/topic_stress.json",
    "evaluate_expanded_audit.py", "tests/test_moderation_contract.py",
)


def hashes():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in FROZEN}


def save_json(name, obj):
    (OUT / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def wilson(success, total):
    if not total:
        return None
    z = 1.959963984540054
    proportion = success / total
    denom = 1 + z * z / total
    centre = (proportion + z * z / (2 * total)) / denom
    half = z * np.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total)) / denom
    return [max(0.0, float(centre - half)), min(1.0, float(centre + half))]


def binary_metrics(reference, predicted):
    y, p = np.asarray(reference, dtype=int), np.asarray(predicted, dtype=int)
    tn, fp, fn, tp = (int(n) for n in confusion_matrix(y, p, labels=[0, 1]).ravel())
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    return {
        "n": len(y), "positive_references": int(y.sum()),
        "accuracy": float(accuracy_score(y, p)),
        "attack_precision": precision, "attack_recall": recall,
        "attack_f1": float(f1_score(y, p, zero_division=0)),
        "macro_f1": float(f1_score(y, p, average="macro", labels=[0, 1], zero_division=0)),
        "tn": tn, "fp": fp, "fn": fn, "tp": tp,
        "accuracy_wilson95": wilson(tp + tn, len(y)),
        "precision_wilson95": wilson(tp, tp + fp),
        "recall_wilson95": wilson(tp, tp + fn),
    }


def attack_scores(bundle, texts):
    margins = bundle["pipeline"].decision_function(list(texts))
    probabilities = bundle["sigmoid"].predict_proba(margins[:, None])[:, 1]
    return probabilities, (probabilities >= bundle["threshold"]).astype(int)


def ensure_source():
    path = ROOT / "data/raw/attack_annotated_comments.tsv"
    expected = "7e39135b410eaed85c7ffec85cf829fd"
    if path.exists() and hashlib.md5(path.read_bytes()).hexdigest() == expected:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(".partial")
    try:
        with urllib.request.urlopen("https://ndownloader.figshare.com/files/7554634", timeout=45) as response:
            with partial.open("wb") as stream:
                while block := response.read(1024 * 1024):
                    stream.write(block)
        if hashlib.md5(partial.read_bytes()).hexdigest() != expected:
            raise ValueError("WikiDetox source checksum mismatch")
        partial.replace(path)
    finally:
        partial.unlink(missing_ok=True)


def audit_authored_attacks(bundle):
    source = json.loads((ROOT / "data/attack_stress.json").read_text())
    rows = pd.DataFrame(source["cases"])
    assert rows["id"].is_unique and rows["text"].is_unique
    assert rows["attack"].isin([0, 1]).all()
    rows["attack_probability"], rows["alert_prediction"] = attack_scores(bundle, rows["text"])
    rows["processed_text"] = rows["text"].map(preprocess_text)
    for name in ("LinearSVC", "LogisticRegression"):
        model = joblib.load(ROOT / f"artifacts/{name}.joblib")
        rows[name] = model.predict(rows["text"])
    primary = rows[~rows["ambiguous"]]
    aggregate = {name: binary_metrics(primary["attack"], primary[name]) for name in (
        "alert_prediction", "LinearSVC", "LogisticRegression"
    )}
    category = []
    for name, group in primary.groupby("category", sort=True):
        category.append({"category": name, **binary_metrics(group["attack"], group["alert_prediction"])})
    rows.to_csv(OUT / "attack_stress_predictions.csv", index=False)
    pd.DataFrame(category).to_csv(OUT / "attack_stress_categories.csv", index=False)
    primary[primary["attack"].ne(primary["alert_prediction"])].to_csv(OUT / "attack_stress_errors.csv", index=False)
    save_json("attack_stress_metrics.json", {
        "provenance": source["provenance"], "excluded_ambiguous": int(rows["ambiguous"].sum()),
        "models": aggregate,
        "interval_caution": "Wilson intervals describe these authored cases under an iid approximation; they do not quantify generalization to natural conversations.",
    })

    # Meaning-preserving formatting and transcript-like perturbations. All are simulations.
    transforms = {
        "uppercase": str.upper,
        "html_wrap": lambda s: "<p>" + s + "</p>",
        "extra_whitespace": lambda s: "  " + "  \n ".join(s.split()) + "  ",
        "punctuation_removed": lambda s: re.sub(r"[^\w\s]", "", s),
        "disfluency_prefix": lambda s: "um well I mean " + s,
        "chat_prefix": lambda s: "btw " + s,
    }
    variants = []
    for row in primary.itertuples():
        for transform, function in transforms.items():
            text = function(row.text)
            variants.append({
                "id": row.id, "transform": transform, "text": text,
                "reference": row.attack, "original_prediction": row.alert_prediction,
                "original_probability": row.attack_probability,
                "processed_identical": preprocess_text(text) == row.processed_text,
            })
    variants = pd.DataFrame(variants)
    variants["attack_probability"], variants["prediction"] = attack_scores(bundle, variants["text"])
    variants["changed"] = variants["prediction"].ne(variants["original_prediction"])
    variants.to_csv(OUT / "attack_perturbations.csv", index=False)
    summaries = []
    for name, group in variants.groupby("transform"):
        summaries.append({
            "transform": name, "changed_decisions": int(group["changed"].sum()),
            "change_rate": float(group["changed"].mean()),
            "identical_preprocessed": int(group["processed_identical"].sum()),
            **binary_metrics(group["reference"], group["prediction"]),
        })
    save_json("attack_perturbation_metrics.json", summaries)
    return aggregate["alert_prediction"]


def audit_existing_holdout(bundle):
    saved = pd.read_csv(ROOT / "results/alert_benchmark_predictions.csv")
    raw_path = ROOT / "data/raw/attack_annotated_comments.tsv"
    digest = hashlib.md5(raw_path.read_bytes()).hexdigest()
    assert digest == "7e39135b410eaed85c7ffec85cf829fd"
    raw = pd.read_csv(raw_path, sep="\t", quoting=csv.QUOTE_NONE, keep_default_na=False,
                      usecols=["rev_id", "comment"])
    rows = saved.merge(raw, on="rev_id", how="left", validate="one_to_one")
    assert len(rows) == 22_921 and rows["comment"].notna().all()
    # Re-run actual inference over every original held-out comment, not only saved CSV metrics.
    probabilities, predictions = attack_scores(bundle, rows["comment"])
    assert np.array_equal(predictions, rows["alert_prediction"])
    assert np.allclose(probabilities, rows["attack_probability"], atol=1e-7, rtol=1e-7)
    rows["words"] = rows["comment"].map(lambda s: len(preprocess_text(s).split()))
    text = rows["comment"].str.casefold()
    masks = {
        "all_existing_test": np.ones(len(rows), dtype=bool),
        "length_1_to_10": rows["words"].le(10),
        "length_11_to_40": rows["words"].between(11, 40),
        "length_41_to_100": rows["words"].between(41, 100),
        "length_over_100": rows["words"].gt(100),
        "contains_second_person": text.str.contains(r"\byou(?:r|rs)?\b", regex=True),
        "contains_negation": text.str.contains(r"\b(?:not|never|no)\b|n't", regex=True),
        "contains_quote_mark": text.str.contains(r'["“”]', regex=True),
        "contains_profanity_token": text.str.contains(r"\b(?:fuck\w*|shit\w*|damn|bloody|piss\w*)\b", regex=True),
        "contains_question_mark": text.str.contains("?", regex=False),
        "contains_export_artifacts": rows["comment"].str.contains("NEWLINE_TOKEN|TAB_TOKEN", regex=True),
    }
    slices = []
    for name, mask in masks.items():
        group = rows[mask]
        if len(group):
            slices.append({"slice": name, **binary_metrics(group["label"], group["alert_prediction"])})
    pd.DataFrame(slices).to_csv(OUT / "existing_holdout_slices.csv", index=False)
    overall = binary_metrics(rows["label"], rows["alert_prediction"])
    save_json("existing_holdout_metrics.json", {
        **overall, "source_md5": digest, "all_predictions_reproduced": True,
        "independence": "This is the existing test set, not 22,921 new observations. Slices overlap and are lexical flags, not human semantic labels.",
    })
    # Include concrete reviewable mistakes sampled deterministically, without cherry-picking by score.
    errors = rows[rows["label"].ne(rows["alert_prediction"])]
    errors.groupby("label", group_keys=False).sample(n=20, random_state=1806).to_csv(
        OUT / "existing_holdout_error_sample.csv", index=False
    )
    return overall


def audit_topics(policy, encoder, bundle):
    source = json.loads((ROOT / "data/topic_stress.json").read_text())
    sessions = source["sessions"]
    assert len({s["id"] for s in sessions}) == len(sessions)
    assert all(t[2] in {"on_topic", "off_topic", "unclear"} for s in sessions for t in s["turns"])
    rows, events = score_sessions(sessions, policy["threshold"], policy["backend"], policy["use_context"], encoder)
    metrics = event_metrics(rows, events)
    metrics.update({
        "sessions": len(sessions), "turns": len(rows),
        "event_precision_wilson95": wilson(metrics["detected"], int(rows["alert"].sum())),
        "event_recall_wilson95": wilson(metrics["detected"], len(events)),
        "policy_threshold": policy["threshold"], "provenance": source["provenance"],
    })
    clear = rows[rows["reference"].ne("unclear")]
    clear_metrics = binary_metrics(
        clear["reference"].eq("off_topic"), clear["state"].eq("off_topic")
    )
    for key in ("precision", "recall", "f1"):
        clear_metrics[f"off_topic_{key}"] = clear_metrics.pop(f"attack_{key}")
    clear_metrics["positive_class"] = "off_topic"
    metrics["clear_turn_classification"] = clear_metrics
    session_rows = []
    for session in sessions:
        subset = rows[rows["session"].eq(session["id"])]
        local_events = [e for e in events if e[0] == session["id"]]
        session_rows.append({"session": session["id"], "category": session["category"],
                             **event_metrics(subset, local_events)})
    pd.DataFrame(session_rows).to_csv(OUT / "topic_stress_sessions.csv", index=False)
    controls = [row for row in session_rows if row["events"] == 0]
    metrics["negative_control_sessions"] = len(controls)
    metrics["negative_controls_without_alerts"] = sum(row["false_alerts"] == 0 for row in controls)
    event_rows = []
    for sid, episode, first, last in events:
        window = rows[rows["session"].eq(sid) & rows["turn"].between(first, last)]
        alerts = window[window["alert"]]
        event_rows.append({"session": sid, "episode": episode, "first_turn": first,
                           "last_turn": last, "detected": not alerts.empty,
                           "first_alert_turn": int(alerts.iloc[0]["turn"]) if not alerts.empty else None})
    pd.DataFrame(event_rows).to_csv(OUT / "topic_stress_events.csv", index=False)
    rows.to_csv(OUT / "topic_stress_turns.csv", index=False)
    rows[rows["reference"].ne(rows["state"])].to_csv(OUT / "topic_stress_turn_errors.csv", index=False)
    save_json("topic_stress_metrics.json", metrics)

    # Full production session wrapper: compare every topic result with isolated monitor evaluation.
    wrapper_rows = []
    for session in sessions:
        state = new_session(session["topic"], (bundle, policy, encoder))
        for index, (speaker, text, reference) in enumerate(session["turns"], 1):
            old_count = len(state["turns"])
            updated = analyze_turn(state, speaker, text, (bundle, policy, encoder))
            assert len(state["turns"]) == old_count, "Prior state mutated"
            expected = rows[rows["session"].eq(session["id"]) & rows["turn"].eq(index)].iloc[0]
            actual = updated["turns"][-1]
            assert actual["speaker"] == speaker
            assert actual["topic"]["state"] == expected["state"]
            assert actual["topic"]["alert"] == expected["alert"]
            assert all(a["speaker"] == updated["turns"][a["turn"]-1]["speaker"] for a in updated["alerts"])
            wrapper_rows.append({"session": session["id"], "turn": index,
                                 "latency_ms": actual["latency_ms"],
                                 "personal_attack": actual["personal_attack"],
                                 "topic_alert": actual["topic"]["alert"]})
            state = updated
    wrapper = pd.DataFrame(wrapper_rows)
    wrapper.to_csv(OUT / "production_wrapper_turns.csv", index=False)
    save_json("production_wrapper_checks.json", {
        "matched_topic_predictions": len(wrapper), "speaker_attribution_verified": True,
        "prior_states_unchanged": True, "sessions": len(sessions),
        "warm_median_ms": float(wrapper["latency_ms"].median()),
        "warm_p95_ms": float(wrapper["latency_ms"].quantile(0.95)),
        "timing_scope": "Warm text wrapper on this local CPU, excludes queue, UI rendering, audio and ASR. Includes repeated topic encoding and state copying.",
    })
    return metrics


def audit_workloads(resources):
    texts = [
        "A standard school uniform can make the daily choice of clothing simpler.",
        "I disagree because a uniform can still be expensive for a family.",
        "The school uniform policy should include financial support for families.",
        "You are a stupid idiot and I would rather talk about my pet lizard.",
        "My pet lizard sleeps beside a little purple toy castle.",
        "The school uniform trial should measure the full cost for parents.",
    ]
    def run_session(count):
        state = new_session("Schools should require pupils to wear a standard uniform.", resources)
        elapsed = []
        for i in range(count):
            start = perf_counter()
            state = analyze_turn(state, "A" if i % 2 == 0 else "B", texts[i % len(texts)], resources)
            elapsed.append((perf_counter()-start)*1000)
        if state["alerts"]:
            before = state
            state = review_alert(state, state["alerts"][0]["id"], "Reviewed")
            assert before["alerts"][0]["status"] == "Pending"
        assert len(state["turns"]) == count
        assert len({a["id"] for a in state["alerts"]}) == len(state["alerts"])
        return state, elapsed

    state, elapsed = run_session(250)
    with ThreadPoolExecutor(max_workers=2) as pool:
        parallel = list(pool.map(run_session, [20, 20, 20, 20]))
    assert len({item[0]["id"] for item in parallel}) == 4
    assert len({json.dumps(s["monitor"], sort_keys=True) for s, _ in parallel}) == 1
    for s, _ in parallel:
        assert [t["text"] for t in s["turns"]] == [texts[i % len(texts)] for i in range(20)]
    report = {
        "long_session_turns": len(state["turns"]), "long_session_alerts": len(state["alerts"]),
        "warm_end_to_end_median_ms": float(np.median(elapsed)),
        "warm_end_to_end_p95_ms": float(np.percentile(elapsed, 95)),
        "first_50_median_ms": float(np.median(elapsed[:50])),
        "last_50_median_ms": float(np.median(elapsed[-50:])),
        "concurrent_independent_sessions": 4, "parallel_workers": 2,
        "concurrent_session_turns": 20, "cross_session_contamination": False,
        "scope": "Synthetic repetition is a state/performance workload, not a quality benchmark. Does not establish production scalability or browser/network timing.",
    }
    save_json("workload_checks.json", report)
    return report


def main():
    OUT.mkdir(exist_ok=True, parents=True)
    frozen = hashes()
    save_json("manifest.json", {
        "frozen_sha256": frozen,
        "packages": {name: version(name) for name in ("scikit-learn", "numpy", "sentence-transformers", "torch")},
        "design": "Policies, models and labels frozen before inference. Authored stress cases, existing holdout re-audit and workflow checks reported separately.",
    })
    resources = load_resources()
    bundle, policy, encoder = resources
    print("Resources loaded; policies frozen.", flush=True)
    ensure_source()
    attacks = audit_authored_attacks(bundle)
    print("Authored attack stress:", json.dumps(attacks), flush=True)
    holdout = audit_existing_holdout(bundle)
    print("Existing heldout predictions exactly reproduced:", holdout["n"], flush=True)
    topics = audit_topics(policy, encoder, bundle)
    print("Topic episodes:", topics["detected"], "/", topics["events"], "false alerts:", topics["false_alerts"], flush=True)
    workload = audit_workloads(resources)
    assert frozen == hashes(), "Model, policy, data or inference files changed during audit"
    save_json("summary.json", {
        "attack_stress": attacks, "existing_holdout": holdout,
        "topic_stress": {k: v for k, v in topics.items() if k != "provenance"},
        "workload": workload, "frozen_files_unchanged": True,
    })
    print("Audit saved to", OUT, flush=True)


if __name__ == "__main__":
    main()
