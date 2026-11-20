"""Inspectable conversational suggestions. These rules do not verify evidence or truth."""

from collections import defaultdict
from datetime import datetime, timezone
import math
import re

VERSION = "conversation-context-v3"
POLICY = {"dominance_share": .70, "minimum_speech_seconds": 30}

QUESTION = re.compile(r"^(?:what|why|how|who|when|where|which|can|could|should|would|do|does|did|is|are)\b", re.I)
REBUTTAL = re.compile(r"\b(?:i disagree|that is incorrect|that's incorrect|on the contrary|however|but that|does not follow|doesn't follow|not necessarily)\b", re.I)
SUPPORT = re.compile(r"\b(?:because|for example|for instance|according to|research|study|studies|data|evidence|statistics|survey)\b", re.I)
AGREEMENT = re.compile(r"^(?:yes[, .]|i agree\b|we agree\b|you(?:'re| are) right\b|that(?:'s| is) a fair point\b)", re.I)
EVIDENCE_REQUEST = re.compile(r"\b(?:evidence|source|sources|proof|study|data|support that)\b", re.I)


def quotation_context(text, recent):
    """Only exempt an explicitly rejected/reported *fully quoted* insult.

    A remaining second-person assertion is deliberately left to the detector.
    The raw classifier score is retained by the caller.
    """
    quotes = re.findall(r'["“]([^"”]+)["”]', text)
    outside = re.sub(r'["“][^"”]+["”]', '', text)
    reporting = re.search(r"\b(?:the phrase|the statement|the words|the expression|calling someone)\b", outside, re.I)
    rejection = re.search(r"\b(?:unacceptable|personal attack|insult|offensive|inappropriate|should not|shouldn't)\b", outside, re.I)
    if quotes and reporting and rejection and not re.search(r"\b(?:you|your|idiot|stupid|moron)\b", outside, re.I):
        return {"suppressed": True, "reason": "Explicit discussion of a quoted insult; inspect the source turn.",
                "context_turns": [t['number'] for t in recent]}
    denial = re.fullmatch(r"(?:no[, ]+)?i (?:did not|didn't|never) (?:call you (?:an? )?(?:idiot|moron|fool)|say (?:that )?you (?:are|were) (?:an? )?(?:idiot|moron|fool))[.!]?", text.strip(), re.I)
    accusation = any(re.search(r"\b(?:called me|calling me|you said|you say)\b", t['text'], re.I) for t in recent[-2:])
    if denial and accusation:
        return {"suppressed": True, "reason": "Narrow denial of a recently attributed insult; inspect the surrounding turns.",
                "context_turns": [t['number'] for t in recent]}
    return {"suppressed": False, "reason": None, "context_turns": [t['number'] for t in recent]}


