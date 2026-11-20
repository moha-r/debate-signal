# External diagnostic annotations

The `baseline/external_*.csv` and `revised/external_*.csv` diagnostics derive identifiers and mapped annotation labels from **An annotated corpus of argumentative microtexts**, Andreas Peldszus and Manfred Stede (2015).

- Source: https://github.com/peldszus/arg-microtexts
- Pinned commit: `6707c133de713130cabe647f2f218681d65fdc15`
- Source license: [Creative Commons Attribution-NonCommercial-ShareAlike 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/).
- The derived external-annotation tables are provided under that same license. The repository's original code and authored dialogue fixtures are separate materials.
- The original English texts are professionally translated written microtexts. They are not natural spoken conversations.
- Mapping changes: root ADUs become `claim`; `sup`/`exa` become `reason`; `reb`/`und` become `rebuttal`. Additional-premise and multi-edge cases are excluded. Proponent/opponent annotations become synthetic A/B labels for the selected sequential-link diagnostic. No real speaker identity is inferred.
- CSV outputs contain document IDs, ADU IDs, source-text hashes and predictions, without original corpus text. Raw corpus files remain in ignored `data/raw/arg-microtexts/` for reproducibility and are not serving or training inputs.

These results must not be presented as full original-corpus task scores, proof of spoken-dialogue accuracy, or independent human review of the assistant-authored dialogue fixtures.
