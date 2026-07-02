"""Collector dashboard endpoints for Phase 8."""

from flask import Blueprint, request
from flask_jwt_extended import get_jwt

from app.services.rbac_service import require_permission
from app.services.social.collector_dashboard_service import get_collector_dashboard
from app.utils.responses import success_response

collector_dashboard_bp = Blueprint(
    'social_collector_dashboard',
    __name__,
    url_prefix='/collector',
)


def _district() -> str:
    return get_jwt().get('district_id', '')


@collector_dashboard_bp.route('/dashboard', methods=['GET'])
@require_permission('collected_post', 'read')
def collector_dashboard():
    days = request.args.get('days', 14, type=int) or 14
    data = get_collector_dashboard(_district(), days=days)
    return success_response(data=data)
