"""Monitoring API endpoints — health, audit summaries, activity, and error logs.

Routes
------
GET /api/v1/monitoring/health          — full health check (DB, Redis, system)
GET /api/v1/monitoring/audit           — audit log summary (last N hours)
GET /api/v1/monitoring/activity        — activity log summary (last N hours)
GET /api/v1/monitoring/errors          — error log summary (last N hours)
"""
import logging

from flask import Blueprint, request
from flask_jwt_extended import get_jwt

from app.services.monitoring.health_service import get_full_health
from app.services.monitoring.error_log_service import (
    get_error_summary, get_activity_summary, get_audit_summary,
)
from app.services.rbac_service import require_permission
from app.utils.responses import success_response, error_response

logger = logging.getLogger(__name__)
monitoring_bp = Blueprint('monitoring', __name__, url_prefix='/monitoring')


def _district():
    return get_jwt().get('district_id', '')


def _hours() -> int:
    """Parse ``?hours=N`` query param, clamped to [1, 720]."""
    try:
        return max(1, min(int(request.args.get('hours', 24)), 720))
    except ValueError:
        return 24


@monitoring_bp.route('/health', methods=['GET'])
def health():
    """Full health check — DB, Redis, system disk.

    This endpoint is public (no JWT required) so that load balancers and
    uptime monitors can call it without authentication.
    """
    result = get_full_health()
    status_code = 200 if result['status'] == 'healthy' else (
        503 if result['status'] == 'unhealthy' else 207
    )
    resp, _ = success_response(data=result)
    return resp, status_code


@monitoring_bp.route('/audit', methods=['GET'])
@require_permission('audit_log', 'read')
def audit_summary():
    """Audit log summary for the last N hours (default 24).

    Query param: ``?hours=48``
    """
    data = get_audit_summary(_district(), hours=_hours())
    return success_response(data=data)


@monitoring_bp.route('/activity', methods=['GET'])
@require_permission('activity_log', 'read')
def activity_summary():
    """Activity log summary for the last N hours.

    Query param: ``?hours=24``
    """
    data = get_activity_summary(_district(), hours=_hours())
    return success_response(data=data)


@monitoring_bp.route('/errors', methods=['GET'])
@require_permission('audit_log', 'read')
def error_summary():
    """Error log summary from the audit log for the last N hours.

    Query param: ``?hours=24``
    """
    data = get_error_summary(_district(), hours=_hours())
    return success_response(data=data)
