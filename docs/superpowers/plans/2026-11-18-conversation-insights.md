# Conversation insights implementation

Approved scope: recent-turn context, an inspectable argument map, measured participation, a source-linked session report, and explicit moderator feedback.

1. Add deterministic insight extraction and timing aggregation with regression tests. Argument roles and semantic links are tentative suggestions, never factual verification or a trained argument classifier. Preserve raw detector scores.
2. Apply bounded context only to short follow-up questions using directly topical recent turns. Do not deploy the previous broad context candidate, whose challenge event recall regressed. Add narrowly scoped quotation handling and test direct insults remain detectable.
3. Persist sessions and feedback in local SQLite. Keep review workflow separate from correct/incorrect labels. Export feedback with context and detector provenance for later supervised training.
4. Carry finalized AssemblyAI word timestamps and a recording identifier through the gateway. Union speech intervals per speaker and recording; report missing timing explicitly. Recompute when attribution changes. Dominance is a configurable advisory after 30 measured seconds and two confirmed voices.
5. Add live participation and argument views, a source-linked report and feedback controls matching the approved visual direction. Include report and corrections in exports.
6. Verify backend contracts, existing linguistic regressions, frontend build, and browser flows. Keep existing sessions before restarting the local service.

Report questions remain “answer not linked” unless a likely substantive reply is linked. Referenced evidence is unverified. Agreement requires explicit language; no winner or truth scores. New extraction quality requires an independently annotated evaluation before accuracy claims.
