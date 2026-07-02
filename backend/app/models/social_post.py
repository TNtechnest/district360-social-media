"""SocialPost model — outbound content authored or scheduled by district staff."""
from sqlalchemy import String, Text, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.base import TenantScopedModel


class SocialPost(TenantScopedModel):
    """A piece of content to be published (or already published) on a social platform."""
    __tablename__ = 'social_post'

    # FK to the connected social account
    account_id: Mapped[str] = mapped_column(
        String(36), db.ForeignKey('social_account.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )

    # User who created the post draft
    author_id: Mapped[str] = mapped_column(
        String(36), db.ForeignKey('user.id', ondelete='SET NULL'),
        nullable=True,
    )

    # draft | scheduled | published | failed | cancelled
    status: Mapped[str] = mapped_column(String(20), default='draft', nullable=False, index=True)

    # Main text body
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Platform where this was / will be published
    platform: Mapped[str] = mapped_column(String(30), nullable=False, index=True)

    # ID returned by the platform after successful publish
    platform_post_id: Mapped[str] = mapped_column(String(255), nullable=True)

    # ISO timestamp when post was / will be published
    scheduled_at: Mapped[str] = mapped_column(String(50), nullable=True)
    published_at: Mapped[str] = mapped_column(String(50), nullable=True)

    # Engagement metrics snapshot (populated by collector)
    likes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    comments: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    shares: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    views: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Denormalised count of SocialComment rows (updated on comment sync)
    social_comment_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Platform-specific extra payload (hashtags, link, reel settings, etc.)
    meta: Mapped[dict] = mapped_column(db.JSON, default=dict, nullable=False)

    # AI analysis results cached here after processing
    ai_analysis: Mapped[dict] = mapped_column(db.JSON, default=dict, nullable=False)

    # Error message if publishing failed
    error_message: Mapped[str] = mapped_column(Text, nullable=True)

    account = relationship('SocialAccount', back_populates='posts')
    media_items = relationship(
        'MediaItem', back_populates='post', lazy='joined',
        cascade='all, delete-orphan',
    )
    social_comments = relationship(
        'SocialComment', back_populates='post', lazy='dynamic',
        cascade='all, delete-orphan',
    )

    def to_dict(self):
        return {
            'id': self.id,
            'district_id': self.district_id,
            'account_id': self.account_id,
            'author_id': self.author_id,
            'status': self.status,
            'content': self.content,
            'platform': self.platform,
            'platform_post_id': self.platform_post_id,
            'scheduled_at': self.scheduled_at,
            'published_at': self.published_at,
            'likes': self.likes,
            'comments': self.comments,
            'shares': self.shares,
            'views': self.views,
            'meta': self.meta,
            'ai_analysis': self.ai_analysis,
            'error_message': self.error_message,
            'media': [m.to_dict() for m in self.media_items],
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
