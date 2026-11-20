"""Measure real DistilBERT forward/backward steps on local Apple Silicon."""

import argparse
from importlib.metadata import version
import json
from pathlib import Path
import platform
from time import perf_counter

import numpy as np
import torch
from huggingface_hub import model_info
from transformers import AutoModelForSequenceClassification, AutoTokenizer


MODEL = "distilbert/distilbert-base-uncased"
ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--max-length", type=int, default=128)
    parser.add_argument("--steps", type=int, default=6)
    args = parser.parse_args()
    if not torch.backends.mps.is_available():
        raise RuntimeError("The requested local benchmark requires an available MPS device")
    torch.manual_seed(1842)
    torch.set_num_threads(4)
    torch.mps.set_per_process_memory_fraction(.65)
    revision = model_info(MODEL).sha
    print("Loading", MODEL, revision, "on MPS", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=revision)
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL, revision=revision, num_labels=2
    ).to("mps")
    model.train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-5, foreach=False)
    texts = [
        "The proposed transport policy needs a more detailed funding estimate. I disagree with the conclusion because it omits operating costs.",
        "You are a dishonest idiot and you cannot understand even the simplest question about this proposal.",
        "I do not think you are stupid. We are interpreting the figures differently and should check the original source.",
        "With all due respect, you have nothing between your ears and you are wasting our time.",
    ]
    texts = [texts[i % len(texts)] for i in range(args.batch_size)]
    inputs = tokenizer(texts, padding="max_length", truncation=True,
                       max_length=args.max_length, return_tensors="pt").to("mps")
    labels = torch.tensor([i % 2 for i in range(args.batch_size)], device="mps")
    timings, losses = [], []
    for step in range(args.steps + 2):
        torch.mps.synchronize()
        start = perf_counter()
        optimizer.zero_grad(set_to_none=True)
        loss = model(**inputs, labels=labels).loss
        if not torch.isfinite(loss):
            raise RuntimeError("Nonfinite benchmark loss")
        loss.backward()
        optimizer.step()
        torch.mps.synchronize()
        elapsed = perf_counter() - start
        if step >= 2:
            timings.append(elapsed)
            losses.append(float(loss.detach().cpu()))
        print(f"Step {step + 1}/{args.steps + 2}: {elapsed:.3f}s, loss {float(loss.detach().cpu()):.4f}", flush=True)
    report = {
        "machine": platform.machine(), "macOS": platform.mac_ver()[0],
        "device": "mps", "model": MODEL, "revision": revision,
        "batch_size": args.batch_size, "padded_max_length": args.max_length,
        "precision": "float32", "trainable_parameters": sum(p.numel() for p in model.parameters() if p.requires_grad),
        "measured_steps": len(timings), "warmup_steps": 2,
        "median_step_seconds": float(np.median(timings)),
        "p95_step_seconds": float(np.percentile(timings, 95)),
        "examples_per_second": float(args.batch_size / np.median(timings)),
        "mps_tensor_memory_GiB": torch.mps.current_allocated_memory() / 2**30,
        "mps_driver_memory_GiB": torch.mps.driver_allocated_memory() / 2**30,
        "mps_recommended_memory_GiB": torch.mps.recommended_max_memory() / 2**30,
        "losses": losses,
        "packages": {name: version(name) for name in ("torch", "transformers", "numpy")},
        "scope": "Synthetic repeated batches measure feasibility and approximate throughput, not accuracy. Excludes data preparation, tokenization, validation, checkpoint I/O and prolonged memory/thermal effects. Benchmark weights are discarded.",
    }
    manifest_path = ROOT / "data/transformer/manifest.json"
    if manifest_path.exists():
        rows = json.loads(manifest_path.read_text())["parts"]["fit"]["rows"]
        report["fit_rows"] = rows
        report["estimated_training_only_minutes_per_epoch"] = rows / report["examples_per_second"] / 60
    destination = ROOT / "results/transformer"
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "local_hardware_benchmark.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
