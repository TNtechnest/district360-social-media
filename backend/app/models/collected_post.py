"""CollectedPost model — inbound social media content gathered by the AI Collector.

The collector harvests public posts, comments, and mentions from connected
platforms and stores them here for AI analysis (sentiment, complaints,
emergencies, trends, spam).
"""
from sqlalchemy import String, Text, Integer, Boolean, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.base import TenantScopedModel


class CollectedPost(TenantScopedModel):
    """A post/comment/mention collected from a social platform."""
    __tablename__ = 'collected_post'

    # Connected account this was collected through
    account_id: Mapped[str] = mapped_column(
        String(36), db.ForeignKey('social_account.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )

    # Platform of origin: facebook | instagram | youtube | x | telegram
    platform: Mapped[str] = mapped_column(String(30), nullable=False, index=True)

    # post | comment | mention | dm | story_reply | reel_comment
    content_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)

    # Platform-native ID of the original content
    platform_content_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # Author details
    author_platform_id: Mapped[str] = mapped_column(String(255), nullable=True)
    author_username: Mapped[str] = mapped_column(String(255), nullable=True)

    # Raw text of the collected content
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Detected / declared language: en | ta | tanglish | unknown
    language: Mapped[str] = mapped_column(String(20), default='unknown', nullable=False, index=True)

    # When the content was originally posted on the platform
    platform_created_at: Mapped[str] = mapped_column(String(50), nullable=True)

    # Engagement counts at time of collection
    likes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    comments: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    shares: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # ------------------------------------------------------------------ AI labels
    # Sentiment: positive | negative | neutral | mixed
    sentiment: Mapped[str] = mapped_column(String(20), nullable=True, index=True)
    sentiment_score: Mapped[float] = mapped_column(Float, nullable=True)

    # Boolean AI flags
    is_complaint: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_emergency: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_spam: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    # Trend / topic tags extracted by AI
    trend_tags: Mapped[list] = mapped_column(db.JSON, default=list, nullable=False)

    # AI-suggested reply text
    suggested_reply: Mapped[str] = mapped_column(Text, nullable=True)

    # Full AI analysis result blob
    ai_result: Mapped[dict] = mapped_column(db.JSON, default=dict, nullable=False)

    # Processing state: pending | processed | failed
    ai_status: Mapped[str] = mapped_column(String(20), default='pending', nullable=False, index=True)

    # Human review state: unreviewed | reviewed | actioned | ignored
    review_status: Mapped[str] = mapped_column(String(20), default='unreviewed', nullable=False, index=True)

    account = relationship('SocialAccount', back_populates='collected_posts')

    __table_args__ = (
        db.UniqueConstraint(
            'account_id', 'platform_content_id',
            name='uix_collected_post_account_content',
        ),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'district_id': self.district_id,
            'account_id': self.account_id,
            'platform': self.platform,
            'content_type': self.content_type,
            'platform_content_id': self.platform_content_id,
            'author_platform_id': self.author_platform_id,
            'author_username': self.author_username,
            'raw_text': self.raw_text,
            'language': self.language,
            'platform_created_at': self.platform_created_at,
            'likes': self.likes,
            'comments': self.comments,
            'shares': self.shares,
            'sentiment': self.sentiment,
            'sentiment_score': self.sentiment_score,
            'is_complaint': self.is_complaint,
            'is_emergency': self.is_emergency,
            'is_spam': self.is_spam,
            'trend_tags': self.trend_tags,
            'suggested_reply': self.suggested_reply,
            'ai_result': self.ai_result,
            'ai_status': self.ai_status,
            'review_status': self.review_status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