def argument_for(turn, previous, encoder, *, trace=None):
    from argument_models import available, load_models, role_scores, relation_scores, vector, words
    from question_tracker import REFERENCE, question_info, find_responses, outside_quotes, response_status
    from relation_context import action_verb, has_reply_cue, relation_rank, retrieval_score
    text=turn['text']; visible=outside_quotes(text).strip()
    info=question_info(text,turn.get('_topic_text',''))
    answers=find_responses(turn,previous,encoder)
    if trace is not None:
        trace.update(question=info, matched_responses=answers, candidates=[])
    learned=available(encoder)
    gates=load_models().get('confidence_gates',{}) if learned else {}
    relation_margin=.015
    backend={'backend':'local-logistic'}
    if learned and len(vector(encoder,'A short discussion.'))==384:
        from dialogue_relations import relation_backend
        backend=relation_backend()
        if backend['backend']=='dialogue-roberta':
            gates={**gates,'relation':{'support':backend['threshold'],'attack':backend['threshold']}}
            relation_margin=backend['margin']
    method='learned-roles-relations-v2' if learned else 'guarded-rule-fallback-v2'
    role='unclassified';cue='Insufficient contextual evidence';confidence=None
    explicit=None
    metalinguistic=bool(re.search(r"\b(?:phrase|expression|word|question)\b.*\b(?:title|printed|pronounce|spelling|named)\b",visible,re.I))
    negative=bool(re.search(r"\b(?:i (?:do not|don't|cannot|can't) (?:agree|accept)|i am not convinced|no (?:evidence|proof)|does not establish|doesn't establish|does not demonstrate|doesn't demonstrate|on the other hand|but still)\b",visible,re.I))
    recent_arguments=[t for t in previous[-2:] if t['topic']['state']=='on_topic'
                      and t.get('argument',{}).get('role') in ('claim','reason','rebuttal','agreement')]
    contextual_question=info['is_question'] and (
        any(words(text)&words(t['text']) for t in recent_arguments) or
        bool(info['evidence_requested'] and recent_arguments and REFERENCE.search(visible)))
    contextual_agreement=bool(AGREEMENT.search(visible) and any(
        len(words(visible)&words(t['text']))>=2 and float(vector(encoder,text)@vector(encoder,t['text']))>=.42
        for t in recent_arguments))
    if turn['personal_attack']:
        cue='Personal attack flagged; argument role withheld'
    elif metalinguistic:
        cue='Metalinguistic mention rather than a current argument'
    elif response_status(text,'explanation')=='declined':
        cue='Explicit refusal to answer; retained as a response, not an argument'
    elif turn['topic']['state']=='off_topic' and not (answers or contextual_question or contextual_agreement):
        cue='Outside the current discussion; argument role withheld'
    elif info['is_question']:
        role,cue='question','Direct question or request for information'
    elif answers and answers[0]['status'] in ('insufficient_evidence','uncertain_answer','partial_answer'):
        role,cue='claim','Response qualifying what is known or supplied'
    elif negative or REBUTTAL.search(visible):
        role,cue,explicit='rebuttal','Explicit challenge or negated agreement','attack'
    elif AGREEMENT.search(visible):
        role,cue,explicit='agreement','Explicit agreement language','support'
    elif SUPPORT.search(visible) and re.search(r'\b(?:because|for example|for instance|according to)\b',visible,re.I):
        role,cue='reason','Explicit reason or evidence reference (unverified)'
    elif re.search(r'\b(?:should|must|ought to)\b',visible,re.I):
        role,cue='claim','Explicit policy position'
    elif learned and not previous and len(text.split())>=5 and turn['topic']['state']=='on_topic':
        role,cue='claim','Opening substantive position'
    elif learned:
        scores=role_scores(text,previous,encoder)
        role=max(scores,key=scores.get);confidence=scores[role]
        cue='Locally trained contextual role classifier'
        if confidence<gates.get('role',{}).get(role,1.):
            role,cue=('claim','Substantive statement; learned role withheld below development confidence gate') if len(text.split())>=5 else ('unclassified','Role classifier abstained on an uncertain contribution')
            confidence=None
    elif SUPPORT.search(visible):
        role,cue,explicit='reason','Reason or evidence reference (unverified)','support'
    elif len(text.split())>=5 and turn['topic']['state']=='on_topic':
        role,cue='claim','Substantive topical statement'
    if not turn['personal_attack'] and not metalinguistic and answers and role=='unclassified' and answers[0]['status']!='declined':
        role,cue='claim','Substantive contextual response to an earlier question'
    if answers and role in ('claim','reason') and explicit is None and answers[0]['status']!='declined':
        role,cue='claim','Statement responding to an earlier question'
        confidence=None
    if not previous and role in ('reason','rebuttal') and re.search(r"\bshould\b",visible,re.I) and not negative and not SUPPORT.search(visible):
        role,cue='claim','Opening policy position'
    link=None
    if role in ('claim','reason','rebuttal','agreement'):
        candidates=[t for t in previous if t.get('argument',{}).get('role') in ('claim','reason','rebuttal','agreement')
                    and not t.get('personal_attack')
                    and not any(r['status'] in ('declined','uncertain_answer','insufficient_evidence')
                                for r in t['argument'].get('answers',[]))
                    and (t['topic']['state']!='off_topic' or t['argument'].get('answers'))]
        contextual_cue=explicit is not None or has_reply_cue(visible)
        proposed_action=action_verb(visible)
        illustrates=bool(re.match(r'^(?:for example|for instance)\b',visible,re.I))
        detail=words(text)-words(turn.get('_topic_text',''))
        ranked=[]
        if candidates and not (answers and answers[0]['status']!='declined'):
            current=vector(encoder,text)
            similarity={t['number']:float(current@vector(encoder,t['text'])) for t in candidates}
            def retrieval_key(target):
                distance=turn['number']-target['number']
                overlap=len(detail&words(target['text']))/max(1,len(detail))
                return (retrieval_score(similarity[target['number']],distance,overlap),target['number'])
            candidates=sorted(candidates,key=retrieval_key,reverse=True)[:12]
            probabilities=relation_scores(text,candidates,turn['number'],encoder)
            if trace is not None:
                trace['eligible_targets']=sorted(similarity)
            for index,target in enumerate(candidates):
                sim=similarity[target['number']]
                entry={'turn': target['number'], 'similarity': sim, 'state': 'scored'}
                if trace is not None:
                    trace['candidates'].append(entry)
                if index>=backend.get('max_candidates',len(candidates)):
                    entry['state']='outside_pair_budget'
                    continue
                if sim<.20:
                    entry['state']='similarity_gate'
                    continue
                if probabilities:
                    scores=probabilities[index]
                    entry['probabilities']=scores
                    relation=explicit or max(('support','attack'),key=lambda k:scores.get(k,0))
                    probability=scores.get(relation,0)
                    shared_detail=detail&words(target['text'])
                    if illustrates and target['number']==turn['number']-1 and sim>=.50:
                        # Explicit examples can elaborate the concern in the preceding turn.
                        if scores.get('rephrase',0)>.60:
                            relation,probability='support',scores['support']
                    accepts_paraphrase=role=='agreement' and shared_detail or illustrates and relation=='support' and target['number']==turn['number']-1 and sim>=.50
                    rephrased=scores.get('rephrase',0) if accepts_paraphrase else 0
                    probability+=rephrased
                    entry.update(relation=relation, confidence=probability)
                    # Standalone policy proposals require a shared detail beyond the motion.
                    if relation=='support' and cue=='Explicit policy position' and not contextual_cue and not shared_detail:
                        entry['state']='independent_policy'
                        continue
                    if relation=='support' and proposed_action and not contextual_cue:
                        target_action=action_verb(target['text'])
                        if target_action and target_action!=proposed_action:
                            entry['state']='parallel_proposal'
                            continue
                    if probability<gates.get('relation',{}).get(relation,1.) or probability<=scores.get('none',0)-rephrased:
                        entry['state']='model_or_threshold_rejection'
                        continue
                    distance=turn['number']-target['number']
                    base=relation_rank(probability,sim,distance)
                    overlap=len(shared_detail)/max(1,len(detail))
                    score=.77*base+.15*overlap+.08/distance
                    if role=='agreement':
                        score=.55*probability+.20*sim+.20*overlap+.05*math.exp(-distance/3)
                else:
                    relation=explicit or ('attack' if role=='rebuttal' else 'support')
                    probability=sim;score=sim
                    if role=='claim' or sim<.35:
                        entry['state']='fallback_gate'
                        continue
                entry.update(state='ranked', rank=score)
                ranked.append((score,target,relation,probability,sim))
            ranked.sort(key=lambda x:(x[0],x[1]['number']),reverse=True)
            if trace is not None:
                trace['ranked_targets']=[item[1]['number'] for item in ranked]
                trace['explicit_relation']=explicit
            if ranked and (len(ranked)==1 or ranked[0][0]-ranked[1][0]>=relation_margin):
                score,target,relation,probability,sim=ranked[0]
                link={'turn':target['number'],'relation':relation,'confidence':round(probability,4),'similarity':round(sim,4),'tentative':True}
                if relation=='attack' and explicit is None and role in ('claim','reason') and probability>=.80 and not SUPPORT.search(visible):
                    role,cue,confidence='rebuttal','Likely conflict with an earlier position',None
                # A relation is separate from the primary speech act: a claim may support another claim.
        if answers and answers[0]['status']!='declined':
            answer=answers[0]
            target=next(t for t in previous if t['number']==answer['turn'])
            link={'turn':answer['turn'],'relation':'answers','confidence':answer['confidence'],'similarity':round(float(vector(encoder,text)@vector(encoder,target['text'])),4),'tentative':True}
        # Clear acknowledgements can refer to the immediately preceding substantive contribution.
        if role=='agreement' and not link and previous and len(text.split())<=4:
            target=previous[-1]
            if target.get('argument',{}).get('role') in ('claim','reason','rebuttal'):
                link={'turn':target['number'],'relation':'support','confidence':None,'similarity':None,'tentative':True}
    if trace is not None:
        trace.update(role=role, cue=cue, link=link, topic=turn['topic']['state'])
    return {'role':role,'cue':cue,'link':link,'method':method,'role_confidence':confidence,
            'evidence_requested':role=='question' and info['evidence_requested'],
            'question':info if role=='question' else None,'answers':answers,'relation_model':backend}


