"""Causal question-to-response matching, independent of the argument graph's link."""
import math
import re
from argument_models import vector, words

QUESTION=re.compile(r'^(?:what|why|how|who|when|where|which|can|could|should|would|do|does|did|is|are)\b',re.I)
INDIRECT=re.compile(r"^(?:i (?:wonder|would like to know)|please (?:explain|show|provide|tell|clarify|give)|(?:can|could|would) you (?:explain|show|provide|tell|clarify|give))\b",re.I)
EVIDENCE=re.compile(r'\b(?:evidence|source|sources|proof|study|data|support that)\b|\bwhich (?:estimate|report|survey) supports?\b',re.I)
GENERIC={'conclus','claim','support','evid','sourc','question','explain','estim','expect','provid','show','use'}
NUMBER=re.compile(
    r'\b(?:\d+(?:\.\d+)?|zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|'
    r'thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|'
    r'sixty|seventy|eighty|ninety|hundred|thousand|million|billion)\b', re.I)
CONDITIONAL_VALUE=re.compile(r"\b(?:depends? on|would depend on|varies? (?:with|by)|would vary|to be determined)\b",re.I)
PERSON_CUE=re.compile(r'\b(?:staff|department|team|committee|volunteers?|drivers?|operators?|workers?|employees?|officers?|coordinators?|attendants?|teachers?|engineers?|contractors?|council)\b',re.I)
LOCATION_CUE=re.compile(r'\b(?:located|adjacent|next to|across from|in front of|behind|collection point|drop.off (?:point|site)|connects? .+? to)\b',re.I)
PLATFORM_TYPE=re.compile(r'\b(?:what|which)\s+(?:video\s+)?(?:platform|software|application|app)\b',re.I)
PLATFORM_ANSWER=re.compile(r'\b(?:platform|software|application|app|zoom|teams|webex|google meet)\b',re.I)
ATTRIBUTION=re.compile(r'\b(?:according to|published|reported|study found|survey showed|audit found|report states)\b',re.I)
REFERENCE=re.compile(r"\b(?:that|this|those|these)\s+(?:claim|conclusion|number|figure|statement|point|estimate|argument|proposal)\b",re.I)
ACKNOWLEDGEMENT=re.compile(r"^(?:i agree|we agree|you(?:'re| are) right|fair point)\b",re.I)
QUANTITY_UNITS=re.compile(r'^(?:\s*(?:per\b|each\b|hours?\b|minutes?\b|days?\b|weeks?\b|months?\b|years?\b|dollars?\b|pounds?\b|euros?\b|percent\b|%))',re.I)


def outside_quotes(text):
    return re.sub(r'["“][^"”]*["”]',' ',text).replace('’',"'")


def question_kind(text):
    if EVIDENCE.search(text): return 'evidence'
    if PLATFORM_TYPE.search(text): return 'platform'
    if re.search(r'\b(?:how many|how much|what (?:is the )?(?:cost|price|number))\b',text,re.I): return 'quantity'
    if re.search(r'\bwhat (?:is|are|would be|will be) (?:the )?(?:[a-z-]+ ){0,5}(?:cost|price|number|capacity|budget|amount|percentage|duration|fee|rate)\b',text,re.I): return 'quantity'
    if re.search(r'\bwhat (?:would|will|does|did) [^?]{1,80} (?:cost|weigh|measure)\b',text,re.I): return 'quantity'
    # The interrogative head determines the answer type. Embedded relative clauses do not.
    head=re.search(r'\b(what time|what|which|how|why|when|who|where)\b',text,re.I)
    if head:
        kind={'when':'time','what time':'time','who':'person','where':'location'}
        return kind.get(head.group(1).lower(),'explanation')
    return 'explanation'


def question_info(text,motion=''):
    visible=outside_quotes(text)
    question=bool('?' in visible or QUESTION.match(visible.strip()) or INDIRECT.match(visible.strip()))
    return {'is_question':question,'kind':question_kind(visible),
            'focus':sorted(words(visible)-words(motion)-GENERIC),
            'evidence_requested':question and bool(EVIDENCE.search(visible))}


def response_status(text,kind):
    normalized=outside_quotes(text).casefold()
    if re.search(r"\b(?:refuse to answer|(?:will not|won't|would rather not) answer|rather discuss .* than answer|decline to answer)\b",normalized): return 'declined'
    if re.search(r"\b(?:do not have|don't have|have not (?:provided|supplied)|haven't (?:provided|supplied)|no (?:data|evidence|source)|do not (?:yet )?know|don't (?:yet )?know)\b",normalized):
        return 'insufficient_evidence' if kind=='evidence' else 'uncertain_answer'
    if kind=='quantity' and not NUMBER.search(normalized): return 'partial_answer'
    return 'possible_answer'


def askable_text(text):
    plain=re.sub(r'^(?:i wonder|i would like to know|please explain|please clarify)\s+', '',text.strip(), flags=re.I)
    # Embedded questions often retain statement order after removing the request.
    return re.sub(r'^(how|why|where|when)\s+(.{2,72}?)\s+(could|would|will|can|should)\s+',
                  r'\1 \3 \2 ',plain, count=1, flags=re.I)


