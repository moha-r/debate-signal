"""Compare the completed DistilBERT experiment with the production attack rule."""

import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter

import joblib
import numpy as np
import pandas as pd
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from prepare_transformer_data import clean_transformer_text
from training_policy import select_alert_threshold
from transformer_batches import binary_scores

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data/transformer"
RUN = ROOT / "results/transformer/distilbert_run02"
ARTIFACT = ROOT / "artifacts/DistilBERT_candidate_v2"
BASELINE = "Current LinearSVC alert"
CANDIDATE = "DistilBERT candidate"


def read_json(path):
    return json.loads(path.read_text())


def save_json(path, value):
    partial = path.with_suffix(".partial")
    partial.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    partial.replace(path)


class DistilBertScorer:
    def __init__(self, directory, device, batch_size=24):
        self.tokenizer = AutoTokenizer.from_pretrained(directory, local_files_only=True)
        self.model = AutoModelForSequenceClassification.from_pretrained(
            directory, local_files_only=True
        ).to(device).eval()
        self.device = device
        self.batch_size = batch_size

    @torch.inference_mode()
    def score(self, texts, mode, max_length=128):
        if mode not in {"whole", "overlap"}:
            raise ValueError(f"Unknown inference mode: {mode}")
        windowed = mode == "overlap"
        width = 96 if windowed else max_length
        encoding = self.tokenizer(
            [clean_transformer_text(text) for text in texts],
            padding="max_length", truncation=True, max_length=width,
            stride=32 if windowed else 0, return_overflowing_tokens=windowed,
            return_tensors="np",
        )
        ids, masks = encoding["input_ids"], encoding["attention_mask"]
        lengths = masks.sum(axis=1)
        order = np.argsort(lengths, kind="stable")
        scores = np.empty(len(ids), dtype=float)
        for first in range(0, len(order), self.batch_size):
            batch = order[first:first + self.batch_size]
            padded = min(width, max(32, (int(lengths[batch].max()) + 31) // 32 * 32))
            values = self.model(
                input_ids=torch.from_numpy(ids[batch, :padded]).to(self.device),
                attention_mask=torch.from_numpy(masks[batch, :padded]).to(self.device),
            ).logits.softmax(dim=-1)[:, 1]
            scores[batch] = values.cpu().numpy()
        if not windowed:
            return scores
        maximum = np.zeros(len(texts), dtype=float)
        np.maximum.at(maximum, encoding["overflow_to_sample_mapping"], scores)
        return maximum


def baseline_scores(bundle, texts):
    margins = bundle["pipeline"].decision_function(list(texts))
    return bundle["sigmoid"].predict_proba(margins[:, None])[:, 1]


def compare(frame, candidate, baseline, cutoff, baseline_cutoff):
    return {
        BASELINE: binary_scores(frame.label, baseline, baseline_cutoff),
        CANDIDATE: binary_scores(frame.label, candidate, cutoff),
    }


def save_predictions(path, frame, candidate, baseline, cutoff, baseline_cutoff):
    frame.assign(
        baseline_score=baseline, candidate_score=candidate,
        baseline_alert=(baseline >= baseline_cutoff).astype(int),
        candidate_alert=(candidate >= cutoff).astype(int),
    ).to_csv(path, index=False)


def time_single(scorer, bundle, texts, mode, width):
    candidate_times, baseline_times = [], []
    scorer.score(texts[:2], mode, width)
    for text in texts:
        start = perf_counter()
        baseline_scores(bundle, [text])
        baseline_times.append((perf_counter() - start) * 1000)
        start = perf_counter()
        scorer.score([text], mode, width)
        candidate_times.append((perf_counter() - start) * 1000)
    return {
        key: {"median_ms": float(np.median(times)), "p95_ms": float(np.percentile(times, 95)),
              "samples": len(times), "device": "cpu" if key == BASELINE else scorer.device}
        for key, times in [(BASELINE, baseline_times), (CANDIDATE, candidate_times)]
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", choices=("mps", "cpu"), default="mps")
    parser.add_argument("--batch-size", type=int, default=24)
    args = parser.parse_args()
    if read_json(RUN / "status.json")["state"] != "complete":
        raise RuntimeError("Wait for training and checkpoint selection to complete")
    torch.set_num_threads(4)
    if args.device == "mps":
        torch.mps.set_per_process_memory_fraction(.55)
    output = RUN / "evaluation"
    output.mkdir(exist_ok=True)
    manifest = read_json(DATA / "manifest.json")
    for part in ("validation", "test"):
        if hashlib.sha256((DATA / f"{part}.jsonl").read_bytes()).hexdigest() != manifest["parts"][part]["sha256"]:
            raise ValueError(f"Partition checksum mismatch: {part}")
    validation = pd.read_csv(RUN / "validation_predictions.csv", keep_default_na=False)
    original_validation = pd.read_json(DATA / "validation.jsonl", lines=True)
    assert validation.rev_id.tolist() == original_validation.rev_id.tolist()
    assert validation.label.tolist() == original_validation.label.tolist()
    bundle = joblib.load(ROOT / "artifacts/LinearSVC_alert.joblib")
    configuration = read_json(RUN / "configuration.json")
    width = configuration["max_length"]
    scorer = DistilBertScorer(ARTIFACT / "best", args.device, args.batch_size)
    print("Scoring validation with overlapping 96-token windows...", flush=True)
    options = {
        "whole": validation.attack_probability.to_numpy(),
        "overlap": scorer.score(validation.text.tolist(), "overlap", width),
    }
    policies = {mode: select_alert_threshold(validation.label, scores, minimum_alerts=100)
                for mode, scores in options.items()}
    selected_mode = max(policies, key=lambda mode: (
        policies[mode]["precision_target_met"],
        policies[mode]["recall"] if policies[mode]["precision_target_met"] else policies[mode]["macro_f1"],
        policies[mode]["macro_f1"], mode == "whole",
    ))
    threshold = policies[selected_mode]["threshold"]
    rule = {
        "mode": selected_mode, "max_length": width, "threshold": threshold, "validation_options": policies,
        "selection": "Maximize recall at at least 80% validation precision and 100 alerts. Break ties using macro F1 and prefer the simpler whole-turn rule. If no option qualifies, compare macro F1.",
        "score": "Uncalibrated softmax. The operating threshold is selected using WikiDetox validation.",
        "model_sha256": hashlib.sha256((ARTIFACT / "best/model.safetensors").read_bytes()).hexdigest(),
    }
    save_json(output / "locked_policy.json", rule)
    print("Locked validation rule", json.dumps(rule), flush=True)
    baseline_validation = baseline_scores(bundle, validation.text)
    validation.assign(overlap_score=options["overlap"], baseline_score=baseline_validation).to_csv(
        output / "validation_inference_comparison.csv", index=False
    )

    heldout = pd.read_json(DATA / "test.jsonl", lines=True)
    saved = pd.read_csv(ROOT / "results/alert_benchmark_predictions.csv")
    assert heldout.rev_id.tolist() == saved.rev_id.tolist()
    assert heldout.label.tolist() == saved.label.tolist()
    print(f"Scoring {len(heldout):,} original test comments with the locked rule...", flush=True)
    start = perf_counter()
    candidate = scorer.score(heldout.text.tolist(), selected_mode, width)
    baseline = saved.attack_probability.to_numpy()
    test_metrics = compare(heldout, candidate, baseline, threshold, bundle["threshold"])
    save_predictions(output / "heldout_predictions.csv", heldout[["rev_id", "label"]], candidate, baseline, threshold, bundle["threshold"])
    words = heldout.text.str.split().str.len()
    length_bins = pd.cut(words, bins=[0, 10, 40, 100, np.inf], labels=["1–10", "11–40", "41–100", "101+"])
    length_rows = []
    for group in length_bins.cat.categories:
        mask = (length_bins == group).to_numpy()
        if mask.any():
            for name, metrics in compare(heldout.loc[mask], candidate[mask], baseline[mask], threshold, bundle["threshold"]).items():
                length_rows.append({"words": group, "model": name, **metrics})
    pd.DataFrame(length_rows).to_csv(output / "heldout_length_slices.csv", index=False)
    print("Original test", json.dumps(test_metrics), flush=True)

    stress = pd.DataFrame(read_json(ROOT / "data/attack_stress.json")["cases"])
    stress = stress.loc[~stress.ambiguous].rename(columns={"attack": "label"}).copy()
    candidate_stress = scorer.score(stress.text.tolist(), selected_mode, width)
    frozen_stress = pd.read_csv(ROOT / "results/expanded_audit/attack_stress_predictions.csv").set_index("id")
    baseline_stress = frozen_stress.loc[stress.id, "attack_probability"].to_numpy()
    stress["candidate_score"] = candidate_stress
    stress["baseline_score"] = baseline_stress
    stress_metrics = compare(stress, candidate_stress, baseline_stress, threshold, bundle["threshold"])
    category_rows = []
    for category, rows in stress.groupby("category"):
        for name, metrics in compare(rows, rows.candidate_score, rows.baseline_score, threshold, bundle["threshold"]).items():
            category_rows.append({"category": category, "model": name, **metrics})
    pd.DataFrame(category_rows).to_csv(output / "stress_categories.csv", index=False)
    save_predictions(output / "stress_predictions.csv", stress, candidate_stress, baseline_stress, threshold, bundle["threshold"])
    print("Authored regression", json.dumps(stress_metrics), flush=True)
    timing_texts = stress.sample(n=60, random_state=1842).text.tolist()
    device_timing = time_single(scorer, bundle, timing_texts, selected_mode, width)
    del scorer
    if args.device == "mps":
        torch.mps.empty_cache()
    cpu = DistilBertScorer(ARTIFACT / "best", "cpu")
    timing = time_single(cpu, bundle, timing_texts, selected_mode, width)
    new = test_metrics[CANDIDATE]
    old = test_metrics[BASELINE]
    adoption = {
        "heldout_precision_at_least_80_percent": new["attack_precision"] >= .8,
        "heldout_recall_improved": new["attack_recall"] > old["attack_recall"],
        "heldout_macro_f1_improved": new["macro_f1"] > old["macro_f1"],
        "regression_false_alerts_not_increased": stress_metrics[CANDIDATE]["fp"] <= stress_metrics[BASELINE]["fp"],
        "regression_missed_attacks_not_increased": stress_metrics[CANDIDATE]["fn"] <= stress_metrics[BASELINE]["fn"],
    }
    summary = {
        "inference_policy": rule, "wiki_test": test_metrics, "authored_regression": stress_metrics,
        "cpu_single_turn_latency": timing, "evaluation_device_single_turn_latency": device_timing,
        "adoption_checks": adoption,
        "evaluation_seconds": perf_counter() - start,
        "scope": "Original test contains human-labeled WikiDetox comments. The project assistant authored the dialogue regression inputs before training. Natural recording and independent dialogue annotation are pending.",
    }
    save_json(output / "summary.json", summary)
    print("Completed attack comparison:", output / "summary.json", flush=True)


if __name__ == "__main__":
    main()