def voice_timing(event, recording_id):
    """Accept only finite, finalized provider word intervals, in milliseconds."""
    intervals = []
    for word in event.get('words') or []:
        if not isinstance(word, dict) or word.get('word_is_final') is not True:
            continue
        start, end = word.get('start'), word.get('end')
        if any(isinstance(n, bool) or not isinstance(n, (int,float)) or not math.isfinite(n) for n in (start,end)):
            continue
        if not 0 <= start < end:
            continue
        # A missing word label can inherit a turn label; an explicit UNKNOWN cannot.
        label = word.get('speaker', event.get('speaker_label'))
        intervals.append({"start_ms": start, "end_ms": end, "speaker": label if label in ('A','B') else 'Unknown'})
    return {"recording_id": recording_id, "intervals": intervals, "source": "assemblyai-word-timestamps"}


def union_ms(intervals):
    total, end_at = 0, -1
    for start, end in sorted(intervals):
        total += max(0, end - max(start, end_at))
        end_at = max(end_at, end)
    return total


def participation(turns):
    groups = defaultdict(list)
    timed = 0
    for turn in turns:
        timing = turn.get('voice_timing') or {}
        if timing.get('intervals'):
            timed += 1
        for interval in timing.get('intervals', []):
            groups[(timing['recording_id'], interval['speaker'])].append((interval['start_ms'], interval['end_ms']))
    seconds = {side: round(sum(union_ms(v) for (recording,speaker),v in groups.items() if speaker == side)/1000, 3)
               for side in ('A','B','Unknown')}
    known = seconds['A'] + seconds['B']
    total = sum(seconds.values())
    dominant = max(('A','B'), key=lambda s: seconds[s]) if known else None
    # Unknown speech remains in the denominator and can prevent a dominance claim.
    advisory = dominant if total >= POLICY['minimum_speech_seconds'] and min(seconds['A'],seconds['B']) > 0 and seconds[dominant]/total >= POLICY['dominance_share'] else None
    return {"seconds": seconds, "shares": {s: seconds[s]/total if total else None for s in seconds},
            "timed_turns": timed, "untimed_turns": len(turns)-timed,
            "dominant_speaker": advisory, "policy": POLICY,
            "measurement": "Union of finalized word intervals per recording; pauses excluded. ASR timing is approximate."}


