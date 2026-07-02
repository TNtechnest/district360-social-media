from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.models.base import TenantScopedModel


class ActivityLog(TenantScopedModel):
    """High-volume user activity log for analytics and debugging."""
    __tablename__ = 'activity_log'

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey('user.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    activity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict] = mapped_column('metadata', db.JSON, default=dict, nullable=False)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str] = mapped_column(Text, nullable=True)

    def __init__(self, **kwargs):
        metadata = kwargs.pop('metadata', None)
        super().__init__(**kwargs)
        if metadata is not None:
            self.metadata_ = metadata

    def __getattribute__(self, name):
        if name == 'metadata':
            return object.__getattribute__(self, 'metadata_')
        return super().__getattribute__(name)

    def __setattr__(self, name, value):
        if name == 'metadata':
            name = 'metadata_'
            value = value or {}
        super().__setattr__(name, value)

    def to_dict(self):
        return {
            'id': self.id,
            'district_id': self.district_id,
            'user_id': self.user_id,
            'activity_type': self.activity_type,
            'description': self.description,
            'metadata': self.metadata_,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
