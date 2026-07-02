from sqlalchemy import String, Text, Table, Column, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.base import BaseModel


role_permissions = Table(
    'role_permissions',
    db.Model.metadata,
    Column('role_id', String(36), ForeignKey('role.id', ondelete='CASCADE'), primary_key=True),
    Column('permission_id', String(36), ForeignKey('permission.id', ondelete='CASCADE'), primary_key=True),
)


class Role(BaseModel):
    """A role assigned to users within a district."""
    __tablename__ = 'role'

    district_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey('district.id', ondelete='CASCADE'),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(default=False, nullable=False)

    users = relationship(
        "User",
        secondary="user_roles",
        back_populates="roles",
    )
    permissions = relationship(
        "Permission",
        secondary="role_permissions",
        back_populates="roles",
        lazy="joined",
    )

    __table_args__ = (
        db.UniqueConstraint('district_id', 'name', name='uix_role_district_name'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'district_id': self.district_id,
            'name': self.name,
            'description': self.description,
            'is_system': self.is_system,
            'permissions': [p.to_dict() for p in self.permissions],
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
