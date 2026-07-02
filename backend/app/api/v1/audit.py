"""Audit and activity log endpoints.

Routes
------
GET /api/v1/audit/logs           — list audit logs for caller's district
GET /api/v1/audit/activity       — list activity logs for caller's district
"""
import logging

from flask import Blueprint, request, g
from flask_jwt_extended import get_jwt

from app.extensions import db
from app.models.audit_log import AuditLog
from app.models.activity_log import ActivityLog
from app.services.rbac_service import require_permission
from app.utils.responses import paginated_response
from app.utils.validators import validate_pagination_params

logger = logging.getLogger(__name__)
audit_bp = Blueprint('audit', __name__, url_prefix='/audit')


def _caller_district_id() -> str:
    return get_jwt().get('district_id', '')


@audit_bp.route('/logs', methods=['GET'])
@require_permission('audit_log', 'read')
def list_audit_logs():
    """List audit log entries for the caller's district (paginated).

    Query params:
        page, per_page, action (filter), resource_type (filter).
    """
    district_id = _caller_district_id()
    page, per_page = validate_pagination_params(
        request.args.get('page', 1),
        request.args.get('per_page', 20),
    )
    query = AuditLog.query.filter_by(district_id=district_id)

    action = request.args.get('action')
    if action:
        query = query.filter(AuditLog.action == action)

    resource_type = request.args.get('resource_type')
    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)

    query = query.order_by(AuditLog.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return paginated_response(
        [entry.to_dict() for entry in pagination.items],
        pagination,
    )


@audit_bp.route('/activity', methods=['GET'])
@require_permission('activity_log', 'read')
def list_activity_logs():
    """List activity log entries for the caller's district (paginated).

    Query params:
        page, per_page, activity_type (filter), user_id (filter).
    """
    district_id = _caller_district_id()
    page, per_page = validate_pagination_params(
        request.args.get('page', 1),
        request.args.get('per_page', 20),
    )
    query = ActivityLog.query.filter_by(district_id=district_id)

    activity_type = request.args.get('activity_type')
    if activity_type:
        query = query.filter(ActivityLog.activity_type == activity_type)

    user_id = request.args.get('user_id')
    if user_id:
        query = query.filter(ActivityLog.user_id == user_id)

    query = query.order_by(ActivityLog.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return paginated_response(
        [entry.to_dict() for entry in pagination.items],
        pagination,
    )
