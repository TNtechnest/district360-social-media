"""Escalation Engine — detects SLA breaches and fires escalation actions.

Called by a periodic task (Celery beat / APScheduler) every 5–15 minutes.
Can also be triggered on-demand via the API.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone

from app.extensions import db
from app.models.workflow import ApprovalRequest, WorkflowRule, EscalationLog
from app.utils.db import paginate_query

logger = logging.getLogger(__name__)


def check_sla_breaches() -> int:
    """Scan open approval requests for SLA breaches and escalate them.

    Returns:
        Number of escalations triggered.
    """
    now = datetime.now(timezone.utc).isoformat()
    breached = (
        ApprovalRequest.query
        .filter(
            ApprovalRequest.status == 'pending',
            ApprovalRequest.sla_due_at <= now,
        )
        .all()
    )

    count = 0
    for req in breached:
        try:
            _escalate_request(req)
            count += 1
        except Exception:
            logger.exception('Escalation failed for approval request %s', req.id)

    if count:
        db.session.commit()
        logger.info('Escalated %d SLA-breached approval requests.', count)
    return count


def _escalate_request(req: ApprovalRequest) -> None:
    """Mark an approval request as escalated and log the escalation."""
    req.status = 'escalated'

    log = EscalationLog(
        district_id=req.district_id,
        resource_type=req.resource_type,
        resource_id=req.resource_id,
        rule_id=req.workflow_rule_id,
        escalated_to_id=None,   # Populate from WorkflowRule.actions if configured
        reason=f'SLA breach: due at {req.sla_due_at}',
        escalated_at=datetime.now(timezone.utc).isoformat(),
    )
    db.session.add(log)

    # Attempt to resolve escalation target from the workflow rule
    if req.workflow_rule_id:
        rule = WorkflowRule.query.get(req.workflow_rule_id)
        if rule:
            actions = rule.actions if isinstance(rule.actions, list) else []
            for action in actions:
                if action.get('action') == 'escalate_to_role':
                    # In production: look up users with this role and notify them
                    logger.info(
                        'Escalating %s/%s to role: %s',
                        req.resource_type, req.resource_id, action.get('target_role'),
                    )

    logger.warning(
        'Escalated: %s/%s (was due: %s)',
        req.resource_type, req.resource_id, req.sla_due_at,
    )


def get_escalation_logs(
    district_id: str,
    page: int = 1,
    per_page: int = 20,
    resource_type: str | None = None,
) -> object:
    query = EscalationLog.query.filter_by(district_id=district_id)
    if resource_type:
        query = query.filter(EscalationLog.resource_type == resource_type)
    return paginate_query(query.order_by(EscalationLog.created_at.desc()), page, per_page)


# ---------------------------------------------------------------------------
# Workflow Rule CRUD
# ---------------------------------------------------------------------------

def get_workflow_rules(district_id: str, page: int = 1, per_page: int = 20) -> object:
    return paginate_query(
        WorkflowRule.query.filter_by(district_id=district_id)
        .order_by(WorkflowRule.priority.asc()),
        page, per_page,
    )


def create_workflow_rule(
    district_id: str,
    resource_type: str,
    name: str,
    rule_type: str,
    conditions: dict,
    actions: dict,
    sla_minutes: int | None = None,
    escalation_after_minutes: int | None = None,
    priority: int = 10,
) -> WorkflowRule:
    valid_types = {'approval', 'escalation', 'sla'}
    if rule_type not in valid_types:
        raise ValueError(f"rule_type must be one of: {', '.join(valid_types)}")

    rule = WorkflowRule(
        district_id=district_id,
        resource_type=resource_type,
        name=name,
        rule_type=rule_type,
        conditions=conditions,
        actions=actions,
        sla_minutes=sla_minutes,
        escalation_after_minutes=escalation_after_minutes,
        priority=priority,
        is_active=True,
    )
    db.session.add(rule)
    db.session.commit()
    return rule


def get_sla_summary(district_id: str) -> dict:
    """Return SLA compliance summary for open approval requests."""
    now = datetime.now(timezone.utc).isoformat()
    total   = ApprovalRequest.query.filter_by(district_id=district_id, status='pending').count()
    breached = ApprovalRequest.query.filter(
        ApprovalRequest.district_id == district_id,
        ApprovalRequest.status == 'pending',
        ApprovalRequest.sla_due_at <= now,
    ).count()
    resolved = ApprovalRequest.query.filter(
        ApprovalRequest.district_id == district_id,
        ApprovalRequest.status.in_(['approved', 'rejected']),
    ).count()
    escalated = ApprovalRequest.query.filter_by(district_id=district_id, status='escalated').count()

    compliance_pct = round((resolved / (resolved + escalated) * 100), 2) if (resolved + escalated) else 100.0

    return {
        'open_requests': total,
        'sla_breached': breached,
        'resolved': resolved,
        'escalated': escalated,
        'compliance_pct': compliance_pct,
    }
