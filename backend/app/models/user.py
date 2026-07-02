from sqlalchemy import String, Table, Column, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.base import TenantScopedModel


user_roles = Table(
    'user_roles',
    db.Model.metadata,
    Column('user_id', String(36), ForeignKey('user.id', ondelete='CASCADE'), primary_key=True),
    Column('role_id', String(36), ForeignKey('role.id', ondelete='CASCADE'), primary_key=True),
)


class User(TenantScopedModel):
    """A user account scoped to a district."""
    __tablename__ = 'user'

    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=True)
    auth_provider: Mapped[str] = mapped_column(String(50), default='local', nullable=False)
    status: Mapped[str] = mapped_column(String(20), default='active', nullable=False)
    email_verified: Mapped[bool] = mapped_column(default=False, nullable=False)
    phone_verified: Mapped[bool] = mapped_column(default=False, nullable=False)
    last_login_at: Mapped[str] = mapped_column(String(50), nullable=True)

    district = relationship('District', back_populates='users')
    roles = relationship(
        "Role",
        secondary="user_roles",
        back_populates="users",
        lazy='joined',
    )

    __table_args__ = (
        db.UniqueConstraint('district_id', 'email', name='uix_user_district_email'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'district_id': self.district_id,
            'email': self.email,
            'phone': self.phone,
            'full_name': self.full_name,
            'auth_provider': self.auth_provider,
            'status': self.status,
            'email_verified': self.email_verified,
            'phone_verified': self.phone_verified,
            'last_login_at': self.last_login_at,
            'roles': [r.name for r in self.roles],
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
