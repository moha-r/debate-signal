# DebateSignal

A moderator workspace for an English discussion between two participants, with a public introduction and individual moderator accounts. The moderator sets a motion and records the two automatically labeled voices. Suggested personal-attack and sustained topic-drift alerts, an argument trail, measured participation and a source-linked report support human review.

See [Run the debate dashboard](#run-the-debate-dashboard) to build and start the app. The repository includes the serving classifiers, evaluation reports and notebooks. The optional DistilBERT experiment checkpoint can be recreated with the training commands below.

## Local M1 training workspace

The local MPS availability check and actual DistilBERT forward/backward/optimizer benchmark passed. The short benchmark measured about 16.3 examples/second with batch 4, padded length 128 and float32, with about 2.17 GiB allocated by the Metal driver. Extrapolating that short measurement gives about 85 minutes per pass over the full 82,513-comment fitting pool, excluding validation, tokenization, saving and sustained-load effects. This is a feasibility estimate, not a completed fine-tuning run or an accuracy improvement.

`prepare_transformer_data.py` reproduced the original 22,921-comment test IDs and labels, excluded one original training input matching the authored audit, and saved 82,513 fitting plus 9,169 validation comments locally. The manifest is under `results/transformer/data_manifest.json`; regenerable text files under `data/transformer/` are excluded from Git.

DistilBERT completed two epochs on the local M1 in 116.5 minutes including validation and saving. On the original WikiDetox test, attack recall rose from 74.1% to 83.3% and macro F1 from 0.871 to 0.891. Alert precision fell from 80.4% to 78.4%, below the experiment's 80% adoption target. On the 168 clear authored dialogue cases, false alerts fell from 14 to 5 and missed attacks from 19 to 7. The app serves LinearSVC and the original topic policy. The trained DistilBERT weights and scored comparisons are saved locally.

The executed result notebook is `notebooks/train_distilbert.ipynb`. The Arabic findings are in `reports/distilbert_local_evaluation.md`. The standalone training and comparison figures are under `reports/figures/` as 300 dpi PNG, SVG and PDF. The earlier hardware and data evidence is in `notebooks/local_training_workspace.ipynb`.

    uv run --python 3.13 --with-requirements requirements-training.txt python prepare_transformer_data.py
    HF_HUB_DISABLE_XET=1 uv run --python 3.13 --with-requirements requirements-training.txt python benchmark_local_training.py
    uv run --python 3.13 --with-requirements requirements-training.txt python render_training_figures.py

To reproduce the trained comparison, use the saved candidate or specify new output folders for a new training run. The existing checkpoint can resume an interrupted run with `--resume`.

    HF_HUB_DISABLE_XET=1 uv run --python 3.13 --with-requirements requirements-training.txt python train_distilbert.py
    uv run --python 3.13 --with-requirements requirements-training.txt python evaluate_distilbert.py
    HF_HUB_OFFLINE=1 uv run --python 3.13 --with-requirements requirements-training.txt python evaluate_contextual_topic.py
    uv run --python 3.13 --with-requirements requirements-training.txt python render_distilbert_report.py

## AssemblyAI audio replay

Replay seven scripted English turns through the AssemblyAI realtime API with this command from the project directory. The terminal hides the API key as you type. You can also provide it through `ASSEMBLYAI_API_KEY`.

    uv run --python 3.13 --with-requirements requirements-voice.txt python evaluate_assemblyai.py data/assemblyai_demo/manifest.json --prompt-key

The replay uses Universal-3.6 Pro by default. AssemblyAI lists its base rate as $0.45 per connected hour. Each scripted turn opens and terminates its own connection. The CLI also accepts `--model assemblyai-stt-3-7-realtime` for the newer live conversation model. Use a distinct `--output` path for each run if comparing them. [Realtime pricing](https://www.assemblyai.com/blog/real-time-transcription-python) · [Streaming API](https://www.assemblyai.com/docs/streaming/api-spec/streaming-websocket)

The JSON in `results/assemblyai/replay.json` records word error rate, final transcript arrival relative to the replayed file end, and differences between moderator alerts on the reference and recognized turns. A final can arrive before the end of a clip that includes silence. The seven test clips use synthetic voices with speakers A and B assigned in the manifest. For recorded conversations, replace the manifest with labeled turns and mono PCM16 WAV files at 16 kHz, up to two minutes per run. Replaying a clip sends its audio to AssemblyAI. Get participants' permission before submitting their voices. The replay runs from the terminal. The browser's microphone workflow is a separate step.

## Run the debate dashboard

The imported landing page lives in `landing/`; the workspace lives in `frontend/`. Both use React, TypeScript and Three.js, and are served by one Python service. Clone the repository and build both interfaces from the project directory.

```sh
git clone https://github.com/moha-r/debate-signal.git
cd debate-signal
npm --prefix frontend ci
npm --prefix landing ci
npm --prefix frontend run build
npm --prefix landing run build
uv run --python 3.13 --with-requirements requirements-voice.txt uvicorn local_dashboard:app --host 127.0.0.1 --port 7863 --ws-max-size 8192
```

Open `http://127.0.0.1:7863` for the landing page. **Open workspace** leads to `/app/`, with sign-in at `/login` and account creation at `/signup`. Create an account to start a debate. On an upgraded installation with older unowned local debates, the first account adopts those debates.

Inside the workspace, choose **Explore an example** or **New debate**. The setup flow covers a discussion question, optional participant names, and an optional local microphone check. **My debates** restores the signed-in user's saved sessions, including participant names, transcript, alerts and moderator assessments. Data is stored in `.local/sessions.sqlite3`. Export a session as JSON for a portable copy. The first session downloads the pinned MiniLM weights. Once they are cached, you can start the service with `HF_HUB_OFFLINE=1`.

Accounts use unique normalized email addresses and salted scrypt password hashes. Login sessions use random tokens stored as hashes in SQLite, with HttpOnly SameSite=Lax cookies (Secure when served over HTTPS). Remember-me lasts up to 30 days; a browser-session cookie otherwise has a 24-hour server expiry. Logout revokes the current token. Account endpoints check request origins, and sign-in failures are limited per email and client address. Every debate read/write, correction, feedback export and voice connection checks ownership, including cached debates. Voice commits recheck login validity. No account is pre-created and no passwords or service keys are stored in frontend source or browser storage.

Before deploying, read the current `reports/dialogue_quality_followup_ar.md` and the preserved `reports/argument_quality_repair_ar.md` / `reports/predeploy_quality_audit_ar.md` comparisons. Set `PUBLIC_ORIGIN` to the exact external origin (for example, `https://debate.example.org`) and `DATA_DIR` to an absolute mounted persistent-volume directory. The application validates WebSocket origins for both WS and WSS; a configured HTTPS public origin also makes authentication cookies Secure behind a TLS-terminating proxy. Forward the original host/scheme through a trusted proxy configuration. `.env.example` is a template; environment files are not loaded automatically.

The latest dialogue diagnosis and results are in `reports/dialogue_root_cause_ar.md`. The before/after error ledger is `results/dialogue_root_cause/error_log.csv`. Prepare the local MiniLM answer extractor with `HF_HUB_OFFLINE=0 uv run --python 3.13 --with-requirements requirements-voice.txt python answer_extraction.py`. This downloads a pinned 134 MB checkpoint. When it is available, report suggestions can quote the answer span directly from the source turn. The question tracker continues with lexical matching and typed reply checks if the checkpoint is absent.

SQLite updates check the expected revision inside a write transaction; stale writers receive HTTP 409 instead of overwriting newer turns. Reads use the database as the authoritative revision. Run one service worker/replica for now: active voice-connection tracking is process-local, and duplicate recording prevention has not been validated across replicas. A persistent disk and tested backup/restore procedure remain required. Prepare the owner account before exposing an installation that contains unowned imported sessions.

The predeployment argument audit is reproducible with `HF_HUB_OFFLINE=1 uv run --python 3.13 --with-requirements requirements-voice.txt python evaluate_argument_quality.py --output results/predeploy_audit/new_run`. Existing output directories are protected from accidental overwrite. Authored references are in `data/argument_quality_audit.json`; external-corpus provenance and mapping limits are in `results/predeploy_audit/EXTERNAL_DATA_NOTICE.md`. Part 1 is diagnostic-only and is not packaged into serving data. Use `--fixtures data/argument_repair_holdout.json` for the separately frozen 44-turn authored challenge. Authored diagnostics are not independent human annotation. Argument-role and source-link quality currently do not support a claim of dependable general argument analysis.

The imported Desktop source remains available separately; the integrated copy has its own package lock and a real account form replacing the original UI preview. The landing's `/login` and `/signup` routes reuse its visual language. Workspace assets are built under `/app/`, including the audio worklet, to avoid collisions with landing assets. For frontend development, both Vite configs proxy `/api` to the Python service; the landing also proxies `/app`.

Set `ASSEMBLYAI_API_KEY` in the server environment to enable recording for all signed-in moderators. The server uses that AssemblyAI account for transcription. In **Live room**, select **Start recording** and allow microphone access in your browser. Two participants can take turns speaking into a shared microphone. Completed turns are analyzed automatically. **End recording** finishes the last turn and opens the session review screen. The connection also closes after a minute without audio frames. Defaults additionally limit each recording to 900 seconds, one recording per moderator and two globally. Set `MAX_VOICE_SECONDS` (1–3600) and `MAX_CONCURRENT_VOICE` (1–8) before startup to change these limits. The duration limit flushes final audio before termination. Reservations are atomic within one service process and released on disconnect/errors. These limits bound individual recordings, not daily spending.

AssemblyAI 3.7 Realtime receives microphone audio during recording and assigns speaker labels within that streaming session. Short or ambiguous turns can appear as **Unconfirmed speaker**. Select a recorded turn to correct its speaker and linked alert labels. **Review queue** presents each flagged moment with its surrounding turns, model scores, and review actions. The full transcript is available in a separate review tab. Use the text composer to revise a recovered draft if a connection drops.

The room now includes measured participation and a live argument trail. Participation sums the union of finalized word intervals per speaker and recording, excluding pauses. Unknown labels remain separate, duplicate intervals do not inflate totals, and reconnects use separate recording IDs. Older recordings and typed turns are explicitly untimed. A balance advisory appears only after 30 seconds of measured speech, both speakers are present, and one voice exceeds 70% of all measured speech. This is an advisory policy, not a scientifically validated dominance measure. [AssemblyAI's streaming diarization documentation](https://www.assemblyai.com/docs/streaming/label-speakers-and-separate-channels) describes word timestamps and labels. Correcting a recorded turn reassigns its measured intervals too.

**Argument map** combines the locally trained TF–IDF/MiniLM role classifier with a pinned RoBERTa-large dialogue relation classifier and explicit safeguards for questions, quotation scope, negation, policy positions and reasons. The cross-encoder reads each new statement together with up to six retrieved earlier arguments and scores support/attack/no relation. It runs locally on CPU. The threshold and target margin come from the highest target-and-relation F1 on the existing Part 2 development split. Scores are uncalibrated. Argument role and relationship type are separate; same-speaker self-corrections are allowed. The original logistic relation classifier remains available as a lightweight fallback. The session and every new annotation record the actual relation backend and model revision. Evidence references require human verification.

Prepare the 1.42 GB dialogue checkpoint with `HF_HUB_OFFLINE=0 uv run --python 3.13 --with-requirements requirements-voice.txt python prepare_dialogue_relation_model.py`. The pinned revision and weight SHA-256 are verified. `ARGUMENT_RELATION_BACKEND=auto` uses the cached cross-encoder when available and logs a fallback when missing. `transformer` requires the prepared model; `local` selects the previous logistic model. Restart the process after changing this setting or preparing a missing checkpoint. Keep the Hugging Face cache available to the deployment user, including offline deployments. The model's CC BY-NC-SA 4.0 attribution and inference mapping are in `artifacts/ARGUMENT_MODEL_NOTICE.md`.

With the RoBERTa backend, `artifacts/contextual_link_selector.joblib` checks ambiguous support and challenge suggestions. It compares the proposed link with the closest candidate and competing links and withholds suggestions with weak scores or a close alternative. Clear exchanges can still link to their immediate source, and question responses retain their own tracker. The review map shows the earlier source excerpt under each suggestion and marks uncertain automatic connections. See [the contextual link audit](reports/contextual_link_quality_ar.md) for the baseline comparison, test limitations and reproduction commands.

In **Review → Argument map**, expand **Review role & connection** to change a primary role, choose support/challenge/answer and an earlier source (or no connection), and add a note. Saving is revision-checked and owner-only. JSON exports preserve original automatic annotations alongside moderator annotations. Downstream references invalidated by a correction are cleared with a dependency note. Corrections affect reports and subsequent context; they do not rerun earlier turns or retrain models.

The independent question-response tracker searches open questions across the whole session, including questions older than six turns. Reports distinguish potential answers, partial/uncertain responses, missing evidence and refusals. Partial responses and missing evidence remain flagged for follow-up; potential answers await human review. A moderator-confirmed answer is explicit human input, not factual verification. “No answer linked” requires transcript inspection.

Training uses **Part 2** of Arg-Microtexts (119 whole training documents, 26 development, 26 test), excluding implicit inserted claims. Part 1 remains external diagnostic data. Prefix augmentation applies only to training. Hyperparameter and confidence-gate selection use development only. Exact partitions, hashes and trials are in `results/argument_repair/training/manifest.json`; attribution and the corpus **CC BY-NC-SA 4.0** restrictions are in `artifacts/ARGUMENT_MODEL_NOTICE.md`. This is a noncommercial course research artifact. These written texts do not establish natural-dialogue accuracy. Source-link quality still requires human review.

Reproduce corpus preparation and training with `python prepare_argument_training_corpus.py` followed by `HF_HUB_OFFLINE=1 uv run --python 3.13 --with-requirements requirements-voice.txt python train_argument_models.py`. The encoder must be cached for offline use. Training replaces the model and its training manifest. Test a temporary authenticated SQLite workflow with actual models using `HF_HUB_OFFLINE=1 uv run --python 3.13 --with-requirements requirements-voice.txt python verify_argument_workflow.py`.


**Session report** organizes exact source quotations into claims, reasons, expressed agreement/disagreement and questions to follow up, alongside participation. End recording opens this report. Download the report as Markdown (including the full transcript) or export the complete session as JSON. The report does not determine a winner or factual correctness.

In a flagged moment, **Alert is correct / Alert is incorrect** saves a separate moderator assessment and optional explanation. Reviewed/Dismissed remains the workflow status. Assessments persist in the same transaction as the session, are revision-checked, and can be updated. The report offers JSONL export with original text, preceding context, raw model scores and detector provenance for future supervised evaluation/training. Saving an assessment does not immediately retrain a model.

Recent topic context is limited to four turns and directly topical anchors. Only short semantically linked follow-up questions can inherit relevance. Conversation-management turns such as “What do you think?” appear as **Neutral** and leave the topic-drift counter unchanged. An opinion question with an explicit subject is scored on that subject. Explicit discussion of a fully quoted insult and a narrowly matched denial of a recent accusation can suppress an alert while preserving the classifier's raw score and the policy explanation. These safeguards are heuristic and need natural-dialogue validation. Reproduce the regression comparison with `HF_HUB_OFFLINE=1 uv run --python 3.13 --with-requirements requirements-voice.txt python evaluate_conversation_insights.py`. Results are in `results/conversation_insights/`; existing authored diagnostics are not independent accuracy evidence for the new extraction features.

Gradio provides a standalone sentence classifier for the live demo and a separate text-only debate workspace.

From this project directory, run:

    uv run --python 3.13 --with-requirements requirements.txt python app.py

Open http://127.0.0.1:7860. In **Sentence check**, type a sentence or choose an example, then select **Analyze sentence**. The result shows the class at the moderation threshold, both probabilities, and the text after preprocessing. **Clear** resets the input and result. Sentence checks use the saved attack model on their own.

Open **Debate workspace** to test topic relevance and contextual alerts. The first debate session loads the pinned MiniLM encoder from Hugging Face if it is missing locally. Subsequent sessions reuse it.

1. Enter a question and choose **Start / reset session**.
2. Choose **A** or **B**, type a completed turn, and choose **Analyze and add turn**.
3. Inspect **Moderator alerts**. Select an alert to **Mark reviewed** or **Dismiss**.
4. Expand **Latest turn analysis** to inspect personal-attack probabilities, topic similarity and the text after preprocessing.

Starting a session resets the current in-memory transcript and alert queue. Separate browser sessions have separate conversation state. Refreshing the browser starts a fresh workspace. This Gradio prototype processes typed input in its Python process and keeps the session in memory.

## Models and evidence

The attack pipeline was trained on WikiDetox Personal Attacks. It uses Snowball stemming, word and bigram TF-IDF, and a LinearSVC classifier selected by three-fold training cross-validation. A sigmoid fitted on training out-of-fold margins supplies probabilities. The alert threshold is 0.35, selected on a separate pool of training out-of-fold predictions.

| Attack decision rule | Precision | Recall | Macro F1 |
|---|---:|---:|---:|
| Original LinearSVC | 0.8754 | 0.6659 | 0.8642 |
| Calibrated alert at 0.35 | 0.8037 | 0.7413 | 0.8712 |

These scores use 22,921 written comments. Live spoken English requires a separate audit. The authored Manglish probe and four real errors are under results/.

Topic monitoring uses sentence-transformers/all-MiniLM-L6-v2 at the revision recorded in results/topic_policy.json. It compares each utterance with the original motion and uses the preceding relevant turn for short follow-ups. It signals sustained drift after two off-topic utterances, and sends one alert until the conversation returns to the motion.

The initial diagnostic has 85 authored turns. A further 60-turn challenge uses the frozen policy. These are small authored examples with no independent annotation. The challenge caught 3 of 4 sustained detours, and missed a smartphone-camera detour during a surveillance-camera discussion. Topic similarity is an experimental cue for human review.

## Expanded audit before speech integration

The frozen-policy audit adds 180 authored attack cases (168 clear and 12 ambiguous), 1,008 paired text perturbations and 24 conversations containing 288 turns and 18 drift episodes. The calibrated attack rule scored 82.3% precision and 77.4% recall on the clear authored cases. Topic monitoring found 17 of 18 episodes with two false alerts; it also misclassified 19 related turns as off-topic. These are targeted authored diagnostics, not independent human annotation or natural speech accuracy.

All 22,921 original held-out attack predictions were reproduced from verified source text. Twenty-seven deterministic workflow tests passed; the real wrapper matched topic decisions on all 288 turns. A 250-turn workload and four parallel independent sessions completed without state contamination in the tested workload. Technical test success does not establish language understanding.

The audit exposed important weaknesses in negation, quoted insults, implicit degradation, long turns and contextual follow-ups. No model or threshold was changed. See the [Arabic findings report](docs/evaluation/2026-11-18-expanded-audit-report.md) and the executed local notebook `notebooks/expanded_audit.ipynb`. The expanded notebook has not been uploaded to Colab.

To reproduce the audit from this directory:

    uv run --python 3.13 --with-requirements requirements.txt python evaluate_expanded_audit.py
    uv run --python 3.13 --with-requirements requirements.txt python run_workflow_checks.py

The first command downloads the verified WikiDetox comments when needed. Raw downloads under `data/raw/` are excluded from Git. Results, row-level mistakes, hashes and timings are saved under `results/expanded_audit/`. After using these cases to improve the models, evaluate on a new locked test set.

## Training and evaluation

- notebooks/train_evaluate.ipynb contains the executed data exploration, preprocessing comparison, 80/20 stratified split, model tuning, held-out evaluation, calibration and error/dialect audits.
- notebooks/topic_relevance.ipynb presents the locally executed topic diagnostic and challenge evidence.
- evaluate_topic_relevance.py reproduces the initial lexical/semantic comparison. evaluate_topic_challenge.py scores the additional authored sessions using the locked policy.
- artifacts/ contains the two original pipelines and the calibrated alert bundle. results/ contains the model selection settings, metrics and test predictions.

WikiDetox is released under CC0. The code records file IDs and checksums for Figshare version 6. See the [Wikimedia release](https://meta.wikimedia.org/wiki/Research:Detox/Data_Release) and [Figshare dataset](https://doi.org/10.6084/m9.figshare.4054689.v6). MiniLM is provided under Apache-2.0. See its [model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2).
