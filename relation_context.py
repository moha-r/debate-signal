"""Language features for explicit references between speaking turns."""
import re
import math

_MODAL_ACTION = re.compile(
    r"\b(?:should|could|would|must|might|ought to)\s+"
    r"(?:(?:also|still|instead|probably|perhaps|not|only|just)\s+){0,2}"
    r"(?:(?:need|have) to\s+)?(?:be\s+)?([a-z]+)\b",re.I)
_REPLY_CUE = re.compile(r"\b(?:because|since|therefore|instead|thus|for example|for instance|according to)\b|^(?:that|this|these|those) (?:is|are|would|will|could|cannot|does|suggests?|\w+ (?:is|would|could))\b",re.I)
_AGREEMENT = re.compile(r"^(?:i agree|we agree|you(?:'re| are) right|that's a fair point)\b",re.I)

_INTRO = re.compile(
    r"^(?:i (?:agree|disagree)(?: that| because)?|we agree(?: that)?|"
    r"you(?:'re| are) right(?: that)?|that's a fair point|"
    r"however|on the other hand|on the contrary|for example|for instance)\b[\s,:;.!-]*",
    re.I,
)


def strip_speech_act(text):
    cleaned = _INTRO.sub('',text.strip(),count=1)
    return cleaned if len(cleaned.split())>=3 else text


def is_explicit_agreement(text):
    return bool(_AGREEMENT.match(text.strip()))


def action_verb(text):
    found = _MODAL_ACTION.search(text)
    if found is None:
        return None
    verb = found.group(1).lower()
    return None if verb in ('be','have','need','require','seem') else verb


def has_reply_cue(text):
    return bool(_REPLY_CUE.search(text.strip()))


def relation_rank(confidence, similarity, distance):
    return .7*confidence+.25*similarity+.05*math.exp(-distance/8)


def retrieval_score(similarity, distance, detail_overlap):
    # Chosen on the radio development episodes at the existing six-pair budget.
    return similarity+.22/distance+.10*detail_overlap
