"""Session state and model inference for the human moderator's text workspace."""

from copy import deepcopy
from datetime import datetime, timezone
from functools import lru_cache
import json
import hashlib
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import joblib

from nlp_pipeline import preprocess_text
from topic_relevance import MODEL_ID, MODEL_REVISION, TopicMonitor, FOLLOW_UP
from conversation_insights import argument_for, quotation_context


ROOT = Path(__file__).resolve().parent
MONITOR_FIELDS = ("previous_text", "previous_relevant", "off_topic_count", "alert_active")


@lru_cache(maxsize=1)
def load_attack_bundle():
    bundle = joblib.load(ROOT / "artifacts/LinearSVC_alert.joblib")
    bundle['artifact_sha256'] = hashlib.sha256((ROOT / 'artifacts/LinearSVC_alert.joblib').read_bytes()).hexdigest()
    return bundle


def score_attack(text, bundle):
    margin = bundle["pipeline"].decision_function([text])
    return float(bundle["sigmoid"].predict_proba(margin[:, None])[0, 1])


@lru_cache(maxsize=1)
def load_resources():
    from sentence_transformers import SentenceTransformer

    bundle = load_attack_bundle()
    policy = json.loads((ROOT / "results/topic_policy.json").read_text())
    encoder = SentenceTransformer(MODEL_ID, revision=MODEL_REVISION, device="cpu")
    return bundle, policy, encoder


def new_session(topic, resources=None):
    topic = topic.strip()
    if len(topic.split()) < 3:
        raise ValueError("Enter a discussion question with at least three words.")
    resources = resources or load_resources()
    _, policy, encoder = resources
    monitor = TopicMonitor(topic, policy["threshold"], policy["backend"], policy["use_context"], encoder)
    from argument_models import available, artifact_sha256
    arguments=available(encoder)
    relation_metadata={'backend':'guarded-rules'}
    if arguments:
        from dialogue_relations import relation_backend
        relation_metadata=relation_backend()
    return {
        "id": str(uuid4()), "topic": topic, "started_at": datetime.now(timezone.utc).isoformat(),
        "turns": [], "alerts": [], "monitor": {key: getattr(monitor, key) for key in MONITOR_FIELDS},
        "detectors": {"attack": "LinearSVC_alert", "topic": MODEL_ID, "revision": MODEL_REVISION,
                      "context_policy": "neutral-turns-v2", "attack_threshold": resources[0]['threshold'],
                      "attack_sha256": resources[0].get('artifact_sha256'), "topic_threshold": policy['threshold'],
                      'arguments':arguments['version'] if arguments else 'guarded-rule-fallback-v2',
                      'argument_sha256':artifact_sha256() if arguments else None,
                      'argument_relations':relation_metadata},
    }


def analyze_turn(session, speaker, text, resources=None, *, argument_trace=None):
    if session is None:
        raise ValueError("Start a session with a discussion topic first.")
    if speaker not in ("A", "B", "Unknown"):
        raise ValueError("Choose speaker A or B.")
    text = text.strip()
    if not text:
        raise ValueError("Enter a completed speaking turn.")
    model_text = preprocess_text(text)
    if not model_text:
        raise ValueError("Enter words to analyze. This input contains only removable characters.")

    resources = resources or load_resources()
    bundle, policy, encoder = resources
    start = perf_counter()
    probability = score_attack(text, bundle)
    attack = probability >= bundle["threshold"]
    context = quotation_context(text, session['turns'][-4:])
    attack = attack and not context['suppressed']
    monitor = TopicMonitor(
        session["topic"], policy["threshold"], policy["backend"], policy["use_context"], encoder
    )
    for field in MONITOR_FIELDS:
        setattr(monitor, field, session["monitor"][field])
    topic_result = monitor.process(text)
    # Context can rescue only a short follow-up, using a directly grounded anchor.
    # Broad inheritance previously reduced held-out drift recall, so it is excluded.
    if (topic_result['state'] == 'off_topic' and not session['monitor']['alert_active']
            and len(text.split()) <= 9 and FOLLOW_UP.match(text.casefold())):
        for anchor in reversed(session['turns'][-4:]):
            if (anchor['topic'].get('direct_score') or 0) < policy['threshold']:
                continue
            import numpy as np
            link = float(np.dot(encoder.encode(text, normalize_embeddings=True),
                                encoder.encode(anchor['text'], normalize_embeddings=True)))
            if link < .30:
                continue
            score = monitor.similarity(anchor['text'] + ' ' + text)
            if score >= policy['threshold']:
                topic_result.update(state='on_topic', score=score, used_context=True, alert=False,
                                    off_topic_count=0, context_turn=anchor['number'])
                monitor.off_topic_count = 0
                monitor.alert_active = False
                break
    # Build the updated state after both detectors succeed.
    updated = deepcopy(session)
    updated["monitor"] = {key: getattr(monitor, key) for key in MONITOR_FIELDS}
    turn = {
        "number": len(session["turns"]) + 1, "speaker": speaker, "text": text,
        "processed_text": model_text,
        "time": datetime.now(timezone.utc).isoformat(),
        "attack_probability": probability, "personal_attack": attack,
        "attack_context": context,
        "topic": topic_result,
        "latency_ms": 0.0,
    }
    turn['_topic_text']=session['topic']
    if argument_trace is None:
        turn['argument'] = argument_for(turn, session['turns'], encoder)
    else:
        turn['argument'] = argument_for(turn, session['turns'], encoder, trace=argument_trace)
    turn.pop('_topic_text')
    updated["turns"].append(turn)
    for kind, triggered in (
        ("Personal attack", attack),
        ("Topic drift", topic_result["alert"]),
    ):
        if triggered:
            updated["alerts"].append({
                "id": f'R{len(updated["alerts"]) + 1}',
                "kind": kind, "speaker": speaker, "turn": turn["number"],
                "time": turn["time"], "text": text, "status": "Pending",
            })
    # Include argument extraction and state construction; ASR/HTTP remain outside this timer.
    turn['latency_ms'] = (perf_counter() - start) * 1000
    return updated


def correct_voice_speaker(session, number, speaker):
    if speaker not in ("A", "B"):
        raise ValueError("Choose speaker A or B.")
    updated = deepcopy(session)
    turn = next((turn for turn in updated["turns"] if turn["number"] == number), None)
    if turn is None or turn.get("source") != "voice":
        raise ValueError("Select a recorded turn to correct.")
    turn["speaker"] = speaker
    for interval in (turn.get('voice_timing') or {}).get('intervals', []):
        interval['speaker'] = speaker
    turn['speaker_corrected'] = True
    by_number = {item['number']: item for item in updated['turns']}
    for item in updated['turns']:
        argument = item.get('argument') or {}
        link = argument.get('link')
        if link and argument.get('role') in ('claim','rebuttal') and argument.get('method') not in ('learned-roles-relations-v2','guarded-rule-fallback-v2','moderator-correction'):
            target = by_number.get(link['turn'])
            if target and target['speaker'] == item['speaker']:
                argument['link'] = None
    for alert in updated["alerts"]:
        if alert["turn"] == number:
            alert["speaker"] = speaker
    return updated


def review_alert(session, alert_id, decision):
    if session is None:
        raise ValueError("Start a session first.")
    if decision not in ("Reviewed", "Dismissed"):
        raise ValueError("Unknown review action.")
    updated = deepcopy(session)
    matches = [alert for alert in updated["alerts"] if alert["id"] == alert_id]
    if not matches or matches[0]["status"] != "Pending":
        raise ValueError("Select a pending alert to review.")
    matches[0]["status"] = decision
    return updated
