"""MetaOAuthState — short-lived CSRF state for Meta OAuth flow.

Stores the ``state`` parameter generated at /oauth/login so the callback
can validate it, preventing CSRF attacks.  Records also capture which
district and user initiated the flow so the callback can attribute the
connected account correctly.

Rows are single-use and expire after 10 minutes.
"""
from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.models.base import TenantScopedModel


class MetaOAuthState(TenantScopedModel):
    """CSRF state token for a pending Meta OAuth flow."""
    __tablename__ = 'meta_oauth_state'

    # The random ``state`` value sent to Meta and verified on callback
    state: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True, index=True
    )

    # User who initiated the flow
    initiated_by: Mapped[str] = mapped_column(
        String(36),
        db.ForeignKey('user.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )

    # Which platforms are being connected: facebook | instagram | both
    platform_scope: Mapped[str] = mapped_column(String(30), nullable=False)

    # ISO expiry timestamp
    expires_at: Mapped[str] = mapped_column(String(50), nullable=False)

    # Has this state been consumed?
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Optional label the admin gave the connection
    connection_label: Mapped[str] = mapped_column(String(255), nullable=True)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'district_id': self.district_id,
            'initiated_by': self.initiated_by,
            'platform_scope': self.platform_scope,
            'expires_at': self.expires_at,
            'is_used': self.is_used,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
