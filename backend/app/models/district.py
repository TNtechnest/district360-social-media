from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.models.base import BaseModel


class District(BaseModel):
    """A tenant representing a district."""
    __tablename__ = 'district'

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    region: Mapped[str] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default='active', nullable=False)
    config: Mapped[dict] = mapped_column(db.JSON, default=dict, nullable=False)

    users = db.relationship('User', back_populates='district', lazy='dynamic',
                            cascade='all, delete-orphan')
    departments = db.relationship('Department', back_populates='district', lazy='dynamic',
                                  cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'slug': self.slug,
            'region': self.region,
            'status': self.status,
            'config': self.config,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
