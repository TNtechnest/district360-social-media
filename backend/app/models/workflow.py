"""Workflow models — approval queues, escalation rules, SLA tracking."""
from sqlalchemy import String, Text, Integer, Boolean, Float
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.models.base import TenantScopedModel


class WorkflowRule(TenantScopedModel):
    """An approval / escalation / SLA rule for a resource type."""
    __tablename__ = 'workflow_rule'

    # What this rule governs: social_post | collected_post | campaign
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)

    # rule_type: approval | escalation | sla
    rule_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)

    # Conditions as JSON: [{"field": "platform", "op": "eq", "value": "facebook"}]
    conditions: Mapped[dict] = mapped_column(db.JSON, default=dict, nullable=False)

    # Actions as JSON: [{"action": "notify", "target_role": "district_admin"}]
    actions: Mapped[dict] = mapped_column(db.JSON, default=dict, nullable=False)

    # For SLA rules: minutes until breach
    sla_minutes: Mapped[int] = mapped_column(Integer, nullable=True)

    # For escalation: minutes after SLA breach before escalation fires
    escalation_after_minutes: Mapped[int] = mapped_column(Integer, nullable=True)

    priority: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'district_id': self.district_id,
            'resource_type': self.resource_type,
            'name': self.name,
            'description': self.description,
            'rule_type': self.rule_type,
            'conditions': self.conditions,
            'actions': self.actions,
            'sla_minutes': self.sla_minutes,
            'escalation_after_minutes': self.escalation_after_minutes,
            'priority': self.priority,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class ApprovalRequest(TenantScopedModel):
    """An item awaiting approval before publication/action."""
    __tablename__ = 'approval_request'

    # Who submitted for approval
    submitter_id: Mapped[str] = mapped_column(
        String(36), db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True,
    )
    # Assigned approver
    approver_id: Mapped[str] = mapped_column(
        String(36), db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True,
    )

    resource_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    resource_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # pending | approved | rejected | escalated | cancelled
    status: Mapped[str] = mapped_column(String(20), default='pending', nullable=False, index=True)

    notes: Mapped[str] = mapped_column(Text, nullable=True)
    approver_comment: Mapped[str] = mapped_column(Text, nullable=True)

    # ISO timestamps
    submitted_at: Mapped[str] = mapped_column(String(50), nullable=True)
    reviewed_at: Mapped[str] = mapped_column(String(50), nullable=True)
    sla_due_at: Mapped[str] = mapped_column(String(50), nullable=True, index=True)

    workflow_rule_id: Mapped[str] = mapped_column(
        String(36), db.ForeignKey('workflow_rule.id', ondelete='SET NULL'), nullable=True,
    )

    def to_dict(self):
        return {
            'id': self.id,
            'district_id': self.district_id,
            'submitter_id': self.submitter_id,
            'approver_id': self.approver_id,
            'resource_type': self.resource_type,
            'resource_id': self.resource_id,
            'status': self.status,
            'notes': self.notes,
            'approver_comment': self.approver_comment,
            'submitted_at': self.submitted_at,
            'reviewed_at': self.reviewed_at,
            'sla_due_at': self.sla_due_at,
            'workflow_rule_id': self.workflow_rule_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class EscalationLog(TenantScopedModel):
    """Records escalation events for SLA breaches."""
    __tablename__ = 'escalation_log'

    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    rule_id: Mapped[str] = mapped_column(
        String(36), db.ForeignKey('workflow_rule.id', ondelete='SET NULL'), nullable=True,
    )
    escalated_to_id: Mapped[str] = mapped_column(
        String(36), db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=True)
    escalated_at: Mapped[str] = mapped_column(String(50), nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'district_id': self.district_id,
            'resource_type': self.resource_type,
            'resource_id': self.resource_id,
            'rule_id': self.rule_id,
            'escalated_to_id': self.escalated_to_id,
            'reason': self.reason,
            'escalated_at': self.escalated_at,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
