# Expanded evaluation before microphone integration

The user requested substantially broader accuracy and workflow tests, then explicitly requested that all work continue without subagents. No subagent-created files were present when that request arrived; all test data, evaluation and review below are performed by the primary assistant.

1. Freeze SHA-256 hashes of the saved models, topic policy and inference code. Do not tune or retrain against this audit.
2. Author a larger, labeled English stress diagnostic before computing its predictions: at least 160 attack utterances and 24 conversations. Cover stance disagreement, quoted abuse, negation, implicit abuse, lexical detours, short follow-ups, acknowledgement interruptions, isolated detours, returns and manually simulated transcript noise.
3. Re-audit the existing 22,921-comment WikiDetox test predictions, joining verified source text for length and language-feature slices. This reuses the existing test set; it is not an additional independent sample. Add confidence intervals and confusion counts.
4. Test stateful workflow contracts with deterministic test doubles and exercise the production session wrapper using real models. Measure warm text inference and a long-session workload separately from model quality.
5. Save row-level predictions, subgroup results, errors, diagnostic provenance, limitations, an executed evidence notebook and an Arabic findings report. Report failures; do not redefine labels or change thresholds to improve these scores.

Authored examples and manually perturbed text do not establish accuracy on natural speech. Human annotation and recorded conversations remain a separate validation step. Tests cannot guarantee every possible failure is absent.
