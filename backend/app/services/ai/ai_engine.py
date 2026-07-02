"""AI Engine — orchestrates all NLP / detection passes on a single text.

Entry point for the AI pipeline.  Call ``analyze(text)`` to get a full
analysis result that can be stored in ``CollectedPost.ai_result``.

Pipeline:
  1. Language detection
  2. Sentiment analysis
  3. Complaint detection
  4. Emergency detection
  5. Spam detection
  6. Trend / topic extraction
  7. Reply suggestion

All steps are synchronous and CPU-only by default (no GPU / API calls).
To plug in an LLM API, override the individual sub-module functions or
call ``analyze`` from a Celery task.
"""
import logging
import re
from dataclasses import dataclass, field

from app.services.ai.language_detector import detect_language
from app.services.ai.sentiment_analyzer import analyze_sentiment
from app.services.ai.detectors import detect_complaint, detect_emergency, detect_spam, detect_trends
from app.services.ai.reply_suggester import suggest_reply

logger = logging.getLogger(__name__)


@dataclass
class AIAnalysisResult:
    """Full AI analysis result for one piece of social content."""
    language: str
    sentiment_label: str
    sentiment_score: float
    is_complaint: bool
    complaint_confidence: float
    is_emergency: bool
    emergency_confidence: float
    is_spam: bool
    spam_confidence: float
    category: str
    issue_type: str | None
    keywords: list
    summary: str
    trend_tags: list
    top_topic: str | None
    suggested_reply: str
    reply_category: str
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            'language': self.language,
            'sentiment': {
                'label': self.sentiment_label,
                'score': self.sentiment_score,
            },
            'complaint': {
                'detected': self.is_complaint,
                'confidence': self.complaint_confidence,
            },
            'emergency': {
                'detected': self.is_emergency,
                'confidence': self.emergency_confidence,
            },
            'spam': {
                'detected': self.is_spam,
                'confidence': self.spam_confidence,
            },
            'category': self.category,
            'issue_type': self.issue_type,
            'keywords': self.keywords,
            'summary': self.summary,
            'trends': {
                'tags': self.trend_tags,
                'top_topic': self.top_topic,
            },
            'reply': {
                'suggested': self.suggested_reply,
                'category': self.reply_category,
            },
        }

    def to_post_fields(self) -> dict:
        """Extract the flat fields that map directly to CollectedPost columns."""
        return {
            'language': self.language,
            'sentiment': self.sentiment_label,
            'sentiment_score': self.sentiment_score,
            'is_complaint': self.is_complaint,
            'is_emergency': self.is_emergency,
            'is_spam': self.is_spam,
            'trend_tags': self.trend_tags,
            'category': self.category,
            'issue_type': self.issue_type,
            'keywords': self.keywords,
            'summary': self.summary,
            'suggested_reply': self.suggested_reply,
            'ai_result': self.to_dict(),
            'ai_status': 'processed',
        }


def analyze(
    text: str,
    district_name: str = 'District360',
    ref_id: str = 'N/A',
) -> AIAnalysisResult:
    """Run the full AI pipeline on *text*.

    Args:
        text:          Raw social media content.
        district_name: Used in reply template personalisation.
        ref_id:        Tracking reference included in suggested reply.

    Returns:
        :class:`AIAnalysisResult` with all analysis fields populated.
    """
    if not text or not text.strip():
        return _empty_result()

    try:
        # Step 1 — language
        language = detect_language(text)

        # Step 2 — sentiment
        sentiment = analyze_sentiment(text, language)

        # Step 3 — complaint
        complaint = detect_complaint(text, language)

        # Step 4 — emergency
        emergency = detect_emergency(text, language)

        # Step 5 — spam
        spam = detect_spam(text, language)

        # Step 6 — trends
        trends = detect_trends(text)

        # Step 7 — Phase 6 categorisation, keyword extraction, and summary
        category = _classify_category(
            sentiment_label=sentiment.label,
            is_complaint=complaint['is_complaint'],
            is_emergency=emergency['is_emergency'],
            is_spam=spam['is_spam'],
            text=text,
        )
        keywords = _extract_keywords(
            text=text,
            complaint_keywords=complaint.get('matched_keywords', []),
            emergency_keywords=emergency.get('matched_keywords', []),
            spam_reasons=spam.get('reasons', []),
            trend_tags=trends.get('tags', []),
        )
        issue_type = _detect_issue_type(trends.get('tags', []), keywords)
        summary = _summarize_comment(
            text=text,
            category=category,
            top_topic=issue_type or trends.get('top_topic'),
        )

        # Step 8 — reply suggestion
        reply = suggest_reply(
            text=text,
            language=language,
            is_complaint=complaint['is_complaint'],
            is_emergency=emergency['is_emergency'],
            sentiment_label=sentiment.label,
            district_name=district_name,
            ref_id=ref_id,
            topic=trends.get('top_topic') or 'the reported issue',
        )

        return AIAnalysisResult(
            language=language,
            sentiment_label=sentiment.label,
            sentiment_score=sentiment.score,
            is_complaint=complaint['is_complaint'],
            complaint_confidence=complaint['confidence'],
            is_emergency=emergency['is_emergency'],
            emergency_confidence=emergency['confidence'],
            is_spam=spam['is_spam'],
            spam_confidence=spam['confidence'],
            category=category,
            issue_type=issue_type,
            keywords=keywords,
            summary=summary,
            trend_tags=trends.get('tags', []),
            top_topic=trends.get('top_topic'),
            suggested_reply=reply.suggested_reply,
            reply_category=reply.category,
            raw={
                'complaint_keywords': complaint.get('matched_keywords', []),
                'emergency_keywords': emergency.get('matched_keywords', []),
                'spam_reasons': spam.get('reasons', []),
            },
        )

    except Exception:
        logger.exception('AI Engine failed to analyse text (first 100 chars): %s', text[:100])
        return _empty_result(ai_status_failed=True)


