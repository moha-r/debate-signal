"""Export figures from measured results; never substitutes a benchmark for quality."""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "reports/figures"


def save(fig, name):
    fig.tight_layout()
    for extension in ("png", "svg", "pdf"):
        fig.savefig(OUT / f"{name}.{extension}", dpi=300, bbox_inches="tight")
    plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "svg.fonttype": "none", "pdf.fonttype": 42})
    colours = ["#315a8b", "#15847e", "#b24f65"]
    manifest = json.loads((ROOT / "results/transformer/data_manifest.json").read_text())
    parts = manifest["parts"]
    fig, ax = plt.subplots(figsize=(7.0, 4.1))
    names = ["Fitting", "Validation", "Original test"]
    counts = [parts[k]["rows"] for k in ("fit", "validation", "test")]
    bars = ax.bar(names, counts, color=colours, width=.55)
    ax.bar_label(bars, labels=[f"{n:,}" for n in counts], padding=5)
    ax.set(ylim=(0, 100_000), ylabel="Comments", title="Transformer candidate: preserved data boundaries")
    ax.text(.01, -.22, "One original training comment matching an audit input was excluded.\nTest comments are reserved from fitting and threshold selection.", transform=ax.transAxes, fontsize=8, color="#52617d")
    save(fig, "transformer_data_partitions")

    metrics = pd.read_csv(ROOT / "results/heldout_metrics.csv")
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    x = np.arange(len(metrics))
    for offset, key, label, colour in ((-.18, "Accuracy", "Accuracy", colours[0]), (.18, "F1 (macro)", "Macro F1", colours[1])):
        bars = ax.bar(x+offset, metrics[key]*100, .34, label=label, color=colour)
        ax.bar_label(bars, fmt="%.1f", padding=4)
    ax.set_xticks(x, metrics["Model"])
    ax.set(ylim=(0, 110), ylabel="Score (%)", title="Existing classical models: original WikiDetox test")
    ax.legend(loc="upper right", frameon=False)
    ax.text(.01, -.17, "22,921 comments. These are the existing baseline results; DistilBERT is not evaluated here.", transform=ax.transAxes, fontsize=8, color="#52617d")
    save(fig, "existing_classical_model_comparison")

    categories = pd.read_csv(ROOT / "results/expanded_audit/attack_stress_categories.csv")
    categories = categories.assign(errors=categories.fp+categories.fn).sort_values("errors", ascending=True)
    fig, ax = plt.subplots(figsize=(8.2, 6.0))
    ax.barh(categories.category.str.replace("_", " "), categories.fp, color=colours[2], label="False alerts")
    ax.barh(categories.category.str.replace("_", " "), categories.fn, left=categories.fp, color=colours[0], label="Missed attacks")
    ax.set(xlabel="Errors (12 cases per category)", title="Current attack detector: authored stress diagnostic")
    ax.legend(frameon=False, loc="lower right")
    ax.text(.01, -.11, "168 clear authored cases; 12 ambiguous cases excluded. No independent human annotation.", transform=ax.transAxes, fontsize=8, color="#52617d")
    save(fig, "current_attack_stress_errors")

    topic = json.loads((ROOT / "results/expanded_audit/topic_stress_metrics.json").read_text())
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    values = [topic["detected"], topic["events"]-topic["detected"], topic["false_alerts"]]
    bars = ax.bar(["Detected episodes", "Missed episodes", "False alerts"], values, color=colours, width=.55)
    ax.bar_label(bars, padding=4)
    ax.set(ylim=(0, 20), ylabel="Count", title="Current topic monitor: authored conversation diagnostic")
    ax.text(.01, -.18, "24 conversations · 288 turns · 18 drift episodes.\nFalse alerts are separate from reference episodes. No natural audio evaluated.", transform=ax.transAxes, fontsize=8, color="#52617d")
    save(fig, "current_topic_episode_results")

    benchmark = json.loads((ROOT / "results/transformer/local_hardware_benchmark.json").read_text())
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    values = [benchmark["median_step_seconds"]*1000, benchmark["p95_step_seconds"]*1000]
    bars = ax.bar(["Median step", "P95 step"], values, color=colours[:2], width=.5)
    ax.bar_label(bars, labels=[f"{v:.0f} ms" for v in values], padding=5)
    ax.set(ylim=(0, max(values)*1.28), ylabel="Forward + backward + optimizer step (ms)",
           title="Local M1 / MPS: DistilBERT training feasibility")
    ax.text(.01, -.21, f"Batch {benchmark['batch_size']} · padded length {benchmark['padded_max_length']} · float32 · {benchmark['measured_steps']} measured steps after 2 warm-ups.\nSynthetic batches; measures speed and memory, not trained-model accuracy.", transform=ax.transAxes, fontsize=8, color="#52617d")
    save(fig, "local_mps_training_benchmark")
    print(f"Saved five measured-result figures as PNG (300 dpi), SVG and PDF in {OUT}")


if __name__ == "__main__":
    main()
