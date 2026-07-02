"""Service Request models — citizen-facing issue tracking with department routing."""

from sqlalchemy import String, Text, Integer, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.base import TenantScopedModel


REQUEST_STATUSES = (
    'submitted', 'acknowledged', 'in_progress', 'escalated',
    'resolved', 'closed', 'rejected',
)

REQUEST_PRIORITIES = ('low', 'medium', 'high', 'urgent', 'emergency')


class ServiceRequestCategory(TenantScopedModel):
    """Categorisation tree for service requests."""
    __tablename__ = 'service_request_category'

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    parent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey('service_request_category.id', ondelete='SET NULL'),
        nullable=True,
    )
    department_id: Mapped[str] = mapped_column(
        String(36), ForeignKey('department.id', ondelete='SET NULL'),
        nullable=True,
    )
    default_priority: Mapped[str] = mapped_column(String(20), default='medium', nullable=False)
    sla_hours: Mapped[int] = mapped_column(Integer, default=48, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    parent = relationship('ServiceRequestCategory', remote_side='ServiceRequestCategory.id', back_populates='children')
    children = relationship('ServiceRequestCategory', back_populates='parent', lazy='dynamic')
    department = relationship('Department', foreign_keys=[department_id])

    __table_args__ = (
        db.UniqueConstraint('district_id', 'code', name='uix_sr_category_district_code'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'district_id': self.district_id,
            'name': self.name,
            'code': self.code,
            'description': self.description,
            'parent_id': self.parent_id,
            'department_id': self.department_id,
            'default_priority': self.default_priority,
            'sla_hours': self.sla_hours,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class ServiceRequest(TenantScopedModel):
    """A citizen-submitted service request / grievance."""
    __tablename__ = 'service_request'

    category_id: Mapped[str] = mapped_column(
        String(36), ForeignKey('service_request_category.id', ondelete='SET NULL'),
        nullable=True, index=True,
    )
    department_id: Mapped[str] = mapped_column(
        String(36), ForeignKey('department.id', ondelete='SET NULL'),
        nullable=True, index=True,
    )

    citizen_id: Mapped[str] = mapped_column(
        String(36), ForeignKey('user.id', ondelete='SET NULL'),
        nullable=True, index=True,
    )
    assigned_to: Mapped[str] = mapped_column(
        String(36), ForeignKey('user.id', ondelete='SET NULL'),
        nullable=True, index=True,
    )

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default='submitted', nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(20), default='medium', nullable=False, index=True)

    location: Mapped[str] = mapped_column(Text, nullable=True)
    ward: Mapped[str] = mapped_column(String(100), nullable=True)
    landmark: Mapped[str] = mapped_column(String(255), nullable=True)

    citizen_phone: Mapped[str] = mapped_column(String(20), nullable=True)
    citizen_email: Mapped[str] = mapped_column(String(255), nullable=True)

    # Timestamps as ISO strings for flexibility
    acknowledged_at: Mapped[str] = mapped_column(String(50), nullable=True)
    resolved_at: Mapped[str] = mapped_column(String(50), nullable=True)
    closed_at: Mapped[str] = mapped_column(String(50), nullable=True)
    sla_deadline: Mapped[str] = mapped_column(String(50), nullable=True)

    resolution_notes: Mapped[str] = mapped_column(Text, nullable=True)
    citizen_feedback: Mapped[str] = mapped_column(Text, nullable=True)
    satisfaction_score: Mapped[int] = mapped_column(Integer, nullable=True)

    is_escalated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    escalation_reason: Mapped[str] = mapped_column(Text, nullable=True)
    tags: Mapped[list] = mapped_column(db.JSON, default=list, nullable=False)

    category = relationship('ServiceRequestCategory', foreign_keys=[category_id])
    department = relationship('Department', foreign_keys=[department_id])
    citizen = relationship('User', foreign_keys=[citizen_id])
    assignee = relationship('User', foreign_keys=[assigned_to])

    def to_dict(self):
        return {
            'id': self.id,
            'district_id': self.district_id,
            'category_id': self.category_id,
            'department_id': self.department_id,
            'citizen_id': self.citizen_id,
            'assigned_to': self.assigned_to,
            'title': self.title,
            'description': self.description,
            'status': self.status,
            'priority': self.priority,
            'location': self.location,
            'ward': self.ward,
            'landmark': self.landmark,
            'citizen_phone': self.citizen_phone,
            'citizen_email': self.citizen_email,
            'acknowledged_at': self.acknowledged_at,
            'resolved_at': self.resolved_at,
            'closed_at': self.closed_at,
            'sla_deadline': self.sla_deadline,
            'resolution_notes': self.resolution_notes,
            'citizen_feedback': self.citizen_feedback,
            'satisfaction_score': self.satisfaction_score,
            'is_escalated': self.is_escalated,
            'escalation_reason': self.escalation_reason,
            'tags': self.tags,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class ServiceRequestComment(TenantScopedModel):
    """Audit trail of comments / status changes on a service request."""
    __tablename__ = 'service_request_comment'

    request_id: Mapped[str] = mapped_column(
        String(36), ForeignKey('service_request.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )
    author_id: Mapped[str] = mapped_column(
        String(36), ForeignKey('user.id', ondelete='SET NULL'),
        nullable=True,
    )
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    old_status: Mapped[str] = mapped_column(String(20), nullable=True)
    new_status: Mapped[str] = mapped_column(String(20), nullable=True)

    author = relationship('User', foreign_keys=[author_id])

    def to_dict(self):
        return {
            'id': self.id,
            'district_id': self.district_id,
            'request_id': self.request_id,
            'author_id': self.author_id,
            'comment': self.comment,
            'is_internal': self.is_internal,
            'old_status': self.old_status,
            'new_status': self.new_status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
