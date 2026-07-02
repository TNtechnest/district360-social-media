"""Analytics API endpoints.

Routes
------
GET /api/v1/analytics/reach            — reach summary for a period
GET /api/v1/analytics/reach/trend      — daily reach trend (last N days)
GET /api/v1/analytics/engagement       — engagement summary
GET /api/v1/analytics/engagement/platform — per-platform breakdown
GET /api/v1/analytics/growth           — growth vs prior period
GET /api/v1/analytics/campaigns        — campaign performance list
GET /api/v1/analytics/campaigns/<tag>/trend — daily trend for one campaign
"""
import logging
from datetime import datetime, timezone, timedelta

from flask import Blueprint, request
from flask_jwt_extended import get_jwt

from app.services.analytics.reach_analytics import get_reach_summary, get_reach_trend
from app.services.analytics.engagement_analytics import get_engagement_summary, get_platform_engagement
from app.services.analytics.growth_analytics import get_growth_metrics
from app.services.analytics.campaign_analytics import get_campaign_summary, get_campaign_trend
from app.services.rbac_service import require_permission
from app.utils.responses import success_response, error_response

logger = logging.getLogger(__name__)
analytics_bp = Blueprint('analytics', __name__, url_prefix='/analytics')


def _district():
    return get_jwt().get('district_id', '')


def _parse_window(default_days: int = 30) -> tuple[datetime, datetime]:
    """Parse ``?start=YYYY-MM-DD&end=YYYY-MM-DD`` or default to last N days."""
    now = datetime.now(timezone.utc)
    try:
        start_str = request.args.get('start')
        end_str   = request.args.get('end')
        if start_str and end_str:
            start = datetime.strptime(start_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            end   = datetime.strptime(end_str,   '%Y-%m-%d').replace(
                hour=23, minute=59, second=59, tzinfo=timezone.utc)
        else:
            end   = now
            start = now - timedelta(days=default_days)
        return start, end
    except ValueError:
        raise ValueError("Date format must be YYYY-MM-DD (e.g. ?start=2026-06-01&end=2026-06-30)")


@analytics_bp.route('/reach', methods=['GET'])
@require_permission('analytics', 'read')
def reach_summary():
    """Reach summary: total posts, impressions, collected posts, platform breakdown."""
    try:
        start, end = _parse_window(30)
        data = get_reach_summary(_district(), start, end)
        return success_response(data=data)
    except ValueError as exc:
        return error_response(str(exc), 400, 'VALIDATION_ERROR')


@analytics_bp.route('/reach/trend', methods=['GET'])
@require_permission('analytics', 'read')
def reach_trend():
    """Daily reach trend for the last N days (default 30)."""
    try:
        days = min(int(request.args.get('days', 30)), 365)
    except ValueError:
        return error_response('days must be an integer.', 400, 'VALIDATION_ERROR')
    data = get_reach_trend(_district(), days=days)
    return success_response(data=data)


@analytics_bp.route('/engagement', methods=['GET'])
@require_permission('analytics', 'read')
def engagement_summary():
    """Engagement summary: outbound totals, sentiment distribution, AI flags."""
    try:
        start, end = _parse_window(30)
        data = get_engagement_summary(_district(), start, end)
        return success_response(data=data)
    except ValueError as exc:
        return error_response(str(exc), 400, 'VALIDATION_ERROR')


@analytics_bp.route('/engagement/platform', methods=['GET'])
@require_permission('analytics', 'read')
def platform_engagement():
    """Per-platform engagement breakdown (likes, comments, shares)."""
    try:
        start, end = _parse_window(30)
        data = get_platform_engagement(_district(), start, end)
        return success_response(data=data)
    except ValueError as exc:
        return error_response(str(exc), 400, 'VALIDATION_ERROR')


@analytics_bp.route('/growth', methods=['GET'])
@require_permission('analytics', 'read')
def growth():
    """Growth metrics vs the equivalent prior period."""
    try:
        start, end = _parse_window(30)
        data = get_growth_metrics(_district(), start, end)
        return success_response(data=data)
    except ValueError as exc:
        return error_response(str(exc), 400, 'VALIDATION_ERROR')


@analytics_bp.route('/campaigns', methods=['GET'])
@require_permission('analytics', 'read')
def campaigns():
    """Campaign performance: sorted by total engagement."""
    try:
        start, end = _parse_window(30)
        data = get_campaign_summary(_district(), start, end)
        return success_response(data=data)
    except ValueError as exc:
        return error_response(str(exc), 400, 'VALIDATION_ERROR')


@analytics_bp.route('/campaigns/<campaign_tag>/trend', methods=['GET'])
@require_permission('analytics', 'read')
def campaign_trend(campaign_tag):
    """Daily engagement trend for a specific campaign tag."""
    try:
        days = min(int(request.args.get('days', 30)), 365)
    except ValueError:
        return error_response('days must be an integer.', 400, 'VALIDATION_ERROR')
    data = get_campaign_trend(_district(), campaign_tag, days=days)
    return success_response(data=data)
