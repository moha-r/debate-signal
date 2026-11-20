"""Recreate WikiDetox boundaries and prepare readable text for a transformer."""

import argparse
import csv
import hashlib
import html
import json
from pathlib import Path
import re
import unicodedata

import pandas as pd
from sklearn.model_selection import train_test_split

from nlp_pipeline import APOSTROPHES, HTML_TAG, URL, preprocess_text


ROOT = Path(__file__).resolve().parent


def clean_transformer_text(text):
    text = text.replace("NEWLINE_TOKEN", " ").replace("TAB_TOKEN", " ")
    text = unicodedata.normalize("NFKC", html.unescape(text)).translate(APOSTROPHES)
    text = HTML_TAG.sub(" ", text)
    text = URL.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def split_fit_validation(frame, seed=1842, fraction=.1):
    return train_test_split(frame, test_size=fraction, stratify=frame["label"], random_state=seed)


def validate_supplement(cases, blocked_inputs):
    seen, output = set(), []
    for case in cases:
        text = clean_transformer_text(case["text"])
        key = preprocess_text(text)
        if not key or key in blocked_inputs or key in seen:
            raise ValueError("Supplement contains empty, duplicate or reserved evaluation input")
        if case["label"] not in (0, 1):
            raise ValueError("Supplement labels must be binary")
        seen.add(key)
        output.append({**case, "text": text, "label": int(case["label"])})
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "data/transformer")
    args = parser.parse_args()
    files = {
        "attack_annotated_comments.tsv": "7e39135b410eaed85c7ffec85cf829fd",
        "attack_annotations.tsv": "c1621e0451236eb3eea9c8f7df77f4b7",
    }
    for name, digest in files.items():
        if hashlib.md5((ROOT / "data/raw" / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Source checksum mismatch: {name}")
    comments = pd.read_csv(ROOT / "data/raw/attack_annotated_comments.tsv", sep="\t",
                           quoting=csv.QUOTE_NONE, keep_default_na=False, usecols=["rev_id", "comment"])
    votes = pd.read_csv(ROOT / "data/raw/attack_annotations.tsv", sep="\t",
                        usecols=["rev_id", "attack"], dtype={"attack": "int8"})
    labels = votes.groupby("rev_id")["attack"].agg(attack_votes="sum", ratings="size")
    labels["label"] = (2 * labels["attack_votes"] > labels["ratings"]).astype("int8")
    data = comments.merge(labels, left_on="rev_id", right_index=True, validate="one_to_one")
    data["model_text"] = data["comment"].map(preprocess_text)
    data = data[data["model_text"].ne("")]
    consistent = data.groupby("model_text", sort=False)["label"].transform("nunique").eq(1)
    data = (data[consistent].sort_values(["ratings", "rev_id"], ascending=[False, True])
            .drop_duplicates("model_text").sort_values("rev_id").reset_index(drop=True))
    outer_train, test = train_test_split(data, test_size=.2, stratify=data["label"], random_state=42)
    original = pd.read_csv(ROOT / "results/heldout_predictions.csv")
    assert test["rev_id"].tolist() == original["rev_id"].tolist(), "Original outer test split changed"
    assert test["label"].tolist() == original["label"].tolist()
    assert len(outer_train) == 91_683 and len(test) == 22_921
    stress = json.loads((ROOT / "data/attack_stress.json").read_text())
    blocked = {preprocess_text(c["text"]) for c in stress["cases"]}
    # The authored audit is a regression set. Still remove exact normalized matches from fitting/validation.
    excluded = outer_train[outer_train["model_text"].isin(blocked)].copy()
    available = outer_train[~outer_train["model_text"].isin(blocked)].copy()
    fit, validation = split_fit_validation(available)
    parts = {"fit": fit, "validation": validation, "test": test}
    args.output.mkdir(parents=True, exist_ok=True)
    summaries = {}
    for name, frame in parts.items():
        frame = frame.copy()
        frame["text"] = frame["comment"].map(clean_transformer_text)
        assert frame["text"].str.len().gt(0).all()
        target = args.output / f"{name}.jsonl"
        frame[["rev_id", "text", "label"]].to_json(target, orient="records", lines=True, force_ascii=False)
        summaries[name] = {
            "rows": len(frame), "attacks": int(frame["label"].sum()),
            "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            "revision_ids_sha256": hashlib.sha256(",".join(map(str, frame["rev_id"])).encode()).hexdigest(),
        }
    assert not set(fit["rev_id"]) & set(validation["rev_id"])
    assert not set(test["rev_id"]) & set(available["rev_id"])
    assert not set(available["model_text"]) & blocked
    manifest = {
        "source_md5": files, "outer_seed": 42, "validation_seed": 1842,
        "validation_fraction": .1, "original_outer_train_rows": len(outer_train),
        "excluded_audit_matching_training_rows": len(excluded),
        "excluded_training_revision_ids": excluded["rev_id"].tolist(),
        "parts": summaries,
        "input": "Readable original text, punctuation/negation/quotes retained; no stemming. Classical normalization used only to preserve original split and exclude exact audit matches.",
        "evaluation_scope": "Original WikiDetox outer test is preserved. Existing authored stress cases informed the design and are regressions, not an independent final test. Natural dialogue and independent human labels remain pending.",
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2), flush=True)


if __name__ == "__main__":
    main()
