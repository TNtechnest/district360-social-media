"""Authentication extension models — OTP codes, sessions, device tracking."""

from sqlalchemy import String, Text, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.base import TenantScopedModel


class OtpCode(TenantScopedModel):
    """One-time password for email/SMS verification."""
    __tablename__ = 'otp_code'

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey('user.id', ondelete='CASCADE'), nullable=True, index=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=True, index=True)
    code: Mapped[str] = mapped_column(String(6), nullable=False)
    purpose: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[str] = mapped_column(String(50), nullable=False)
    attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    verified_at: Mapped[str] = mapped_column(String(50), nullable=True)
    sent_to: Mapped[str] = mapped_column(String(255), nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'email': self.email,
            'phone': self.phone,
            'purpose': self.purpose,
            'is_used': self.is_used,
            'expires_at': self.expires_at,
            'attempts': self.attempts,
            'verified_at': self.verified_at,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class UserSession(TenantScopedModel):
    """Active user session tracking."""
    __tablename__ = 'user_session'

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True,
    )
    token_jti: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    device_name: Mapped[str] = mapped_column(String(255), nullable=True)
    device_type: Mapped[str] = mapped_column(String(50), nullable=True)
    browser: Mapped[str] = mapped_column(String(255), nullable=True)
    os_info: Mapped[str] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=True)
    location: Mapped[str] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_activity_at: Mapped[str] = mapped_column(String(50), nullable=True)
    logged_out_at: Mapped[str] = mapped_column(String(50), nullable=True)

    user = relationship('User', foreign_keys=[user_id])

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'device_name': self.device_name,
            'device_type': self.device_type,
            'browser': self.browser,
            'os_info': self.os_info,
            'ip_address': self.ip_address,
            'location': self.location,
            'is_active': self.is_active,
            'last_activity_at': self.last_activity_at,
            'logged_out_at': self.logged_out_at,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class OAuthConnection(TenantScopedModel):
    """Links a user to an external OAuth provider."""
    __tablename__ = 'oauth_connection'

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True,
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_email: Mapped[str] = mapped_column(String(255), nullable=True)
    access_token: Mapped[str] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[str] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[str] = mapped_column(String(50), nullable=True)
    raw_profile: Mapped[dict] = mapped_column(db.JSON, default=dict, nullable=False)

    user = relationship('User', foreign_keys=[user_id])

    __table_args__ = (
        db.UniqueConstraint('user_id', 'provider', name='uix_oauth_user_provider'),
        db.UniqueConstraint('provider', 'provider_user_id', name='uix_oauth_provider_user'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'provider': self.provider,
            'provider_user_id': self.provider_user_id,
            'provider_email': self.provider_email,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
