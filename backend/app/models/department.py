from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.base import TenantScopedModel


class Department(TenantScopedModel):
    """A department within a district."""
    __tablename__ = 'department'

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    wards: Mapped[list] = mapped_column(db.JSON, default=list, nullable=False)
    head_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey('user.id', ondelete='SET NULL'),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(20), default='active', nullable=False)

    district = relationship('District', back_populates='departments')
    head = relationship('User', foreign_keys=[head_id])

    __table_args__ = (
        db.UniqueConstraint('district_id', 'code', name='uix_department_district_code'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'district_id': self.district_id,
            'name': self.name,
            'code': self.code,
            'description': self.description,
            'wards': self.wards,
            'head_id': self.head_id,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
