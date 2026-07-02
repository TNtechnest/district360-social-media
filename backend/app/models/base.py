import uuid
from datetime import datetime, timezone

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class BaseModel(db.Model):
    """Abstract base model with UUID primary key and timestamps."""
    __abstract__ = True

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class TenantScopedModel(BaseModel):
    """Abstract model that adds district_id tenant scoping."""
    __abstract__ = True

    district_id: Mapped[str] = mapped_column(
        String(36),
        db.ForeignKey('district.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