def _empty_result(ai_status_failed: bool = False) -> AIAnalysisResult:
    return AIAnalysisResult(
        language='unknown',
        sentiment_label='neutral',
        sentiment_score=0.0,
        is_complaint=False,
        complaint_confidence=0.0,
        is_emergency=False,
        emergency_confidence=0.0,
        is_spam=False,
        spam_confidence=0.0,
        category='neutral',
        issue_type=None,
        keywords=[],
        summary='No analysable comment text was provided.',
        trend_tags=[],
        top_topic=None,
        suggested_reply='',
        reply_category='general',
    )


def _classify_category(
    sentiment_label: str,
    is_complaint: bool,
    is_emergency: bool,
    is_spam: bool,
    text: str,
) -> str:
    """Map detector output into the Phase 6 category taxonomy."""
    if is_spam:
        return 'spam'
    if is_complaint or is_emergency:
        return 'complaint'
    if '?' in text or re.search(r'\b(what|when|where|why|how|can|could|will|is|are)\b', text, re.IGNORECASE):
        return 'question'
    if sentiment_label == 'positive':
        return 'positive'
    if sentiment_label == 'negative':
        return 'negative'
    return 'neutral'


def _extract_keywords(
    text: str,
    complaint_keywords: list,
    emergency_keywords: list,
    spam_reasons: list,
    trend_tags: list,
) -> list[str]:
    """Return a compact, stable keyword list for storage and reporting."""
    keywords: list[str] = []
    seen = set()

    def add(value: str) -> None:
        value = value.strip().lower()
        if value and value not in seen:
            keywords.append(value)
            seen.add(value)

    for value in trend_tags + complaint_keywords + emergency_keywords:
        add(str(value))

    for reason in spam_reasons:
        for value in re.findall(r"'([^']+)'|([a-z][a-z\s_]{2,})", str(reason).lower()):
            add(next(part for part in value if part))

    stop_words = {
        'the', 'and', 'for', 'this', 'that', 'with', 'from', 'near', 'please',
        'have', 'has', 'are', 'was', 'were', 'our', 'your', 'there', 'very',
    }
    for token in re.findall(r'\b[a-zA-Z][a-zA-Z]{3,}\b', text.lower()):
        if token not in stop_words:
            add(token)
        if len(keywords) >= 10:
            break

    return keywords[:10]


def _detect_issue_type(trend_tags: list, keywords: list) -> str | None:
    """Detect Phase 7 civic issue types from trend tags and keywords."""
    issue_order = ('drainage', 'water', 'roads', 'electricity', 'garbage')
    aliases = {
        'road': 'roads',
        'pothole': 'roads',
        'streetlight': 'electricity',
        'power': 'electricity',
        'waste': 'garbage',
        'sanitation': 'garbage',
        'sewage': 'drainage',
        'drain': 'drainage',
        'waterlogging': 'drainage',
    }
    candidates = [str(value).lower() for value in trend_tags + keywords]
    for issue in issue_order:
        if issue in candidates:
            return issue
    for value in candidates:
        if value in aliases:
            return aliases[value]
    return None


def _summarize_comment(text: str, category: str, top_topic: str | None) -> str:
    """Build a short extractive summary suitable for dashboards."""
    cleaned = re.sub(r'\s+', ' ', text).strip()
    if len(cleaned) > 140:
        cleaned = cleaned[:137].rstrip() + '...'
    topic = top_topic or 'general'
    return f'{category.title()} comment about {topic}: {cleaned}'
