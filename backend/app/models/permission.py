"""Permission model for RBAC."""
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.base import BaseModel


class Permission(BaseModel):
    """A granular permission (resource + action)."""
    __tablename__ = 'permission'

    resource: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    roles = relationship(
        "Role",
        secondary="role_permissions",
        back_populates="permissions",
    )

    __table_args__ = (
        db.UniqueConstraint('resource', 'action', name='uix_permission_resource_action'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'resource': self.resource,
            'action': self.action,
            'description': self.description,
        }
