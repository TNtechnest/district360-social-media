"""SocialComment model — comments on district-published social posts.

Captures comments received on the district's own SocialPost records
(both Facebook Page posts and Instagram Business media).

Design decisions:
  - Separate from CollectedPost: comments here are tied to a specific
    SocialPost we own, enabling threaded replies and direct moderation.
  - CollectedPost handles broad inbound monitoring (mentions, hashtags,
    public posts). SocialComment handles the engagement layer on our content.
  - Supports nesting: parent_comment_id → replies (one level deep mirrors
    Facebook/Instagram API structures).
"""
from sqlalchemy import String, Text, Integer, Boolean, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.base import TenantScopedModel


class SocialComment(TenantScopedModel):
    """A comment received on a district-published social media post."""
    __tablename__ = 'social_comment'

    # ── Foreign keys ─────────────────────────────────────────────────────────

    # The post this comment belongs to
    post_id: Mapped[str] = mapped_column(
        String(36),
        db.ForeignKey('social_post.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )

    # Parent comment (null = top-level; set = reply)
    parent_comment_id: Mapped[str] = mapped_column(
        String(36),
        db.ForeignKey('social_comment.id', ondelete='CASCADE'),
        nullable=True,
        index=True,
    )

    # ── Platform identity ─────────────────────────────────────────────────────

    # facebook | instagram
    platform: Mapped[str] = mapped_column(String(30), nullable=False, index=True)

    # Native comment ID from the platform (e.g. Facebook comment_id)
    platform_comment_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # Author information as returned by the platform
    author_platform_id: Mapped[str] = mapped_column(String(255), nullable=True)
    author_name: Mapped[str] = mapped_column(String(255), nullable=True)
    author_username: Mapped[str] = mapped_column(String(255), nullable=True)
    author_profile_url: Mapped[str] = mapped_column(Text, nullable=True)

    # ── Content ───────────────────────────────────────────────────────────────

    # Raw comment text
    text: Mapped[str] = mapped_column(Text, nullable=False)

    # ISO 8601 timestamp from the platform
    platform_created_at: Mapped[str] = mapped_column(String(50), nullable=True)

    # Engagement
    likes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reply_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # ── Moderation / state ────────────────────────────────────────────────────

    # visible | hidden | deleted | spam
    moderation_status: Mapped[str] = mapped_column(
        String(20), default='visible', nullable=False, index=True
    )

    # Has the district replied to this comment?
    is_replied: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Text of the district's reply (if sent via the platform)
    reply_text: Mapped[str] = mapped_column(Text, nullable=True)

    # Platform ID of the sent reply
    reply_platform_id: Mapped[str] = mapped_column(String(255), nullable=True)

    # ISO timestamp of reply
    replied_at: Mapped[str] = mapped_column(String(50), nullable=True)

    # Staff user who replied
    replied_by_id: Mapped[str] = mapped_column(
        String(36),
        db.ForeignKey('user.id', ondelete='SET NULL'),
        nullable=True,
    )

    # ── AI Analysis ──────────────────────────────────────────────────────────
    # Detected language: en | ta | tanglish | unknown
    language: Mapped[str] = mapped_column(String(20), default='unknown', nullable=False, index=True)

    # Populated after CommentAnalysis is run
    sentiment: Mapped[str] = mapped_column(String(20), nullable=True, index=True)
    sentiment_score: Mapped[float] = mapped_column(Float, nullable=True)
    is_complaint: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_emergency: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_spam: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    suggested_reply: Mapped[str] = mapped_column(Text, nullable=True)

    # pending | processed | failed
    ai_status: Mapped[str] = mapped_column(
        String(20), default='pending', nullable=False, index=True
    )

    # ── Relationships ─────────────────────────────────────────────────────────

    post = relationship('SocialPost', back_populates='social_comments')

    replies = relationship(
        'SocialComment',
        backref=db.backref('parent', remote_side='SocialComment.id'),
        lazy='dynamic',
        cascade='all, delete-orphan',
        foreign_keys='SocialComment.parent_comment_id',
    )

    analysis = relationship(
        'CommentAnalysis',
        back_populates='comment',
        uselist=False,
        cascade='all, delete-orphan',
    )

    # ── Constraints ───────────────────────────────────────────────────────────

    __table_args__ = (
        db.UniqueConstraint(
            'post_id', 'platform_comment_id',
            name='uix_social_comment_post_platform_comment',
        ),
    )

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self, include_analysis: bool = False) -> dict:
        d = {
            'id': self.id,
            'district_id': self.district_id,
            'post_id': self.post_id,
            'parent_comment_id': self.parent_comment_id,
            'platform': self.platform,
            'platform_comment_id': self.platform_comment_id,
            'author_platform_id': self.author_platform_id,
            'author_name': self.author_name,
            'author_username': self.author_username,
            'author_profile_url': self.author_profile_url,
            'text': self.text,
            'platform_created_at': self.platform_created_at,
            'likes': self.likes,
            'reply_count': self.reply_count,
            'moderation_status': self.moderation_status,
            'is_replied': self.is_replied,
            'reply_text': self.reply_text,
            'reply_platform_id': self.reply_platform_id,
            'replied_at': self.replied_at,
            'replied_by_id': self.replied_by_id,
            'language': self.language,
            'sentiment': self.sentiment,
            'sentiment_score': self.sentiment_score,
            'is_complaint': self.is_complaint,
            'is_emergency': self.is_emergency,
            'is_spam': self.is_spam,
            'suggested_reply': self.suggested_reply,
            'ai_status': self.ai_status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_analysis and self.analysis:
            d['analysis'] = self.analysis.to_dict()
        return d
