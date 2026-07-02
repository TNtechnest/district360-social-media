"""Language detection — English, Tamil (ta), and Tanglish.

Tanglish is Tamil written in Roman script (transliterated Tamil), extremely
common in social media posts from Tamil Nadu districts.

Strategy (no heavy ML dependency required at baseline):
  1. Unicode range check → if ≥ 30 % of characters fall in the Tamil Unicode
     block (U+0B80–U+0BFF) → ``'ta'``
  2. Tanglish keyword heuristics → common Tamil words spelled in ASCII
     (``neenga``, ``vanakkam``, ``ungaluku``, etc.) → ``'tanglish'``
  3. Fallback → ``'en'``

For production, swap ``detect_language`` with an ML-based detector
(e.g. ``langdetect``, ``fasttext``, or a fine-tuned model).
"""
import re
import unicodedata
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tamil Unicode block: U+0B80 – U+0BFF
# ---------------------------------------------------------------------------
TAMIL_UNICODE_START = 0x0B80
TAMIL_UNICODE_END   = 0x0BFF

# ---------------------------------------------------------------------------
# High-frequency Tanglish words / phrases (case-insensitive substrings)
# These are commonly used Tamil words written in English characters.
# ---------------------------------------------------------------------------
TANGLISH_MARKERS = [
    'vanakkam', 'neenga', 'ungaluku', 'enna', 'sollunga', 'parunga',
    'pannunga', 'theriyuma', 'pls sollu', 'ippo', 'appove', 'yov', 'dei',
    'macha', 'da', 'bro', 'enna panrom', 'ellam', 'eppo', 'enga', 'romba',
    'konjam', 'paaru', 'solli', 'tholaivu', 'nalla', 'illa', 'sollu',
    'aama', 'theriyala', 'kandupidicha', 'saapadu', 'pesuvom', 'vaazhga',
    'tamizh', 'tamilnadu', 'thamizh', 'ooru', 'veetu', 'vallamai',
    'mannargudi', 'coimbatore', 'madurai', 'trichy', 'chennai nalla',
]

TANGLISH_RE = re.compile(
    '|'.join(
        rf'(?<![a-z]){re.escape(w)}(?![a-z])'
        for w in TANGLISH_MARKERS
    ),
    re.IGNORECASE,
)

# Minimum fraction of Tamil Unicode characters to classify as ``'ta'``
TAMIL_CHAR_THRESHOLD = 0.25


def detect_language(text: str) -> str:
    """Detect whether *text* is English, Tamil, or Tanglish.

    Args:
        text: Raw social media text.

    Returns:
        One of: ``'ta'`` | ``'tanglish'`` | ``'en'`` | ``'unknown'``
    """
    if not text or not text.strip():
        return 'unknown'

    # -- Tamil Unicode check
    chars = [c for c in text if unicodedata.category(c) not in ('Zs', 'Cc')]
    if chars:
        tamil_count = sum(
            1 for c in chars if TAMIL_UNICODE_START <= ord(c) <= TAMIL_UNICODE_END
        )
        if tamil_count / len(chars) >= TAMIL_CHAR_THRESHOLD:
            return 'ta'

    # -- Tanglish heuristic
    if TANGLISH_RE.search(text):
        return 'tanglish'

    return 'en'


def normalize_tanglish(text: str) -> str:
    """Basic Tanglish normalisation — lowercase and trim outer whitespace.

    More sophisticated transliteration can be added here (e.g. mapping
    ``neenga`` → ``நீங்க``) using a lookup table or seq2seq model.

    Args:
        text: Raw Tanglish text.

    Returns:
        Normalised text string.
    """
    return text.lower().strip()
