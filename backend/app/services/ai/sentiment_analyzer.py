"""Sentiment analysis for English, Tamil, and Tanglish text.

Approach (rule-based baseline — production-swap ready):
  - Maintains positive / negative / intensifier word lists for English,
    Tamil, and Tanglish.
  - Score = (positive_hits - negative_hits) / total_tokens
  - Returns label + float score in [-1.0, 1.0].

To upgrade to an ML model, replace ``_score_text`` with a call to a
fine-tuned BERT / IndicBERT / MuRIL model loaded via ``transformers``.

The module is designed to be imported synchronously (no GPU required for
the rule-based default).
"""
import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Word lists
# ---------------------------------------------------------------------------

EN_POSITIVE = {
    'good', 'great', 'excellent', 'wonderful', 'amazing', 'fantastic',
    'helpful', 'thank', 'thanks', 'pleased', 'happy', 'satisfied',
    'appreciate', 'best', 'nice', 'perfect', 'love', 'brilliant',
    'efficient', 'resolved', 'fixed', 'quick', 'prompt', 'safe', 'clean',
}

EN_NEGATIVE = {
    'bad', 'worst', 'terrible', 'horrible', 'awful', 'disgusting',
    'pathetic', 'useless', 'corrupt', 'broken', 'failed', 'dirty',
    'delay', 'delayed', 'slow', 'inefficient', 'unsafe', 'dangerous',
    'complaint', 'problem', 'issue', 'waste', 'fraud', 'scam',
    'negligence', 'ignored', 'hopeless', 'helpless', 'unresolved',
}

EN_INTENSIFIERS = {'very', 'extremely', 'highly', 'absolutely', 'totally', 'so'}

# Tanglish positive tokens
TG_POSITIVE = {
    'nalla', 'supera', 'romba nalla', 'best', 'thanks', 'nandri',
    'vaazhga', 'semma', 'mass', 'clean', 'quick', 'fast', 'helpful',
}

# Tanglish negative tokens
TG_NEGATIVE = {
    'mosama', 'worse', 'ketta', 'problem', 'issue', 'complaint',
    'slow', 'dirty', 'nallave illa', 'waste', 'kodumai', 'bayangaram',
    'help pannala', 'pathukkala', 'corruption', 'cheat',
}

# Tamil (Unicode) positive roots (simplified)
TA_POSITIVE_RE = re.compile(
    r'நன்றி|சரி|நல்ல|சிறந்த|திருப்தி|பாராட்ட|மகிழ்ச்சி|வளர்ச்சி'
)

# Tamil negative roots (simplified)
TA_NEGATIVE_RE = re.compile(
    r'புகார்|சிக்கல்|தண்ணீர்\s*இல்லை|ஆபத்து|அழுக்கு|தாமதம்|ஊழல்|கவலை|ஏமாற்றம்'
)


@dataclass
class SentimentResult:
    label: str          # positive | negative | neutral | mixed
    score: float        # [-1.0, 1.0]
    language: str       # en | ta | tanglish | unknown
    details: dict = field(default_factory=dict)

    def to_dict(self):
        return {
            'label': self.label,
            'score': round(self.score, 4),
            'language': self.language,
            'details': self.details,
        }


def analyze_sentiment(text: str, language: str = 'en') -> SentimentResult:
    """Analyse the sentiment of *text* in the given *language*.

    Args:
        text:     Raw social media text.
        language: One of ``'en'``, ``'ta'``, ``'tanglish'``, ``'unknown'``.

    Returns:
        :class:`SentimentResult` with label, score, and details.
    """
    if not text or not text.strip():
        return SentimentResult(label='neutral', score=0.0, language=language)

    text_lower = text.lower()

    if language == 'ta':
        return _analyze_tamil(text)
    elif language == 'tanglish':
        return _analyze_tanglish(text_lower)
    else:
        return _analyze_english(text_lower)


# ---------------------------------------------------------------------------
# Per-language implementations
# ---------------------------------------------------------------------------

def _analyze_english(text: str) -> SentimentResult:
    tokens = re.findall(r'\b\w+\b', text)
    pos = neg = intensifier_boost = 0
    prev_was_intensifier = False

    for token in tokens:
        if token in EN_INTENSIFIERS:
            prev_was_intensifier = True
            continue
        boost = 2 if prev_was_intensifier else 1
        if token in EN_POSITIVE:
            pos += boost
        elif token in EN_NEGATIVE:
            neg += boost
        prev_was_intensifier = False

    return _build_result(pos, neg, 'en', {'positive_hits': pos, 'negative_hits': neg})


def _analyze_tanglish(text: str) -> SentimentResult:
    pos = sum(1 for w in TG_POSITIVE if w in text)
    neg = sum(1 for w in TG_NEGATIVE if w in text)
    return _build_result(pos, neg, 'tanglish', {'positive_hits': pos, 'negative_hits': neg})


def _analyze_tamil(text: str) -> SentimentResult:
    pos = len(TA_POSITIVE_RE.findall(text))
    neg = len(TA_NEGATIVE_RE.findall(text))
    return _build_result(pos, neg, 'ta', {'positive_hits': pos, 'negative_hits': neg})


def _build_result(pos: int, neg: int, language: str, details: dict) -> SentimentResult:
    total = pos + neg
    if total == 0:
        return SentimentResult(label='neutral', score=0.0, language=language, details=details)

    score = (pos - neg) / total  # range [-1, 1]

    if pos > 0 and neg > 0:
        label = 'mixed'
    elif score > 0:
        label = 'positive'
    else:
        label = 'negative'

    return SentimentResult(label=label, score=score, language=language, details=details)
