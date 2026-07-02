"""Workflow, Approval, Escalation, and SLA API endpoints.

Routes
------
# Approval
GET  /api/v1/workflow/approvals               — list approval requests
POST /api/v1/workflow/approvals               — create approval request
GET  /api/v1/workflow/approvals/<id>          — get single request
POST /api/v1/workflow/approvals/<id>/review   — approve or reject

# Workflow Rules
GET  /api/v1/workflow/rules                   — list workflow rules
POST /api/v1/workflow/rules                   — create rule

# Escalation
POST /api/v1/workflow/escalations/check       — run SLA breach scan
GET  /api/v1/workflow/escalations             — list escalation logs
GET  /api/v1/workflow/sla/summary             — SLA compliance summary
"""
import logging

from flask import Blueprint, request, g
from flask_jwt_extended import get_jwt

from app.services.workflow.approval_service import (
    create_approval_request, review_approval,
    get_approval_requests, get_approval_request,
)
from app.services.workflow.escalation_service import (
    check_sla_breaches, get_escalation_logs,
    get_workflow_rules, create_workflow_rule, get_sla_summary,
)
from app.services.rbac_service import require_permission
from app.utils.responses import success_response, error_response, paginated_response
from app.utils.validators import validate_pagination_params

logger = logging.getLogger(__name__)
workflow_bp = Blueprint('workflow', __name__, url_prefix='/workflow')


def _district():
    return get_jwt().get('district_id', '')


# ---------------------------------------------------------------------------
# Approval Requests
# ---------------------------------------------------------------------------

@workflow_bp.route('/approvals', methods=['GET'])
@require_permission('approval', 'read')
def list_approvals():
    """List approval requests with optional filters.

    Query params: ``page``, ``per_page``, ``status``, ``resource_type``.
    """
    page, per_page = validate_pagination_params(
        request.args.get('page', 1), request.args.get('per_page', 20)
    )
    pagination = get_approval_requests(
        _district(),
        page=page, per_page=per_page,
        status=request.args.get('status'),
        resource_type=request.args.get('resource_type'),
        approver_id=request.args.get('approver_id'),
    )
    return paginated_response([r.to_dict() for r in pagination.items], pagination)


@workflow_bp.route('/approvals', methods=['POST'])
@require_permission('approval', 'create')
def create_approval():
    """Submit a resource for approval.

    Request body (JSON)::

        {
          "resource_type": "social_post",
          "resource_id": "<uuid>",
          "notes": "Please review before publishing.",
          "sla_minutes": 120,
          "approver_id": "<user_uuid>"
        }
    """
    data = request.get_json(silent=True) or {}
    for field in ('resource_type', 'resource_id'):
        if not data.get(field):
            return error_response(f"'{field}' is required.", 400, 'VALIDATION_ERROR')
    try:
        req = create_approval_request(
            district_id=_district(),
            resource_type=data['resource_type'],
            resource_id=data['resource_id'],
            submitter_id=g.current_user.id,
            approver_id=data.get('approver_id'),
            notes=data.get('notes'),
            sla_minutes=int(data.get('sla_minutes', 60)),
        )
        return success_response(data=req.to_dict(), status_code=201, message='Approval request submitted.')
    except ValueError as exc:
        return error_response(str(exc), 400, 'VALIDATION_ERROR')


@workflow_bp.route('/approvals/<request_id>', methods=['GET'])
@require_permission('approval', 'read')
def get_approval(request_id):
    """Get a single approval request by ID."""
    try:
        req = get_approval_request(_district(), request_id)
        return success_response(data=req.to_dict())
    except ValueError as exc:
        return error_response(str(exc), 404, 'NOT_FOUND')


@workflow_bp.route('/approvals/<request_id>/review', methods=['POST'])
@require_permission('approval', 'update')
def review_approval_request(request_id):
    """Approve or reject a pending approval request.

    Request body (JSON)::

        {
          "decision": "approved",
          "comment": "Looks good. Approved for publishing."
        }
    """
    data = request.get_json(silent=True) or {}
    decision = data.get('decision', '').strip()
    if not decision:
        return error_response('decision is required (approved or rejected).', 400, 'VALIDATION_ERROR')
    try:
        req = review_approval(
            district_id=_district(),
            request_id=request_id,
            reviewer_id=g.current_user.id,
            decision=decision,
            comment=data.get('comment'),
        )
        return success_response(data=req.to_dict(), message=f'Request {decision}.')
    except ValueError as exc:
        return error_response(str(exc), 400, 'VALIDATION_ERROR')


# ---------------------------------------------------------------------------
# Workflow Rules
# ---------------------------------------------------------------------------

@workflow_bp.route('/rules', methods=['GET'])
@require_permission('workflow_rule', 'read')
def list_rules():
    """List workflow rules for the district."""
    page, per_page = validate_pagination_params(
        request.args.get('page', 1), request.args.get('per_page', 20)
    )
    pagination = get_workflow_rules(_district(), page=page, per_page=per_page)
    return paginated_response([r.to_dict() for r in pagination.items], pagination)


@workflow_bp.route('/rules', methods=['POST'])
@require_permission('workflow_rule', 'create')
def create_rule():
    """Create a new workflow rule.

    Request body (JSON)::

        {
          "resource_type": "social_post",
          "name": "Require approval for Facebook posts",
          "rule_type": "approval",
          "conditions": {"platform": "facebook"},
          "actions": [{"action": "require_approval", "target_role": "district_admin"}],
          "sla_minutes": 60
        }
    """
    data = request.get_json(silent=True) or {}
    for field in ('resource_type', 'name', 'rule_type', 'conditions', 'actions'):
        if field not in data:
            return error_response(f"'{field}' is required.", 400, 'VALIDATION_ERROR')
    try:
        rule = create_workflow_rule(
            district_id=_district(),
            resource_type=data['resource_type'],
            name=data['name'],
            rule_type=data['rule_type'],
            conditions=data['conditions'],
            actions=data['actions'],
            sla_minutes=data.get('sla_minutes'),
            escalation_after_minutes=data.get('escalation_after_minutes'),
            priority=int(data.get('priority', 10)),
        )
        return success_response(data=rule.to_dict(), status_code=201, message='Workflow rule created.')
    except ValueError as exc:
        return error_response(str(exc), 400, 'VALIDATION_ERROR')


# ---------------------------------------------------------------------------
# Escalation
# ---------------------------------------------------------------------------

@workflow_bp.route('/escalations/check', methods=['POST'])
@require_permission('approval', 'update')
def run_escalation_check():
    """Manually trigger an SLA breach scan and escalate breached items."""
    count = check_sla_breaches()
    return success_response(
        data={'escalated': count},
        message=f'{count} item(s) escalated.',
    )


@workflow_bp.route('/escalations', methods=['GET'])
@require_permission('approval', 'read')
def list_escalations():
    """List escalation log entries for the district."""
    page, per_page = validate_pagination_params(
        request.args.get('page', 1), request.args.get('per_page', 20)
    )
    pagination = get_escalation_logs(
        _district(), page=page, per_page=per_page,
        resource_type=request.args.get('resource_type'),
    )
    return paginated_response([e.to_dict() for e in pagination.items], pagination)


# ---------------------------------------------------------------------------
# SLA Summary
# ---------------------------------------------------------------------------

@workflow_bp.route('/sla/summary', methods=['GET'])
@require_permission('approval', 'read')
def sla_summary():
    """SLA compliance summary: open, breached, resolved, compliance %."""
    data = get_sla_summary(_district())
    return success_response(data=data)
