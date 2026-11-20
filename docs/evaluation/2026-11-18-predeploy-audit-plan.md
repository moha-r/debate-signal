# Argument quality and deployment-readiness audit

## Material Passport

- Scope: current application behavior, English two-speaker dialogue, argument-role extraction, tentative links, question tracking, operational readiness.
- Authority: user requested testing before deployment; no public deployment or use of real user credentials is included.
- Evidence: frozen synthetic dialogue fixtures, a pinned externally annotated corpus if available, existing diagnostics, temporary-database API/WebSocket tests, reproducible timings and source hashes.
- Limit: assistant-authored fixtures are not independently annotated or blind validation. External written argument texts differ from natural spoken debates. No universal accuracy or fairness claims.

## Protocol

1. Freeze new dialogue references before running predictions. Cover explicit/implicit rebuttals, support, agreement, questions, denials, quotations, non-arguments, multiple candidate targets, unrelated turns, delayed answers and bounded context.
2. Measure role macro F1 and class recall, acceptable-role accuracy, exact source-link precision/recall, false links on no-link cases, evidence-request accuracy and question-to-answer associations. Report denominators and ambiguous/excluded cases explicitly.
3. Isolate argument extraction with known topic/attack labels, then replay the full serving wrapper to expose upstream errors. Do not silently substitute oracle labels for end-to-end results.
4. If external data is accessible, preserve its commit/checksum, license and mapping rules. Evaluate its argument-role mapping separately; never describe monologic written data as a natural conversation benchmark. Exclude corpus files and text excerpts from distributed outputs unless needed and licensed.
5. Run the existing test suite. Add focused tests for demonstrated deployment failures, particularly authenticated HTTPS/WSS, origin validation, persistence after restart, ownership across cached and restored debates, and long sessions. Use temporary databases and a local speech-provider fixture.
6. Measure full wrapper wall time separately from the turn's reported latency. Confirm local builds and runtime dependency assumptions. Do not access private transcript contents or create accounts in the live database.
7. Freeze baseline outputs before any fixes. Concrete operational defects may be repaired with regression tests; keep baseline and revised results separate. Do not tune language rules on this audit and call the result independent validation.
8. Deliver an Arabic assessment with strengths, concrete counterexamples, outstanding blockers and a recommendation distinguishing a limited research demo from broader public use.

No visual QA. No subagents. No cloud publication in this audit.
