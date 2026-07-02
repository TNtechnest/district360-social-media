"""AI detection modules: complaint, emergency, spam, and trend.

All detectors use a keyword + pattern rule-based approach by default.
Each returns a structured result dict so the caller can cache it in
``CollectedPost.ai_result``.

For production upgrade:
  - Replace keyword matchers with fine-tuned classification models.
  - Complaint / emergency: fine-tune on district-specific labelled data.
  - Spam: train on a corpus of known spam + legit posts.
  - Trend: add TF-IDF / BM25 clustering across the rolling 24-hour window.
"""
import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ============================================================================
# COMPLAINT DETECTION
# ============================================================================

COMPLAINT_EN = re.compile(
    r'\b(complaint|complain|issue|problem|broken|not\s+working|damage|pothole|'
    r'water\s+cut|power\s+cut|garbage|sewage|blocked|leak|flood|encroachment|'
    r'corruption|bribe|negligence|delay|unresolved|ignored|no\s+response|'
    r'road\s+damage|no\s+water|no\s+electricity|illegal|waste)\b',
    re.IGNORECASE,
)

COMPLAINT_TG = re.compile(
    r'(complaint|pugar|poguthu|problem|issue|ketta|paathukala|help\s*pannala|'
    r'tank\s*illai|current\s*poguthu|tanni\s*varala|road\s*podiyum|'
    r'kuppai|nallave\s*illa|sari\s*pannala)',
    re.IGNORECASE,
)

COMPLAINT_TA = re.compile(
    r'(புகார்|சிக்கல்|சேதம்|குழி|தண்ணீர்\s*இல்லை|மின்சாரம்\s*இல்லை|'
    r'குப்பை|சாக்கடை|ஊழல்|தாமதம்|பதில்\s*இல்லை|கவனிக்கவில்லை)'
)


def detect_complaint(text: str, language: str = 'en') -> dict:
    """Return complaint detection result.

    Returns:
        Dict with ``is_complaint`` (bool), ``confidence`` (float 0-1),
        ``matched_keywords`` (list).
    """
    matches = _run_pattern(text, language, COMPLAINT_EN, COMPLAINT_TG, COMPLAINT_TA)
    is_complaint = len(matches) > 0
    confidence = min(len(matches) * 0.25, 1.0)
    return {
        'is_complaint': is_complaint,
        'confidence': round(confidence, 3),
        'matched_keywords': matches,
    }


# ============================================================================
# EMERGENCY DETECTION
# ============================================================================

EMERGENCY_EN = re.compile(
    r'\b(fire|accident|flood|collapse|drowning|casualty|death|died|dead|'
    r'explosion|gas\s*leak|landslide|earthquake|emergency|critical|urgent|'
    r'danger|hazard|injury|injured|trapped|sos|help\s+me|ambulance|'
    r'blood|hospital|911|rescue)\b',
    re.IGNORECASE,
)

EMERGENCY_TG = re.compile(
    r'(tee\s*pidikuthu|flood\s*aaguthu|accident|collapses|uyir\s*apaththu|'
    r'hospital\s*ponum|rescue\s*panunga|help\s*panunga|sos|danger)',
    re.IGNORECASE,
)

EMERGENCY_TA = re.compile(
    r'(தீ|வெள்ளம்|விபத்து|இடிந்து|உதவி\s*வேண்டும்|ஆபத்து|இறந்தார்|மயக்கம்|'
    r'சிக்கிக்கொண்டனர்|காப்பாற்றுங்கள்|அவசரம்)'
)

# Emergency confidence threshold — even a single strong keyword is flagged
EMERGENCY_SINGLE_KEYWORD_CONFIDENCE = 0.8


def detect_emergency(text: str, language: str = 'en') -> dict:
    """Return emergency detection result.

    Any single strong emergency keyword triggers a high-confidence flag
    because false negatives are worse than false positives here.

    Returns:
        Dict with ``is_emergency`` (bool), ``confidence`` (float 0-1),
        ``matched_keywords`` (list).
    """
    matches = _run_pattern(text, language, EMERGENCY_EN, EMERGENCY_TG, EMERGENCY_TA)
    is_emergency = len(matches) > 0
    confidence = EMERGENCY_SINGLE_KEYWORD_CONFIDENCE if is_emergency else 0.0
    return {
        'is_emergency': is_emergency,
        'confidence': round(confidence, 3),
        'matched_keywords': matches,
    }


# ============================================================================
# SPAM DETECTION
# ============================================================================

SPAM_EN = re.compile(
    r'\b(click\s+here|buy\s+now|free\s+offer|limited\s+time|winner|won|'
    r'prize|lottery|casino|bet|earn\s+money|make\s+money|work\s+from\s+home|'
    r'guaranteed|100\s*%\s*profit|investment\s+opportunity|WhatsApp\s+me|'
    r'call\s+now|discount\s+\d+%|crypto|bitcoin|forex)\b',
    re.IGNORECASE,
)