def session_insights(state):
    turns = state['turns']
    nodes = [{"turn": t['number'], "speaker": t['speaker'], "text": t['text'], **t['argument']}
             for t in turns if t.get('argument')]
    for node in nodes:
        node['roles'] = [node['role']]
        # A rebuttal can contain a reason too; primary-role display must not lose it.
        if node['role'] in ('claim','rebuttal','agreement') and SUPPORT.search(node['text']):
            node['roles'].append('reason')
    questions = []
    for t in turns:
        if t.get('argument',{}).get('role') != 'question':
            continue
        # The response's source turn and question target are different IDs.
        responses=[{'turn':n['turn'],'status':response['status'],'confidence':response.get('confidence'),
                    **({'answer_span':response['answer_span']} if 'answer_span' in response else {})}
                   for n in nodes for response in n.get('answers',[]) if response['turn']==t['number']]
        answers=[r['turn'] for r in responses if r['status']!='declined']
        if not any('answers' in n for n in nodes):
            # Backward compatibility for saved v1 sessions; do not rewrite original annotations.
            answers=[n['turn'] for n in nodes if n.get('link') and n['link']['turn']==t['number']
                     and n['role'] in ('reason','rebuttal','claim') and n['speaker']!=t['speaker']]
        status=('moderator_answered' if any(r['status']=='confirmed_answer' for r in responses) else
                'answer_pending_review' if any(r['status']=='possible_answer' for r in responses) else
                'needs_followup' if responses else 'open')
        questions.append({"turn": t['number'], "text": t['text'], "answer_turns": answers,'status':status,
                          'responses':responses,"evidence_requested": t['argument']['evidence_requested']})
    return {"version": VERSION, "participation": participation(turns), "arguments": nodes,
            "report": {"claims": [n['turn'] for n in nodes if n['role'] == 'claim'],
                       "reasons": [n['turn'] for n in nodes if 'reason' in n['roles']],
                       "agreements": [n['turn'] for n in nodes if n['role'] == 'agreement'],
                       "disagreements": [n['turn'] for n in nodes if n['role'] == 'rebuttal'],
                       "questions": questions,
                       "limitations": "Locally learned role/relation suggestions with explicit language safeguards and an independent question-response tracker. Links need review; referenced evidence is not verified. A linked response may be partial, uncertain or lack evidence."}}


