"""Topic relevance scores and debounced drift alerts for one conversation."""

import re

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
ACKNOWLEDGEMENTS = {
    "okay", "ok", "yes", "no", "understood", "i agree", "go on",
    "please continue", "that sounds reasonable", "that is a fair concern",
}
CONVERSATION_MANAGEMENT = ACKNOWLEDGEMENTS | {
    "and you", "what about you", "how about you", "you first", "your turn",
    "go ahead", "i see", "i got it", "fair enough", "fair point", "makes sense",
    "really", "think", "what do", "what do you", "what do you think about",
    "do you think", "what do you mean", "how so", "why is that", "what about that",
    "do you agree", "do you agree with that", "anything else",
    "tell me more", "can you tell me more", "could you tell me more",
    "can you elaborate", "could you elaborate", "could you explain", "can you explain that",
    "could you explain that", "could you expand on that", "can you clarify that",
    "can you repeat that", "could you repeat that", "can you repeat",
    "say that again", "can you hear me", "can you hear me now",
    "hold on", "hang on", "one second", "give me a second", "let me finish",
    "let me think", "let me think about that", "thanks", "thank you",
}
FILLERS = {"uh", "um", "erm", "ah", "hmm", "well", "yeah", "yep", "okay", "ok", "right", "so"}
OPINION_PROMPT = (
    r"(?:what do you think|what are your thoughts|what(?: is|'?s) your (?:take|opinion))"
)
INVITE_OPINION = re.compile(
    OPINION_PROMPT
    + r"(?: (?:about|on|of) (?:it|this|that|all of this|all of that|the topic|"
    r"(?:this|that|my|the) (?:point|idea|argument|proposal)|what (?:i|we|you) (?:just )?said))?"
)
OPINION_SUBJECT = re.compile(
    rf"^(?:(?:{'|'.join(sorted(FILLERS))})[\s,]+)*"
    + OPINION_PROMPT
    + r"\s+(?:about|on|of)\s+(?P<subject>.+)$",
    re.IGNORECASE,
)
FOLLOW_UP = re.compile(
    r"^(how much|how long|how often|who would|who pays|could|can|would|what about|where could|is that|why)\b"
)


def is_conversation_management(text):
    """Recognize complete floor-management phrases, including unpunctuated ASR."""
    clauses = re.split(r"[.!?…]+", text)
    heard_words = False
    for clause in clauses:
        tokens = re.findall(r"\w+", clause.casefold().replace("'", "").replace("’", ""))
        if not tokens:
            continue
        heard_words = True
        trimmed = []
        if any(word not in FILLERS for word in tokens):
            first = next(i for i, word in enumerate(tokens) if word not in FILLERS)
            # Only strip terminal hesitation sounds. Words like "right" can be
            # part of the phrase "you're right", and should not be removed.
            trimmed = tokens[first:]
            while trimmed[-1] in {"uh", "um", "erm", "hmm"}:
                trimmed.pop()
        phrase = " ".join(trimmed)
        if phrase and phrase not in CONVERSATION_MANAGEMENT and not INVITE_OPINION.fullmatch(phrase):
            return False
    return heard_words


def topic_content(text):
    """Score the named subject of a generic opinion prompt."""
    match = OPINION_SUBJECT.match(text.replace("’", "'"))
    if match:
        return match["subject"].strip(" .?!…") or text
    return text


class TopicMonitor:
    """Keep the original motion as the reference throughout a session."""

    def __init__(self, topic, threshold, backend="minilm", use_context=True, encoder=None):
        if not isinstance(topic, str) or len(topic.split()) < 3:
            raise ValueError("The discussion topic must contain at least three words")
        if backend not in {"minilm", "tfidf"}:
            raise ValueError("Unknown relevance backend")
        if not np.isfinite(threshold) or not 0 < threshold < 1:
            raise ValueError("The similarity threshold must be between zero and one")
        self.topic = topic.strip()
        self.threshold = float(threshold)
        self.backend = backend
        self.use_context = use_context
        self.encoder = encoder
        if backend == "minilm":
            if self.encoder is None:
                from sentence_transformers import SentenceTransformer

                self.encoder = SentenceTransformer(MODEL_ID, revision=MODEL_REVISION, device="cpu")
            self.topic_vector = self.encoder.encode(self.topic, normalize_embeddings=True)
        self.previous_text = ""
        self.previous_relevant = False
        self.off_topic_count = 0
        self.alert_active = False

    def similarity(self, text):
        if self.backend == "minilm":
            vector = self.encoder.encode(text, normalize_embeddings=True)
            return float(np.dot(self.topic_vector, vector))
        # This lexical baseline uses the current text and topic, without future turns or labels.
        vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        matrix = vectorizer.fit_transform([self.topic, text])
        return float((matrix[0] @ matrix[1].T).toarray()[0, 0])

    def process(self, text):
        if not isinstance(text, str):
            raise TypeError("Utterances must be strings")
        text = re.sub(r"\s+", " ", text).strip()
        normalized = re.sub(r"[^\w\s]", "", text.casefold()).strip()
        management = is_conversation_management(text)
        if not normalized or management:
            self.previous_relevant = False
            result = {
                "state": "unclear", "score": None, "direct_score": None,
                "used_context": False, "alert": False, "off_topic_count": self.off_topic_count,
            }
            if management:
                result["reason"] = "conversation_management"
            return result

        direct_score = self.similarity(topic_content(text))
        score = direct_score
        used_context = (
            self.use_context and self.previous_relevant
            and len(text.split()) <= 9 and FOLLOW_UP.match(normalized) is not None
        )
        if used_context:
            score = max(score, self.similarity(self.previous_text + " " + text))
        state = "on_topic" if score >= self.threshold else "off_topic"
        alert = False
        if state == "on_topic":
            self.off_topic_count = 0
            self.alert_active = False
        else:
            self.off_topic_count += 1
            alert = self.off_topic_count >= 2 and not self.alert_active
            self.alert_active = self.alert_active or alert
        self.previous_text = text
        # An inherited follow-up cannot indefinitely extend the topic anchor.
        self.previous_relevant = direct_score >= self.threshold
        return {
            "state": state, "score": score, "direct_score": direct_score,
            "used_context": used_context, "alert": alert,
            "off_topic_count": self.off_topic_count,
        }
