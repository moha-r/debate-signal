# Remaining dialogue-quality repairs

Keep the user-verified AssemblyAI transcription and UI design intact. No subagents or visual QA.

Root causes observed: written-microtext relation model has no accepted attack gate; long-range question matching ignores expected answer type and can mistake related scheduling statements for numerical answers. Existing role/link labels also conflate response speech acts with argumentative reasons.

1. Add failing contracts for expected quantitative answer types, delayed nonanswers, and explicit refusals. Repair only those demonstrated logic defects; preserve partial/uncertain response states.
2. Evaluate the pinned ARG Tech dialogue relation transformer against the current local model. Use M-Arg as an independently annotated diagnostic, never for fitting or threshold selection. Record label mapping, pair direction limitations, source/license, and actual device latency/memory. The already inspected 104/44-turn challenges are regression data from this point onward.
3. Adopt a candidate only with measured quality/runtime evidence; keep artifacts/results and the current version available. No claims based on the model card's accuracy. Integrate source provenance and bounded inference only if supported.
4. Run meaningful contracts and model diagnostics, update the report, and refresh the local service if serving code changes. No paid ASR calls are needed.

## Integration decision — 2026-11-20

Adopt the pinned RoBERTa dialogue pair checkpoint for tentative links, using the development-grid operating point with highest target-and-relation F1 (threshold .50, target margin .015). The earlier experimental precision >= .60 gate was an assistant-selected condition and yielded no candidate. Preserve that result in calibration.json and record the revised F1 objective in artifacts/dialogue_relation_policy.json. Quality still requires human review.

Use CPU inference, six retrieved candidates, 256 tokens, a serialized model load/inference path and a warmup during model preparation. A matched question response can skip argument-pair inference because its primary source is already the question. Every turn records its relation backend. Auto mode identifies fallback. Transformer mode fails clearly if the cached checkpoint is missing.

Specific repairs cover numerical question types, delayed topical nonanswers, refusals, and preserving the speech act of direct answers. No ASR configuration changes. Final checks and measurements are in results/dialogue_followup and the report reports/dialogue_quality_followup_ar.md.
