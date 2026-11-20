"""Shared word-level preprocessing for the personal attack classifier."""

from functools import lru_cache
import html
import re
import unicodedata

from nltk.stem import SnowballStemmer
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


URL = re.compile(r"\b(?:https?://|www\.)[^\s<>]+")
HTML_TAG = re.compile(r"<!--[\s\S]*?-->|</?[a-z][a-z0-9:-]*(?:\s[^<>]*)?/?>")
WORD = re.compile(r"[^\W_]+(?:'[^\W_]+)*")
APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "ʼ": "'"})
EXPANSIONS = {
    "can't": "can not",
    "cannot": "can not",
    "won't": "will not",
    "shan't": "shall not",
    "i'm": "i am",
    "you're": "you are",
    "we're": "we are",
    "they're": "they are",
    "i've": "i have",
    "you've": "you have",
    "we've": "we have",
    "they've": "they have",
    "idk": "i do not know",
    "btw": "by the way",
    "imo": "in my opinion",
    "imho": "in my humble opinion",
    "pls": "please",
    "plz": "please",
    "thx": "thanks",
}
NEGATIVE_CONTRACTION = re.compile(
    r"\b(do|does|did|is|are|was|were|have|has|had|could|should|would|must|might|need)n't\b"
)
KEEP_FORM = frozenset({"i", "you", "your", "yours", "no", "not", "nor", "never", "lah", "ya", "lol"})
STEMMER = SnowballStemmer("english")


def tokenize(text: str) -> list[str]:
    """Remove export noise and return normalized word tokens."""
    text = text.replace("NEWLINE_TOKEN", " ").replace("TAB_TOKEN", " ")
    text = unicodedata.normalize("NFKC", html.unescape(text)).translate(APOSTROPHES).casefold()
    text = HTML_TAG.sub(" ", text)
    text = URL.sub(" ", text)
    text = NEGATIVE_CONTRACTION.sub(r"\1 not", text)
    return [
        word
        for token in WORD.findall(text)
        for word in EXPANSIONS.get(token, token).split()
    ]


@lru_cache(maxsize=32_768)
def stem_word(word: str) -> str:
    if word in KEEP_FORM or not word.isascii() or not word.isalpha():
        return word
    return STEMMER.stem(word)


def preprocess_text(text: str) -> str:
    """Return the same model text used for deduplication and inference."""
    return " ".join(stem_word(word) for word in tokenize(text))


def make_vectorizer(
    ngram_range: tuple[int, int] = (1, 1),
    max_features: int | None = 50_000,
    min_df: int = 2,
) -> TfidfVectorizer:
    """Build an unfitted vectorizer for use inside a scikit-learn pipeline."""
    return TfidfVectorizer(
        preprocessor=preprocess_text,
        tokenizer=str.split,
        token_pattern=None,
        lowercase=False,
        stop_words=None,
        ngram_range=ngram_range,
        max_features=max_features,
        min_df=min_df,
        sublinear_tf=True,
        dtype=np.float32,
    )
