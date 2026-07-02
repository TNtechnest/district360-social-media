"""Approval Engine — manage approval requests for content before publishing.

When a social post is drafted by an officer, an approval request is
created.  A district admin reviews it and approves or rejects.
On approval the post is auto-published.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone, timedelta

from app.extensions import db
from app.models.workflow import ApprovalRequest, WorkflowRule
from app.services.audit_service import write_audit_log
from app.utils.db import paginate_query

logger = logging.getLogger(__name__)


def create_approval_request(
    district_id: str,
    resource_type: str,
    resource_id: str,
    submitter_id: str,
    approver_id: str | None = None,
    notes: str | None = None,
    sla_minutes: int = 60,
    workflow_rule_id: str | None = None,
) -> ApprovalRequest:
    """Create a new approval request.

    Args:
        district_id:      Tenant scope.
        resource_type:    e.g. ``'social_post'``.
        resource_id:      UUID of the resource awaiting approval.
        submitter_id:     User who submitted the content.
        approver_id:      Designated approver (optional — can be assigned later).
        notes:            Submitter notes.
        sla_minutes:      Minutes until SLA breach.
        workflow_rule_id: Linked workflow rule.

    Returns:
        Persisted :class:`ApprovalRequest`.
    """
    now = datetime.now(timezone.utc)
    sla_due = now + timedelta(minutes=sla_minutes)

    existing = ApprovalRequest.query.filter_by(
        district_id=district_id,
        resource_type=resource_type,
        resource_id=resource_id,
        status='pending',
    ).first()
    if existing:
        raise ValueError('An open approval request already exists for this resource.')

    req = ApprovalRequest(
        district_id=district_id,
        resource_type=resource_type,
        resource_id=resource_id,
        submitter_id=submitter_id,
        approver_id=approver_id,
        notes=notes,
        status='pending',
        submitted_at=now.isoformat(),
        sla_due_at=sla_due.isoformat(),
        workflow_rule_id=workflow_rule_id,
    )
    db.session.add(req)
    db.session.flush()

    write_audit_log(
        district_id=district_id, actor_id=submitter_id,
        action='approval_request.created',
        resource_type='approval_request', resource_id=req.id,
        after_state=req.to_dict(),
    )
    db.session.commit()
    logger.info('Approval request created: %s for %s/%s', req.id, resource_type, resource_id)
    return req


def review_approval(
    district_id: str,
    request_id: str,
    reviewer_id: str,
    decision: str,          # 'approved' | 'rejected'
    comment: str | None = None,
) -> ApprovalRequest:
    """Approve or reject a pending approval request.

    On approval of a ``social_post`` resource, the post is auto-published.

    Args:
        district_id: Tenant scope.
        request_id:  UUID of the ApprovalRequest.
        reviewer_id: User performing the review.
        decision:    ``'approved'`` or ``'rejected'``.
        comment:     Reviewer comment.

    Returns:
        Updated :class:`ApprovalRequest`.

    Raises:
        ValueError: If request not found or already reviewed.
    """
    if decision not in ('approved', 'rejected'):
        raise ValueError("decision must be 'approved' or 'rejected'.")

    req = ApprovalRequest.query.filter_by(id=request_id, district_id=district_id).first()
    if not req:
        raise ValueError('Approval request not found.')
    if req.status != 'pending':
        raise ValueError(f"Cannot review a request with status '{req.status}'.")

    req.status           = decision
    req.approver_id      = reviewer_id
    req.approver_comment = comment
    req.reviewed_at      = datetime.now(timezone.utc).isoformat()

    # Auto-publish the social post on approval
    if decision == 'approved' and req.resource_type == 'social_post':
        try:
            from app.services.social.content_service import publish_now
            publish_now(district_id, req.resource_id, actor_id=reviewer_id)
        except Exception:
            logger.exception('Auto-publish failed after approval for post %s', req.resource_id)

    write_audit_log(
        district_id=district_id, actor_id=reviewer_id,
        action=f'approval_request.{decision}',
        resource_type='approval_request', resource_id=request_id,
        before_state={'status': 'pending'},
        after_state=req.to_dict(),
    )
    db.session.commit()
    return req


def get_approval_requests(
    district_id: str,
    page: int = 1,
    per_page: int = 20,
    status: str | None = None,
    resource_type: str | None = None,
    approver_id: str | None = None,
) -> object:
    query = ApprovalRequest.query.filter_by(district_id=district_id)
    if status:
        query = query.filter(ApprovalRequest.status == status)
    if resource_type:
        query = query.filter(ApprovalRequest.resource_type == resource_type)
    if approver_id:
        query = query.filter(ApprovalRequest.approver_id == approver_id)
    return paginate_query(query.order_by(ApprovalRequest.created_at.desc()), page, per_page)


def get_approval_request(district_id: str, request_id: str) -> ApprovalRequest:
    req = ApprovalRequest.query.filter_by(id=request_id, district_id=district_id).first()
    if not req:
        raise ValueError('Approval request not found.')
    return req
