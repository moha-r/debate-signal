"""Local, resumable DistilBERT fitting with training-only checkpoint/threshold selection."""

import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import math
from pathlib import Path
import signal
from time import perf_counter

import numpy as np
import pandas as pd
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer, get_linear_schedule_with_warmup

from nlp_pipeline import preprocess_text
from prepare_transformer_data import validate_supplement
from training_policy import select_alert_threshold
from transformer_batches import batch_arrays, binary_scores


ROOT = Path(__file__).resolve().parent
MODEL = "distilbert/distilbert-base-uncased"
REVISION = "12040accade4e8a0f71eabdb258fecc2e7e948be"
STOP_REQUESTED = False


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    partial = path.with_suffix(path.suffix + ".partial")
    partial.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    partial.replace(path)


def encode_frame(tokenizer, frame, max_length):
    encoded = tokenizer(frame["text"].tolist(), padding="max_length", truncation=True,
                        max_length=max_length, return_tensors="np")
    return (encoded["input_ids"].astype(np.int32), encoded["attention_mask"].astype(np.int8),
            frame["label"].to_numpy(dtype=np.int64))


def tensors(arrays, indices, device):
    return {key: torch.from_numpy(value).to(device) for key, value in batch_arrays(*arrays, indices).items()}


def probabilities(model, arrays, device, batch_size=8):
    model.eval()
    scores = []
    with torch.inference_mode():
        for first in range(0, len(arrays[2]), batch_size):
            batch = tensors(arrays, np.arange(first, min(first+batch_size, len(arrays[2]))), device)
            batch.pop("labels")
            scores.extend(torch.softmax(model(**batch).logits, dim=-1)[:, 1].cpu().tolist())
    return np.asarray(scores)


