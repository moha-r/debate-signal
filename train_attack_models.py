"""Tune two sparse text classifiers using the WikiDetox training partition only."""

import argparse
from importlib.metadata import version
from itertools import product
import json
from pathlib import Path
from time import perf_counter

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from nlp_pipeline import make_vectorizer, preprocess_text


FOLDS = 3
SEED = 42
MODELS = ("LogisticRegression", "LinearSVC")
FEATURES = tuple(product((1, 2), (30_000, 50_000)))
REGULARIZATION = (0.5, 2.0)
WEIGHTS = ("uniform", "balanced")


def make_estimator(name, strength, weighting):
    class_weight = None if weighting == "uniform" else weighting
    if name == "LogisticRegression":
        return LogisticRegression(C=strength, class_weight=class_weight, max_iter=1_000)
    return LinearSVC(
        C=strength, class_weight=class_weight, dual="auto", max_iter=5_000, random_state=SEED
    )


def training_vectorizer(ngram_max, max_features):
    # The split already stores the text produced by preprocess_text for deduplication.
    return make_vectorizer((1, ngram_max), max_features=max_features).set_params(preprocessor=None)


def tune(texts, labels):
    folds = StratifiedKFold(n_splits=FOLDS, shuffle=True, random_state=SEED)
    results = []
    for fold, (fit_idx, val_idx) in enumerate(folds.split(texts, labels), 1):
        for ngram_max, max_features in FEATURES:
            vectorizer = training_vectorizer(ngram_max, max_features)
            start = perf_counter()
            X_fit = vectorizer.fit_transform(texts[fit_idx])
            X_val = vectorizer.transform(texts[val_idx])
            feature_seconds = perf_counter() - start

            # Reuse the fold-local sparse matrices across classifier settings.
            for name, strength, weighting in product(MODELS, REGULARIZATION, WEIGHTS):
                estimator = make_estimator(name, strength, weighting)
                start = perf_counter()
                estimator.fit(X_fit, labels[fit_idx])
                fit_seconds = perf_counter() - start
                predicted = estimator.predict(X_val)
                results.append({
                    "fold": fold,
                    "model": name,
                    "ngram_max": ngram_max,
                    "max_features": max_features,
                    "C": strength,
                    "weighting": weighting,
                    "macro_f1": f1_score(labels[val_idx], predicted, average="macro", zero_division=0),
                    "attack_f1": f1_score(labels[val_idx], predicted, zero_division=0),
                    "features_seconds": feature_seconds,
                    "estimator_fit_seconds": fit_seconds,
                })
            print(f"Fold {fold}/{FOLDS} | n-gram max {ngram_max} | cap {max_features:,}", flush=True)
    return pd.DataFrame(results)


def summarize(fold_results):
    return (
        fold_results
        .groupby(["model", "ngram_max", "max_features", "C", "weighting"], as_index=False)
        .agg(
            cv_macro_f1=("macro_f1", "mean"),
            cv_macro_f1_sd=("macro_f1", "std"),
            cv_attack_f1=("attack_f1", "mean"),
            features_seconds=("features_seconds", "mean"),
            estimator_fit_seconds=("estimator_fit_seconds", "mean"),
        )
        .sort_values(
            ["cv_macro_f1", "cv_attack_f1", "max_features", "ngram_max", "C", "model", "weighting"],
            ascending=[False, False, True, True, True, True, True],
        )
        .reset_index(drop=True)
    )


def fit_and_export(train, selected, output_dir):
    labels = train["label"].to_numpy(dtype=np.int32)
    texts = train["model_text"].to_numpy()
    probe = train.sample(n=min(32, len(train)), random_state=SEED)
    records = []
    for config in selected.to_dict("records"):
        vectorizer = training_vectorizer(config["ngram_max"], config["max_features"])
        start = perf_counter()
        X_fit = vectorizer.fit_transform(texts)
        features_seconds = perf_counter() - start

        estimator = make_estimator(config["model"], config["C"], config["weighting"])
        start = perf_counter()
        estimator.fit(X_fit, labels)
        fit_seconds = perf_counter() - start
        expected = estimator.predict(vectorizer.transform(probe["model_text"])).tolist()
        vectorizer.set_params(preprocessor=preprocess_text)
        pipeline = Pipeline([("tfidf", vectorizer), ("classifier", estimator)])
        assert pipeline.predict(probe["comment"]).tolist() == expected
        artifact = output_dir / f'{config["model"]}.joblib'
        joblib.dump(pipeline, artifact, compress=3)
        records.append({
            **config,
            "artifact": artifact.name,
            "features": X_fit.shape[1],
            "final_features_seconds": features_seconds,
            "final_estimator_fit_seconds": fit_seconds,
        })
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("training_csv", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    train = pd.read_csv(
        args.training_csv,
        keep_default_na=False,
        dtype={"comment": str, "model_text": str, "label": np.int32},
    )
    if not train["model_text"].is_unique or train["model_text"].eq("").any():
        raise ValueError("Training samples must have unique and nonempty model inputs")
    if set(train["label"]) != {0, 1} or train["label"].value_counts().min() < FOLDS:
        raise ValueError("Both labels must be present in every validation fold")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    start = perf_counter()
    folded = tune(train["model_text"].to_numpy(), train["label"].to_numpy(dtype=np.int32))
    assert len(folded) == FOLDS * len(FEATURES) * len(MODELS) * len(REGULARIZATION) * len(WEIGHTS)
    summary = summarize(folded)
    chosen = summary.drop_duplicates("model")
    folded.to_csv(args.output_dir / "cv_folds.csv", index=False)
    summary.to_csv(args.output_dir / "cv_summary.csv", index=False)
    trained = fit_and_export(train, chosen, args.output_dir)
    report = {
        "folds": FOLDS,
        "seed": SEED,
        "training_rows": len(train),
        "champion_by_cv": trained[0]["model"],
        "models": trained,
        "wall_seconds": perf_counter() - start,
        "packages": {
            package: version(package)
            for package in ("scikit-learn", "numpy", "scipy", "nltk", "joblib")
        },
    }
    (args.output_dir / "training_summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(chosen.round(4).to_string(index=False))
    print(f"Champion selected by training CV: {report['champion_by_cv']}")


if __name__ == "__main__":
    main()
