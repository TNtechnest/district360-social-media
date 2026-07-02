"""Report model — stores generated report metadata and export links."""
from sqlalchemy import String, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.models.base import TenantScopedModel


class Report(TenantScopedModel):
    """A generated analytics report."""
    __tablename__ = 'report'

    # daily | weekly | monthly | executive | custom
    report_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)

    # Label shown in UI
    title: Mapped[str] = mapped_column(String(255), nullable=False)

    # ISO date range
    period_start: Mapped[str] = mapped_column(String(30), nullable=False)
    period_end: Mapped[str] = mapped_column(String(30), nullable=False)

    # pending | ready | failed
    status: Mapped[str] = mapped_column(String(20), default='pending', nullable=False, index=True)

    # JSON snapshot of the report data (used for in-app display)
    data: Mapped[dict] = mapped_column(db.JSON, default=dict, nullable=False)

    # Object storage URLs for exports (populated after generation)
    pdf_url: Mapped[str] = mapped_column(Text, nullable=True)
    excel_url: Mapped[str] = mapped_column(Text, nullable=True)

    generated_by: Mapped[str] = mapped_column(
        String(36), db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True,
    )
    generated_at: Mapped[str] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'district_id': self.district_id,
            'report_type': self.report_type,
            'title': self.title,
            'period_start': self.period_start,
            'period_end': self.period_end,
            'status': self.status,
            'data': self.data,
            'pdf_url': self.pdf_url,
            'excel_url': self.excel_url,
            'generated_by': self.generated_by,
            'generated_at': self.generated_at,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