def find_responses(turn,previous,encoder):
    if turn['personal_attack'] or question_info(turn['text']).get('is_question'): return []
    supplied={a['turn'] for t in previous for a in t.get('argument',{}).get('answers',[]) if a['status'] in ('possible_answer','confirmed_answer')}
    questions=[t for t in previous if t.get('argument',{}).get('role')=='question' and t['number'] not in supplied]
    if not questions: return []
    current_words=words(turn['text'])
    text=outside_quotes(turn['text']).strip()
    current_vector=vector(encoder,turn['text'])
    candidates=[]
    semantic=[]
    for q in questions:
        info=q['argument'].get('question') or question_info(q['text'],turn.get('_topic_text',''))
        kind=question_kind(outside_quotes(q['text']))
        focus=set(info.get('focus',[]))
        age=turn['number']-q['number']
        status=response_status(turn['text'],kind)
        lexical=len(focus&current_words)/max(1,len(focus))
        if kind=='quantity' and status=='partial_answer' and not (lexical and CONDITIONAL_VALUE.search(text)):
            continue
        # A direct refusal or admission of missing information is still worth attaching to its question.
        if age==1 and status in ('declined','insufficient_evidence','uncertain_answer'):
            candidates.append((.92,q,status,None));continue
        if ACKNOWLEDGEMENT.match(text) and not re.search(r'[.!]\s+\w',text):
            continue
        if kind=='platform' and status=='possible_answer' and (not PLATFORM_ANSWER.search(text)
                 or re.search(r'\b(?:should|must) (?:also )?(?:allow|support|offer|include|provide)\b',text,re.I)):
            continue
        if age==1 and kind=='quantity' and status=='possible_answer' and len(text.split())<=6:
            value=NUMBER.match(text)
            if value and (not text[value.end():].strip(' .!') or QUANTITY_UNITS.match(text[value.end():])):
                candidates.append((.70,q,status,None))
                continue
        slot_answer=kind in ('quantity','time','person','location') and age==1 and len(turn['text'].split())<=12
        if kind=='evidence' and re.search(r'\b(?:should|could)\b',turn['text'],re.I) and not re.search(r'\b(?:because|example|according|data|study|research|survey)\b',turn['text'],re.I): continue
        similarity=float(current_vector@vector(encoder,q['text']))
        score=.55*max(0,similarity)+.35*lexical+.10*math.exp(-age/10)
        if kind=='evidence' and ATTRIBUTION.search(text) and similarity>=.35:
            shared=words(q['text'])&current_words
            if lexical or shared:
                candidates.append((max(.53,score),q,status,None))
                continue
        if kind=='platform' and status=='possible_answer' and similarity>=.35 and lexical:
            candidates.append((max(.57,score),q,status,None))
            continue
        person=kind=='person' and PERSON_CUE.search(text)
        place=kind=='location' and LOCATION_CUE.search(text)
        if place and age==1 and similarity>=.20:
            candidates.append((max(score,.60),q,status,None))
            continue
        if status=='possible_answer' and kind in ('person','location','quantity','explanation') and (
                similarity>=.28 or lexical or age==1 and (person or place)):
            semantic.append((score,q,status,kind,similarity,lexical,bool(person)))
            continue
        if focus and lexical==0 and not slot_answer or not focus and age>1:
            continue
        if score>=.44 and (similarity>=.20 or lexical>=.5):
            candidates.append((score,q,status,None))
    if semantic:
        semantic.sort(key=lambda item:(item[0],item[1]['number']),reverse=True)
        shortlisted=semantic[:4]
        # Keep the lexical matcher available for test encoders and deployments without the checkpoint.
        extracted=[None]*len(shortlisted)
        if len(current_vector)==384:
            from answer_extraction import extract_answers
            extracted=extract_answers([askable_text(item[1]['text']) for item in shortlisted],turn['text'])
        for item,span in zip(shortlisted,extracted):
            score,q,status,kind,similarity,lexical,person=item
            if span is None:
                if score>=.44 and (similarity>=.20 or lexical>=.5) and lexical:
                    candidates.append((score,q,status,None))
                continue
            if span['margin']<=0:
                if kind=='explanation' and lexical>=.75 and similarity>=.45 and len(current_words)>=3:
                    candidates.append((score,q,status,None))
                continue
            if kind=='quantity' and not NUMBER.search(span['text']):
                continue
            if kind=='person' and not person and lexical<.5:
                continue
            # Grounded spans may answer in different words from the spoken question.
            strength=1/(1+math.exp(-min(span['margin'],30)/4))
            candidates.append((.55*strength+.30*max(0,similarity)+.15*lexical,q,status,span))
    if not candidates: return []
    candidates.sort(key=lambda item:(item[0],item[1]['number']),reverse=True)
    if len(candidates)>1 and candidates[0][0]-candidates[1][0]<.025: return []
    score,q,status,span=candidates[0]
    response={'turn':q['number'],'status':status,'confidence':round(min(score,1),4),'tentative':True}
    if span is not None:
        response['answer_span']={key:span[key] for key in ('text','start','end')}
    return [response]