def limit_stratified(frame, count, seed):
    if not count or len(frame) <= count:
        return frame
    from sklearn.model_selection import train_test_split
    selected, _ = train_test_split(frame, train_size=count, stratify=frame["label"], random_state=seed)
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data/transformer")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/DistilBERT_candidate")
    parser.add_argument("--results", type=Path, default=ROOT / "results/transformer/distilbert_run01")
    parser.add_argument("--device", choices=("mps", "cpu"), default="mps")
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--accumulation", type=int, default=8)
    parser.add_argument("--max-length", type=int, default=128)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--supplement-repeat", type=int, default=32)
    parser.add_argument("--limit-train", type=int, default=0)
    parser.add_argument("--limit-validation", type=int, default=0)
    parser.add_argument("--max-updates", type=int, default=0)
    parser.add_argument("--checkpoint-every", type=int, default=100)
    parser.add_argument("--log-every", type=int, default=10)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if min(args.epochs, args.batch_size, args.accumulation, args.checkpoint_every, args.log_every) <= 0:
        raise ValueError("Training counts must be positive")
    if args.device == "mps" and not torch.backends.mps.is_available():
        raise RuntimeError("MPS is unavailable; no automatic silent CPU fallback")
    args.output.mkdir(exist_ok=True, parents=True)
    args.results.mkdir(exist_ok=True, parents=True)
    checkpoint = args.output / "training_checkpoint.pt"
    if checkpoint.exists() and not args.resume:
        raise ValueError("Existing checkpoint found; use --resume or a new output directory")
    torch.set_num_threads(4)
    torch.manual_seed(1842)
    if args.device == "mps":
        torch.mps.set_per_process_memory_fraction(.65)
    device = torch.device(args.device)

    manifest = json.loads((args.data / "manifest.json").read_text())
    for name in ("fit", "validation"):
        if hashlib.sha256((args.data / f"{name}.jsonl").read_bytes()).hexdigest() != manifest["parts"][name]["sha256"]:
            raise ValueError(f"Partition checksum mismatch: {name}")
    fit = limit_stratified(pd.read_json(args.data / "fit.jsonl", lines=True), args.limit_train, 1842)
    validation = limit_stratified(pd.read_json(args.data / "validation.jsonl", lines=True), args.limit_validation, 1843)
    natural_fit_count = len(fit)
    supplement_file = ROOT / "data/attack_training_supplement.json"
    supplement = json.loads(supplement_file.read_text())
    audit = json.loads((ROOT / "data/attack_stress.json").read_text())
    blocked = {preprocess_text(c["text"]) for c in audit["cases"]}
    # Only text is read to reject overlap, never test labels or predictions for fitting/selection.
    reserved_text = pd.read_json(args.data / "test.jsonl", lines=True)["text"]
    blocked.update(map(preprocess_text, reserved_text))
    blocked.update(map(preprocess_text, validation["text"]))
    extra = validate_supplement(supplement["cases"], blocked)
    if args.supplement_repeat:
        supplemental = pd.DataFrame(extra)[["text", "label"]]
        supplemental["rev_id"] = -np.arange(1, len(supplemental)+1)
        fit = pd.concat([fit, *[supplemental]*args.supplement_repeat], ignore_index=True)
    configuration = {
        "model": MODEL, "revision": REVISION, "seed": 1842, "device": args.device,
        "epochs": args.epochs, "batch_size": args.batch_size, "gradient_accumulation": args.accumulation,
        "max_length": args.max_length, "learning_rate": args.learning_rate, "weight_decay": .01,
        "natural_fitting_comments": natural_fit_count, "validation_comments": len(validation),
        "supplement_unique_cases": len(extra), "supplement_repeat": args.supplement_repeat,
        "training_presentations_per_epoch": len(fit), "precision": "float32",
        "supplement_provenance": supplement["provenance"],
        "supplement_sha256": hashlib.sha256(supplement_file.read_bytes()).hexdigest(),
        "partitions": manifest["parts"],
        "packages": {name: version(name) for name in ("torch", "transformers", "numpy", "scikit-learn")},
        "evaluation_scope": "Checkpoint and threshold use original-training validation only. Existing authored audits are regression data. No natural audio accuracy established.",
    }
    write_json(args.results / "configuration.json", configuration)
    print("Training configuration:", json.dumps({k: configuration[k] for k in (
        "device", "natural_fitting_comments", "validation_comments", "supplement_unique_cases", "supplement_repeat", "epochs"
    )}), flush=True)
    tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=REVISION, local_files_only=True)
    print("Tokenizing fitting and validation text...", flush=True)
    train_arrays = encode_frame(tokenizer, fit, args.max_length)
    val_arrays = encode_frame(tokenizer, validation, args.max_length)
    del fit
    model = AutoModelForSequenceClassification.from_pretrained(MODEL, revision=REVISION, num_labels=2, local_files_only=True).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=.01, foreach=False)
    batches_per_epoch = math.ceil(len(train_arrays[2]) / args.batch_size)
    planned_updates = math.ceil(batches_per_epoch / args.accumulation) * args.epochs
    schedule = get_linear_schedule_with_warmup(optimizer, max(1, int(planned_updates*.05)), planned_updates)
    epoch_start, batch_start, updates, best_score, history = 0, 0, 0, -1.0, []
    checkpoint_epoch, checkpoint_batch = 0, 0
    if args.resume:
        state = torch.load(checkpoint, map_location="cpu", weights_only=True)
        if state["configuration"] != configuration:
            raise ValueError("Resume configuration differs from the saved training run")
        model.load_state_dict(state["model"])
        optimizer.load_state_dict(state["optimizer"])
        schedule.load_state_dict(state["schedule"])
        epoch_start, batch_start, updates = state["epoch"], state["batch"], state["updates"]
        best_score, history = state["best_score"], state["history"]
        torch.set_rng_state(state["torch_rng"])
        if args.device == "mps":
            torch.mps.set_rng_state(state["mps_rng"])
        del state
        print(f"Resumed at epoch {epoch_start+1}, batch {batch_start}, update {updates}", flush=True)

    def save_checkpoint(epoch, next_batch):
        if args.device == "mps":
            torch.mps.synchronize()
        state = {"model": model.state_dict(), "optimizer": optimizer.state_dict(), "schedule": schedule.state_dict(),
                 "epoch": epoch, "batch": next_batch, "updates": updates, "best_score": best_score,
                 "history": history, "configuration": configuration, "torch_rng": torch.get_rng_state()}
        if args.device == "mps":
            state["mps_rng"] = torch.mps.get_rng_state()
        partial = checkpoint.with_suffix(".partial")
        torch.save(state, partial)
        partial.replace(checkpoint)

    def request_stop(signum, frame):
        global STOP_REQUESTED
        STOP_REQUESTED = True
        print("Stop requested; saving at the next optimizer boundary.", flush=True)

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    started = perf_counter()
    log_path = args.results / "training_log.jsonl"
    optimizer.zero_grad(set_to_none=True)
    for epoch in range(epoch_start, args.epochs):
        model.train()
        order = np.random.default_rng(1842+epoch).permutation(len(train_arrays[2]))
        first_batch = batch_start if epoch == epoch_start else 0
        accumulated_losses = []
        for batch_number in range(first_batch, batches_per_epoch):
            indices = order[batch_number*args.batch_size:(batch_number+1)*args.batch_size]
            batch = tensors(train_arrays, indices, device)
            output = model(**batch)
            if not torch.isfinite(output.loss):
                raise RuntimeError("Nonfinite training loss; last durable checkpoint preserved")
            # Last accumulation group may contain fewer micro-batches.
            group_first = (batch_number // args.accumulation) * args.accumulation
            group_size = min(args.accumulation, batches_per_epoch-group_first)
            (output.loss / group_size).backward()
            accumulated_losses.append(float(output.loss.detach().cpu()))
            if (batch_number+1) % args.accumulation and batch_number+1 != batches_per_epoch:
                continue
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0, foreach=False)
            optimizer.step()
            schedule.step()
            optimizer.zero_grad(set_to_none=True)
            updates += 1
            checkpoint_epoch, checkpoint_batch = epoch, batch_number+1
            if updates % args.log_every == 0 or updates == 1:
                elapsed = perf_counter()-started
                record = {"time": timestamp(), "epoch": epoch+1, "batch": batch_number+1,
                          "batches_per_epoch": batches_per_epoch, "update": updates,
                          "loss": float(np.mean(accumulated_losses)), "elapsed_seconds": elapsed,
                          "learning_rate": schedule.get_last_lr()[0]}
                with log_path.open("a") as stream:
                    stream.write(json.dumps(record)+"\n")
                write_json(args.results / "status.json", {"state": "training", **record})
                print(f"Epoch {epoch+1}/{args.epochs} | batch {batch_number+1}/{batches_per_epoch} | update {updates} | loss {record['loss']:.4f} | {elapsed/60:.1f} min", flush=True)
                accumulated_losses = []
            if updates % args.checkpoint_every == 0 or STOP_REQUESTED or (args.max_updates and updates >= args.max_updates):
                save_checkpoint(epoch, batch_number+1)
            if STOP_REQUESTED or (args.max_updates and updates >= args.max_updates):
                write_json(args.results / "status.json", {"state": "interrupted" if STOP_REQUESTED else "smoke_complete",
                           "time": timestamp(), "epoch": epoch+1, "update": updates, "saved_checkpoint": str(checkpoint)})
                print("Stopped with durable checkpoint:", checkpoint, flush=True)
                return
        print(f"Epoch {epoch+1}: evaluating {len(validation):,} training-validation comments...", flush=True)
        scores = probabilities(model, val_arrays, device, batch_size=8)
        metrics = binary_scores(val_arrays[2], scores)
        history.append({"epoch": epoch+1, "update": updates, **metrics})
        write_json(args.results / "epoch_history.json", history)
        print("Validation:", json.dumps(metrics), flush=True)
        if metrics["macro_f1"] > best_score:
            best_score = metrics["macro_f1"]
            model.save_pretrained(args.output / "best", safe_serialization=True)
            tokenizer.save_pretrained(args.output / "best")
        save_checkpoint(epoch+1, 0)
        if args.device == "mps":
            torch.mps.empty_cache()
    del optimizer, schedule, model
    if args.device == "mps":
        torch.mps.empty_cache()
    best = AutoModelForSequenceClassification.from_pretrained(args.output / "best", local_files_only=True).to(device)
    scores = probabilities(best, val_arrays, device, batch_size=8)
    policy = select_alert_threshold(val_arrays[2], scores, minimum_alerts=min(100, max(1, int(val_arrays[2].sum()/4))))
    policy.update({"model_directory": str(args.output / "best"), "max_length": args.max_length,
                   "probability_type": "Uncalibrated softmax; validation-selected decision threshold",
                   "training_configuration": str(args.results / "configuration.json")})
    write_json(args.output / "alert_policy.json", policy)
    write_json(args.results / "validation_metrics.json", binary_scores(val_arrays[2], scores, policy["threshold"]))
    validation.assign(attack_probability=scores, prediction=(scores >= policy["threshold"]).astype(int)).to_csv(args.results / "validation_predictions.csv", index=False)
    write_json(args.results / "status.json", {"state": "complete", "time": timestamp(), "updates": updates,
               "elapsed_seconds_this_process": perf_counter()-started, "best_validation_macro_f1_at_half": best_score,
               "policy": policy})
    print("Training complete. Saved model, tokenizer, validation predictions and threshold.", flush=True)


if __name__ == "__main__":
    main()
