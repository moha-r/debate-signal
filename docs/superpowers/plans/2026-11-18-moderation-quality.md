# Moderator quality improvement implementation plan

> Execute inline using executing-plans. The user explicitly requested no subagents and approved the proposed improvement design. Keep all work in the existing workspace on `codex/moderation-quality`; the repository has no initial commit, so creating a worktree would not preserve its untracked project files.

**Goal:** Improve personal-attack detection and contextual relevance without hiding regressions or contaminating evaluation.

**Architecture:** Reproduce the original WikiDetox outer split, reserve training-only validation and calibrate any new operating point there. Fine-tune pretrained DistilBERT on readable text and clearly marked authored training supplements, keeping audit cases out of fitting. Compare windowed and whole-turn inference, then improve topic context using development sessions only. Preserve the current serving models until a measured candidate passes the adoption criteria.

**Tech stack:** Python, PyTorch, Hugging Face Transformers, scikit-learn, existing Gradio session wrapper; Colab T4 if accessible. No external messages, publication or paid compute.

**User update:** Continue locally on the user's M1, saving executed notebook outputs and standalone figures. A real MPS forward/backward availability check passed. Measure a DistilBERT step before fixing the local run size; cloud T4 is available but the user prefers local command control. Local execution is not presumed faster than T4.

## Task 1 — Reproducible preparation and training boundaries

- [x] Create `prepare_transformer_data.py` and `tests/test_transformer_data.py`.
- [x] Test that normalization preserves negation, punctuation and quoted speech, restores export separators and excludes exact audit inputs from supplemental training. Seven data contracts passed after the expected initial missing-module failure.
- [x] Verify checksums for Figshare files 7554634 and 7554637. Recreate strict-majority labels and the original deduplication using `nlp_pipeline.preprocess_text`.
- [x] Assert the outer test revision IDs exactly equal `results/heldout_predictions.csv` (22,921 rows). One original training row matching an audit input was excluded. The remaining data produced 82,513 fitting and 9,169 validation rows with stratification and seed 1842.
- [x] Reserve original test comments and all authored audit cases from gradient updates and threshold selection. Save partition manifests, checksums and counts under `results/transformer/`.

## Task 2 — DistilBERT fine-tuning

- [x] Create `train_distilbert.py`, `requirements-training.txt` and `notebooks/train_distilbert.ipynb`.
- [x] Train from the pinned `distilbert/distilbert-base-uncased` revision with readable inputs. Record the tokenizer and two labels.
- [x] Use training-only validation for checkpoint and threshold selection. Train for two epochs using length-grouped batches, max length 128, learning rate 2e-5, weight decay .01, batch 4, gradient accumulation 8, seed 1842 and float32 on MPS.
- [x] Verify checkpoint resume in a small run. Save model/tokenizer, evaluation predictions, threshold and package versions.
- [x] Train and evaluate locally. The completed MPS run made 5,350 updates and took 116.5 minutes including validation and saving.

## Task 3 — Quality and latency comparison

- [x] Evaluate the locked candidate on the original outer test of 22,921 comments and the 168 clear authored attack regression cases.
- [x] Compare precision, recall, macro F1, Brier score, error counts and warm CPU/MPS inference latency.
- [x] Compare the first 128 tokens with overlapping 96-token windows on the validation set. Select the first-128-token approach at threshold .30.
- [x] Review the trade-off. WikiDetox recall rose from 74.1% to 83.3% and macro F1 from .871 to .891. Trial precision fell from 80.4% to 78.4%, so the app uses LinearSVC. The authored regression showed 5 versus 14 false alerts and 7 versus 19 missed attacks for DistilBERT versus LinearSVC.

## Task 4 — Contextual topic monitor

- [x] Add tests for an acknowledgement between a directly relevant turn and a short topical follow-up, with anchors that expire and cannot renew from inherited relevance.
- [x] Select bounded context from 2–4 turns on four development conversations. Compare the frozen settings on the original reserved, challenge and expanded regression sets.
- [x] Record turn and episode errors. The selected candidate reduced false notifications from two to one on the expanded regression but caught 16 rather than 17 of 18 periods. It caught two rather than three of four periods on the challenge set. The app uses the established topic policy.
- [ ] Evaluate a trained pair classifier when independent dialogue annotations are available to support training and comparison.

## Task 5 — Final validation and documentation

- [x] Run the app and candidate unit suites together. All 47 tests pass.
- [x] Save row-level predictions, data provenance, model checksum, executed notebook outputs and an Arabic comparison report in `reports/distilbert_local_evaluation.md`.
- [x] Record the evaluation scope. Independent human dialogue labels and natural audio testing remain pending.
- [x] Update README and the project plan with measurements and serving model choices. The historical audit still matches all 11 recorded file hashes.

## Local preflight evidence

- MPS arithmetic and backward check passed. The actual pretrained DistilBERT benchmark completed two warm-up and six measured full-parameter update steps with batch 4 / padded length 128. Median step 0.246 s; about 16.3 examples/s; Metal driver memory about 2.17 GiB. Benchmark weights were discarded.
- The short measurement extrapolates to about 85 training-only minutes per full fitting-data epoch. It excludes validation, tokenization, saving and sustained-load effects. No new accuracy claim follows from it.
- Seven data-boundary tests and four threshold-policy tests passed; all 38 current tests passed together. Historical expanded-audit evidence remains intact.
- `notebooks/local_training_workspace.ipynb` was executed locally with six code cells and five embedded figures. `reports/figures/` has five figures in PNG (300 dpi), SVG and PDF. PDFs were rendered and visually reviewed. These outputs are saved locally, without automatic Drive synchronization.
- Final training and evaluation results are recorded above.
