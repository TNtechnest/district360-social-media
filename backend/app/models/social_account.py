"""SocialAccount model — stores OAuth credentials for each connected platform.

One district can connect multiple accounts per platform (e.g. two Facebook pages).
Tokens are stored encrypted-at-rest; decryption is handled by the social service layer.
"""
from sqlalchemy import String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.base import TenantScopedModel


class SocialAccount(TenantScopedModel):
    """A connected social media account belonging to a district tenant."""
    __tablename__ = 'social_account'

    # Platform identifier: facebook | instagram | youtube | x | telegram
    platform: Mapped[str] = mapped_column(String(30), nullable=False, index=True)

    # Human-readable label set by the admin (e.g. "Main Facebook Page")
    label: Mapped[str] = mapped_column(String(255), nullable=False)

    # Platform-specific account / page / channel ID
    platform_account_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # Display name as returned by the platform
    username: Mapped[str] = mapped_column(String(255), nullable=True)

    # OAuth / API credentials (stored as JSON; values should be encrypted in prod)
    credentials: Mapped[dict] = mapped_column(db.JSON, default=dict, nullable=False)

    # Webhook / bot token for platforms that push data (Telegram, Meta webhooks)
    webhook_secret: Mapped[str] = mapped_column(String(255), nullable=True)

    # Whether the account is actively syncing
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Platform-specific extra config (page_id, channel_id, language, etc.)
    config: Mapped[dict] = mapped_column(db.JSON, default=dict, nullable=False)

    posts = relationship(
        'SocialPost', back_populates='account', lazy='dynamic',
        cascade='all, delete-orphan',
    )
    collected_posts = relationship(
        'CollectedPost', back_populates='account', lazy='dynamic',
        cascade='all, delete-orphan',
    )

    __table_args__ = (
        db.UniqueConstraint(
            'district_id', 'platform', 'platform_account_id',
            name='uix_social_account_district_platform_id',
        ),
    )

    def to_dict(self, include_credentials: bool = False):
        d = {
            'id': self.id,
            'district_id': self.district_id,
            'platform': self.platform,
            'label': self.label,
            'platform_account_id': self.platform_account_id,
            'username': self.username,
            'is_active': self.is_active,
            'config': self.config,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_credentials:
            d['credentials'] = self.credentials
        return d