SPAM_TG = re.compile(
    r'(free\s*offer|click\s*here|earn\s*money|prize|lottery|paise\s*kamao|'
    r'paisa\s*double|winning\s*prize)',
    re.IGNORECASE,
)

SPAM_TA = re.compile(
    r'(இலவச\s*சலுகை|பணம்\s*சம்பாதிக்க|வெற்றி\s*பரிசு|கிளிக்\s*செய்யுங்கள்)'
)

# High repetition is a spam signal
REPETITION_RE = re.compile(r'(.{3,})\1{3,}')


def detect_spam(text: str, language: str = 'en') -> dict:
    """Return spam detection result.

    Returns:
        Dict with ``is_spam`` (bool), ``confidence`` (float 0-1),
        ``reasons`` (list of str).
    """
    reasons = []
    keyword_matches = _run_pattern(text, language, SPAM_EN, SPAM_TG, SPAM_TA)
    if keyword_matches:
        reasons.append(f'spam_keywords: {keyword_matches}')

    if REPETITION_RE.search(text):
        reasons.append('high_repetition')

    # Very short text with a URL is suspicious
    url_count = len(re.findall(r'https?://', text))
    if url_count >= 3:
        reasons.append('multiple_urls')

    is_spam = len(reasons) > 0
    confidence = min(len(reasons) * 0.35, 1.0)
    return {
        'is_spam': is_spam,
        'confidence': round(confidence, 3),
        'reasons': reasons,
    }


# ============================================================================
# TREND DETECTION
# ============================================================================

# Topic taxonomy for district governance
TREND_TOPICS = {
    'water': re.compile(
        r'\b(water|tanni|தண்ணீர்|tanker|pipeline|leak|flood|sewage|drain)\b',
        re.IGNORECASE,
    ),
    'roads': re.compile(
        r'\b(road|pothole|footpath|pavement|signal|traffic|highway|bridge|'
        r'road\s*damage|saddak|sadak)\b',
        re.IGNORECASE,
    ),
    'electricity': re.compile(
        r'\b(electricity|power\s*cut|blackout|current\s*poguthu|மின்சாரம்|'
        r'voltage|transformer|streetlight)\b',
        re.IGNORECASE,
    ),
    'garbage': re.compile(
        r'\b(garbage|waste|kuppai|குப்பை|dustbin|sanitation|clean|dirty)\b',
        re.IGNORECASE,
    ),
    'drainage': re.compile(
        r'\b(drainage|drain|storm\s*water|canal|sewer|sewage|blocked\s*drain|'
        r'waterlogging|standing\s*water|சாக்கடை|வடிகால்)\b',
        re.IGNORECASE,
    ),
    'health': re.compile(
        r'\b(hospital|clinic|doctor|medicine|fever|disease|mosquito|dengue|'
        r'malaria|health\s*camp|ambulance)\b',
        re.IGNORECASE,
    ),
    'education': re.compile(
        r'\b(school|college|education|teacher|student|exam|scholarship|'
        r'palli|kalvi|கல்வி)\b',
        re.IGNORECASE,
    ),
    'safety': re.compile(
        r'\b(safety|crime|theft|police|harassment|eve\s*teasing|fire|'
        r'streetlight|cctv|patrolling)\b',
        re.IGNORECASE,
    ),
    'corruption': re.compile(
        r'\b(corruption|bribe|fraud|scam|misuse|embezzle|ஊழல்|லஞ்சம்)\b',
        re.IGNORECASE,
    ),
}


def detect_trends(text: str) -> dict:
    """Extract topic trend tags from *text*.

    Returns:
        Dict with ``tags`` (list of topic strings), ``top_topic`` (str or None).
    """
    matched_topics = [topic for topic, pattern in TREND_TOPICS.items() if pattern.search(text)]
    return {
        'tags': matched_topics,
        'top_topic': matched_topics[0] if matched_topics else None,
    }


# ============================================================================
# Internal helpers
# ============================================================================

def _run_pattern(
    text: str, language: str,
    en_pat: re.Pattern, tg_pat: re.Pattern, ta_pat: re.Pattern,
) -> list[str]:
    """Run the appropriate pattern(s) and return unique matched strings."""
    matched = set()
    if language in ('en', 'tanglish', 'unknown'):
        matched.update(m.lower() for m in en_pat.findall(text))
    if language in ('tanglish', 'unknown'):
        matched.update(m.lower() for m in tg_pat.findall(text))
    if language == 'ta':
        matched.update(m for m in ta_pat.findall(text))
    # Always run English patterns as a fallback
    if language not in ('en',):
        matched.update(m.lower() for m in en_pat.findall(text))
    return list(matched)
