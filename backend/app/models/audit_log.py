from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.models.base import TenantScopedModel


class AuditLog(TenantScopedModel):
    """Immutable audit trail of significant actions."""
    __tablename__ = 'audit_log'

    actor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey('user.id', ondelete='SET NULL'),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(36), nullable=True)
    before_state: Mapped[dict] = mapped_column(db.JSON, nullable=True)
    after_state: Mapped[dict] = mapped_column(db.JSON, nullable=True)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str] = mapped_column(Text, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'district_id': self.district_id,
            'actor_id': self.actor_id,
            'action': self.action,
            'resource_type': self.resource_type,
            'resource_id': self.resource_id,
            'before_state': self.before_state,
            'after_state': self.after_state,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
