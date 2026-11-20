# Argument quality repair

User approved fixing the audited issues. Execute locally without subagents or visual QA.

## Design

Use a context-aware role/relation component with explicit abstention, plus an independent question tracker. Prefer a locally trained lightweight classifier on frozen MiniLM representations and annotated argument data. Keep clear linguistic handling for direct questions, quotation scope, negation and non-arguments; do not claim those safeguards are learned inference. Preserve source-turn provenance, and provide explicit link types instead of inferring them from the source role in the UI.

## Work

- Freeze a new challenge before evaluating candidates. Preserve the 104-turn previous audit as regression data, not fresh independent validation.
- Partition external data by whole document before fitting, use training/development only for model/threshold selection, and report genre/mapping limits and any authored training supplements. Do not fit the previous audit text.
- Add failing contracts for quoted questions, implicit requests, negative agreement, same-speaker rebuttals, wrong-target links, delayed answers, refusals/insufficient evidence, and correcting argument annotations.
- Add training and inference modules with saved artifacts, source hashes, data/split manifests and measured CPU latency. Compare candidate role and relation models on development data.
- Separate question references from argument links. Maintain open questions beyond six turns, distinguish tentative answers from refusals and insufficient evidence, and preserve original source IDs.
- Integrate typed links, confidence/abstention and optional human corrections into session persistence/API/export/frontend. Keep old saved sessions readable and expose annotation provenance.
- Add explicit finite audio-duration/concurrency limits for the shared service key before a public demo. Keep actual publication out of scope.
- Run meaningful contracts, prior/new linguistic diagnostics, external document-held-out diagnostics, production builds and an authenticated real-model workflow in a temporary DB. Do not rewrite baseline results or present targeted rule repairs as independent accuracy.
- Document remaining limitations honestly; use evidence to choose the serving candidate rather than a promised accuracy target.

## Execution outcome

Implemented local role/relation classifiers, development-only confidence gates, independent long-range question tracking, typed links, manual owner-only revision-checked role/target corrections with original annotations preserved, and bounded voice duration/concurrency. Reproducible corpus preparation, source/license notice, document splits and training manifest are saved.

Verification: 105 functional tests and both production builds pass. The real-model authenticated HTTP/temporary SQLite workflow passes. Previous audit and frozen new challenge are evaluated separately; all previous results remain intact. No subagents, visual tests or public deployment.

Quality caveat: the known 104-turn regression improves roles and displayed-link precision but loses recall/F1; the new 44-turn challenge remains weak at target selection. General semantic quality is still unresolved. Serving remains an explicitly tentative human-reviewed course prototype. Read reports/argument_quality_repair_ar.md before making deployment or accuracy claims.
