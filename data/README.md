# Topic relevance diagnostic

`topic_dialogues.json` contains 8 authored English conversations with 85 turns. The project assistant wrote the utterances and reference labels on 18 November 2026. Independent annotation and validation on natural recordings remain pending.

Each conversation has an explicit motion and speaker IDs A and B. Each turn has one of three labels.

| Label | Meaning |
|---|---|
| `on_topic` | Advances or questions the motion, including objections, relevant examples and short contextual follow-ups |
| `off_topic` | Introduces or continues a separate subject without explaining its relevance to the motion |
| `unclear` | Acknowledgement or insufficient content for a relevance judgment |

The development topics are school uniforms, free public buses, classroom phones and remote work. The reserved topics are tuition fees, nuclear electricity, protected bicycle lanes and homework limits. Development and test sessions have disjoint topics. The threshold grid is fixed before test scoring.

For event evaluation, two or more off-topic turns before a return to the motion form a drift episode. An intervening acknowledgement leaves the episode open. A single detour is recorded in the turn labels. An alert counts as correct when it occurs inside a sustained drift episode. Repeated alerts in that episode count as extra alerts. Detection delay is reported in turns from the first off-topic turn. Audio delay requires timed recordings.

The examples deliberately exercise short follow-ups, sustained detours, isolated detours and returns to the motion. A small authored diagnostic is sensitive to its writer's choices. Its results describe these examples and should be reported alongside their size and provenance.

Run `evaluate_topic_relevance.py` to compare a lexical TF-IDF baseline with MiniLM semantic similarity, select a threshold and context rule on development sessions, then score the reserved topics. The program saves the selected policy, development grid and per-turn test outputs under `results/`.

The first diagnostic selected MiniLM with short follow-up context and a similarity threshold of 0.15. It detected 2 of 3 sustained drift episodes in the four reserved sessions, with zero additional alerts. The missed bakery detour shared the street context of the bicycle-lane motion. Another unrelated comment about expensive headphones also scored as relevant to tuition fees after an alert had already fired. These are examples of semantic overlap causing errors.

topic_challenge.json adds six authored conversations with 60 turns. evaluate_topic_challenge.py scores the already selected policy without tuning it. It caught 3 of 4 sustained drift episodes. The smartphone-camera detour during the public-surveillance discussion was missed. The restaurant story initially appeared relevant to school meals, which delayed that episode's alert by one more turn. These examples have the same authorship and annotation limitations as the initial diagnostic.

## Expanded frozen-policy audit

`attack_stress.json` contains 180 authored utterances, including 168 clear cases balanced 84/84 across the two labels, and 12 ambiguous cases excluded from primary metrics. The clear cases span 14 categories. Some known probes are deliberately repeated as regressions. Context-dependent sarcasm has placeholder labels only; do not use it as primary ground truth.

`topic_stress.json` contains 24 authored conversations, each with 12 turns, for 288 turns total. Eight conversations are negative controls with no sustained drift; the remaining conversations contain 18 drift episodes. Opposing views, procedure, indirect references, acknowledgement interruptions, shared-keyword detours, repeated drift, same-speaker drift, long turns and manually transcript-like phrasing are covered. These labels were authored before computing predictions for this set. The author already knew the project design and previous findings; independent blind human annotation is still absent.

`evaluate_expanded_audit.py` applies the frozen models and topic policy. It creates 1,008 transformed variants from the 168 clear attack cases. They are paired variants rather than independent observations. Manually authored disfluency and punctuation loss are not actual ASR errors. No policy tuning is performed. After using these cases for improvements, treat them as regression data rather than a new independent final test.

Verified source comments for re-auditing the existing 22,921-comment holdout are cached under `data/raw/`. The file is Figshare v6 file 7554634, with MD5 `7e39135b410eaed85c7ffec85cf829fd`. The large raw download is excluded from Git; the audit script can fetch and verify it again.
