"""Save measured candidate comparisons as figures and an executed notebook."""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import nbformat
from nbclient import NotebookClient
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
RUN = ROOT / "results/transformer/distilbert_run02"
EVAL = RUN / "evaluation"
FIGURES = ROOT / "reports/figures"
TOPIC = ROOT / "results/contextual_topic"


def read(path):
    return json.loads(path.read_text())


def save(figure, name):
    figure.tight_layout()
    for extension in ("png", "svg", "pdf"):
        figure.savefig(FIGURES / f"{name}.{extension}", dpi=300, bbox_inches="tight")
    plt.close(figure)


def paired_plot(data, keys, labels, title, axis, name, percent=False):
    figure, axes = plt.subplots(figsize=(8, 4.4))
    positions = np.arange(len(keys))
    for index, (label, metrics) in enumerate(data.items()):
        values = [metrics[key] * (100 if percent else 1) for key in keys]
        bars = axes.bar(positions + (index - .5) * .35, values, width=.35,
                        color=["#315a8b", "#15847e"][index], label=label)
        axes.bar_label(bars, fmt="%.1f" if percent else "%d", padding=4)
    axes.set_xticks(positions, labels)
    axes.set(ylabel=axis, title=title)
    axes.set_ylim(0, 115 if percent else max(1, axes.get_ylim()[1] * 1.24))
    axes.legend(loc="upper center", bbox_to_anchor=(.5, 1), frameon=False, ncols=2)
    save(figure, name)


def main():
    summary = read(EVAL / "summary.json")
    topic = read(TOPIC / "summary.json")
    FIGURES.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "svg.fonttype": "none", "pdf.fonttype": 42})
    paired_plot(summary["wiki_test"], ["attack_precision", "attack_recall", "macro_f1"],
                ["Attack precision", "Attack recall", "Macro F1"], "WikiDetox test · 22,921 comments",
                "Score (%)", "distilbert_wikidetox_comparison", percent=True)
    paired_plot(summary["authored_regression"], ["fp", "fn"], ["False alerts", "Missed attacks"],
                "Authored attack regression · 168 clear cases", "Count", "distilbert_regression_errors")
    paired_plot(topic["expanded_regression"], ["detected", "false_alerts"], ["Detected drift episodes", "False alerts"],
                "Authored topic regression · 18 drift episodes", "Count", "bounded_topic_comparison")
    log = pd.read_json(RUN / "training_log.jsonl", lines=True)
    figure, axes = plt.subplots(figsize=(8, 4.4))
    axes.plot(log["update"], log["loss"], linewidth=.7, color="#a8c0d7", label="Logged mean loss")
    axes.plot(log["update"], log["loss"].rolling(20, min_periods=1).median(), linewidth=2,
              color="#315a8b", label="20-point rolling median")
    axes.axvline(log.loc[log.epoch == 1, "update"].max(), color="#15847e", linestyle="--", label="End of epoch 1")
    axes.set(xlabel="Optimizer updates", ylabel="Cross-entropy loss", title="DistilBERT fine-tuning on Apple M1")
    axes.legend(frameon=False)
    save(figure, "distilbert_training_loss")

    markdown = nbformat.v4.new_markdown_cell
    code = nbformat.v4.new_code_cell
    cells = [
        markdown("# DistilBERT local training and evaluation\n\nThe model trained on Apple M1 with MPS. This notebook displays the saved outputs of the training and evaluation scripts. Validation selected the checkpoint, scoring mode and alert threshold. WikiDetox supplies the original human-labeled test. The project assistant authored the attack and topic regression cases. Spoken dialogue and independent dialogue labels remain pending."),
        code("""from pathlib import Path
import json
import pandas as pd
from IPython.display import display, Image

ROOT = Path.cwd() if (Path.cwd() / 'results/transformer').is_dir() else Path.cwd().parent
run = ROOT / 'results/transformer/distilbert_run02'
read = lambda path: json.loads(path.read_text())
config = read(run / 'configuration.json')
status = read(run / 'status.json')
summary = read(run / 'evaluation/summary.json')
topic = read(ROOT / 'results/contextual_topic/summary.json')
print(f"Completed {config['epochs']} epochs on {config['device'].upper()}, {status['updates']:,} optimizer updates")
print(f"Elapsed: {status['elapsed_seconds_this_process']/60:.1f} minutes")
display(pd.DataFrame(config['partitions']).T[['rows','attacks']])
display(pd.DataFrame(read(run / 'epoch_history.json'))[['epoch','attack_precision','attack_recall','macro_f1']])
display(Image(filename=str(ROOT / 'reports/figures/distilbert_training_loss.png'), width=850))"""),
        markdown("## Validation and original test"),
        code("""policy = summary['inference_policy']
print(f"Selected {policy['mode']} scoring, threshold {policy['threshold']:.2f}")
display(pd.DataFrame(policy['validation_options']).T[['threshold','precision','recall','macro_f1']])
columns = ['accuracy','attack_precision','attack_recall','macro_f1','brier','fp','fn']
display(pd.DataFrame(summary['wiki_test']).T[columns].round(4))
display(Image(filename=str(ROOT / 'reports/figures/distilbert_wikidetox_comparison.png'), width=850))"""),
        markdown("## Authored regression cases and local CPU timing"),
        code("""display(pd.DataFrame(summary['authored_regression']).T[columns].round(4))
categories = pd.read_csv(run / 'evaluation/stress_categories.csv')
display(categories.pivot(index='category', columns='model', values=['fp','fn']))
display(pd.DataFrame(summary['cpu_single_turn_latency']).T)
display(pd.Series(summary['adoption_checks']))
display(Image(filename=str(ROOT / 'reports/figures/distilbert_regression_errors.png'), width=850))"""),
        markdown("## Topic context comparison"),
        code("""print(topic['policy']['settings'])
for partition in ('original_reserved','challenge','expanded_regression'):
    print(partition)
    display(pd.DataFrame(topic[partition]).T[['events','detected','false_alerts','event_f1','turn_macro_f1']].round(4))
display(Image(filename=str(ROOT / 'reports/figures/bounded_topic_comparison.png'), width=850))"""),
    ]
    document = nbformat.v4.new_notebook(cells=cells, metadata={
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    })
    NotebookClient(document, timeout=120, kernel_name="python3",
                   resources={"metadata": {"path": str(ROOT)}}).execute()
    nbformat.write(document, ROOT / "notebooks/train_distilbert.ipynb")
    print("Saved executed comparison notebook and four figures in PNG, SVG and PDF.")


if __name__ == "__main__":
    main()
