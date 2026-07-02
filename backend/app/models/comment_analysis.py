"""CommentAnalysis model — full AI analysis record for a SocialComment.

One-to-one with SocialComment. Stores the complete AI pipeline output
so the comment row stays lean and the analysis blob is queryable separately.

Rationale for a separate table (vs. JSON column on SocialComment):
  - Can be re-processed independently without touching the comment record.
  - Supports reporting queries on analysis fields (index-friendly).
  - Keeps SocialComment focused on platform data; CommentAnalysis on
    AI-derived data.
"""
from sqlalchemy import String, Text, Float, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.base import TenantScopedModel


class CommentAnalysis(TenantScopedModel):
    """Full AI analysis record for one SocialComment."""
    __tablename__ = 'comment_analysis'

    # ── Foreign key ───────────────────────────────────────────────────────────

    comment_id: Mapped[str] = mapped_column(
        String(36),
        db.ForeignKey('social_comment.id', ondelete='CASCADE'),
        nullable=False,
        unique=True,      # one-to-one
        index=True,
    )

    # ── Language ─────────────────────────────────────────────────────────────

    # en | ta | tanglish | unknown
    language: Mapped[str] = mapped_column(String(20), default='unknown', nullable=False)

    # ── Sentiment ─────────────────────────────────────────────────────────────

    # positive | negative | neutral | mixed
    sentiment_label: Mapped[str] = mapped_column(String(20), nullable=True, index=True)
    sentiment_score: Mapped[float] = mapped_column(Float, nullable=True)

    # ── Complaint detection ───────────────────────────────────────────────────

    is_complaint: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    complaint_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    complaint_keywords: Mapped[list] = mapped_column(db.JSON, default=list, nullable=False)

    # ── Emergency detection ───────────────────────────────────────────────────

    is_emergency: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    emergency_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    emergency_keywords: Mapped[list] = mapped_column(db.JSON, default=list, nullable=False)

    # ── Spam detection ────────────────────────────────────────────────────────

    is_spam: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    spam_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    spam_reasons: Mapped[list] = mapped_column(db.JSON, default=list, nullable=False)

    # ── Topic / trend detection ───────────────────────────────────────────────

    # Phase 6 category: positive | negative | neutral | complaint | question | spam
    category: Mapped[str] = mapped_column(String(30), default='neutral', nullable=False, index=True)
    issue_type: Mapped[str] = mapped_column(String(30), nullable=True, index=True)

    # Dashboard-friendly keyword and summary outputs
    keywords: Mapped[list] = mapped_column(db.JSON, default=list, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=True)

    # Phase 7 service request automation link
    service_request_id: Mapped[str] = mapped_column(
        String(36),
        db.ForeignKey('service_request.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )

    trend_tags: Mapped[list] = mapped_column(db.JSON, default=list, nullable=False)
    top_topic: Mapped[str] = mapped_column(String(100), nullable=True)

    # ── Reply suggestion ─────────────────────────────────────────────────────

    suggested_reply: Mapped[str] = mapped_column(Text, nullable=True)
    # complaint | emergency | appreciation | general
    reply_category: Mapped[str] = mapped_column(String(30), nullable=True)

    # ── Processing metadata ───────────────────────────────────────────────────

    # pending | processed | failed
    status: Mapped[str] = mapped_column(String(20), default='pending', nullable=False, index=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)

    # Full raw result from the AI engine (complete pipeline output)
    raw_result: Mapped[dict] = mapped_column(db.JSON, default=dict, nullable=False)

    # Processing time in milliseconds
    processing_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # ── Relationship ─────────────────────────────────────────────────────────

    comment = relationship('SocialComment', back_populates='analysis')
    service_request = relationship('ServiceRequest', foreign_keys=[service_request_id])

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'district_id': self.district_id,
            'comment_id': self.comment_id,
            'language': self.language,
            'sentiment': {
                'label': self.sentiment_label,
                'score': self.sentiment_score,
            },
            'complaint': {
                'detected': self.is_complaint,
                'confidence': self.complaint_confidence,
                'keywords': self.complaint_keywords,
            },
            'emergency': {
                'detected': self.is_emergency,
                'confidence': self.emergency_confidence,
                'keywords': self.emergency_keywords,
            },
            'spam': {
                'detected': self.is_spam,
                'confidence': self.spam_confidence,
                'reasons': self.spam_reasons,
            },
            'category': self.category,
            'issue_type': self.issue_type,
            'keywords': self.keywords,
            'summary': self.summary,
            'service_request_id': self.service_request_id,
            'trends': {
                'tags': self.trend_tags,
                'top_topic': self.top_topic,
            },
            'reply': {
                'suggested': self.suggested_reply,
                'category': self.reply_category,
            },
            'status': self.status,
            'error_message': self.error_message,
            'processing_ms': self.processing_ms,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