def apply_feedback(session, alert_id, verdict, reason):
    from copy import deepcopy
    if verdict not in ('correct','incorrect'):
        raise ValueError('Choose whether the alert was correct or incorrect.')
    updated = deepcopy(session)
    alert = next((a for a in updated['alerts'] if a['id'] == alert_id), None)
    if alert is None:
        raise ValueError('This alert does not exist.')
    alert['feedback'] = {"verdict": verdict, "reason": reason.strip(), "time": datetime.now(timezone.utc).isoformat()}
    return updated


def correct_argument(session, number, role, target, relation, reason):
    """Persist a moderator annotation without rewriting the automatic prediction."""
    from copy import deepcopy
    from question_tracker import question_info
    valid_roles={'claim','reason','rebuttal','question','agreement','unclassified'}
    if role not in valid_roles: raise ValueError('Choose a valid argument role.')
    updated=deepcopy(session)
    turn=next((t for t in updated['turns'] if t['number']==number),None)
    if turn is None: raise ValueError('This turn does not exist.')
    link=None;answers=[]
    if target is None and relation is not None:
        raise ValueError('Choose a source turn for the relationship.')
    if target is not None:
        source=next((t for t in updated['turns'] if t['number']==target),None)
        if source is None or target>=number: raise ValueError('Link only to an existing earlier turn.')
        if role in ('question','unclassified') or relation not in ('support','attack','answers'):
            raise ValueError('Choose a substantive role and a valid relationship.')
        source_role=source.get('argument',{}).get('role')
        if (relation=='answers' and source_role!='question') or (relation!='answers' and source_role not in ('claim','reason','rebuttal','agreement')):
            raise ValueError('Answers must target questions; argument relationships must target arguments.')
        link={'turn':target,'relation':relation,'confidence':None,'similarity':None,'tentative':False}
        if relation=='answers': answers=[{'turn':target,'status':'confirmed_answer','confidence':None,'tentative':False}]
    original=turn.get('argument',{})
    turn.setdefault('argument_original',deepcopy(original))
    question=question_info(turn['text'],session.get('topic','')) if role=='question' else None
    turn['argument']={'role':role,'cue':'Moderator reviewed this contribution','link':link,
                      'method':'moderator-correction','annotation_source':'moderator','role_confidence':None,
                      'evidence_requested':bool(question and question['evidence_requested']),
                      'question':question,'answers':answers,
                      'review':{'reason':reason.strip(),'time':datetime.now(timezone.utc).isoformat()}}
    # Corrections invalidate derived downstream references instead of leaving dangling semantic links.
    for later in updated['turns']:
        if later['number']<=number: continue
        argument=later.get('argument',{})
        stale_answers=role!='question' and any(a['turn']==number for a in argument.get('answers',[]))
        edge=argument.get('link')
        stale_edge=bool(edge and edge['turn']==number and (
            (edge.get('relation')=='answers' and role!='question') or
            (edge.get('relation')!='answers' and role in ('question','unclassified'))))
        if stale_answers or stale_edge:
            later.setdefault('argument_original',deepcopy(argument))
            if stale_answers: argument['answers']=[a for a in argument.get('answers',[]) if a['turn']!=number]
            if stale_edge: argument['link']=None
            argument['dependency_note']=f'Reference to turn {number} invalidated by moderator correction.'
    return updated
