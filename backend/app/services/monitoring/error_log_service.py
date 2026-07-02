"""Error log monitoring service.

Queries the AuditLog and Flask application logs for error patterns.
Provides aggregated error summaries for the monitoring dashboard.
No separate error_log table is needed — we reuse AuditLog with
action prefixed ``'error.'`` and query the DB for anomaly counts.
"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta

from sqlalchemy import func

from app.extensions import db
from app.models.audit_log import AuditLog
from app.models.activity_log import ActivityLog

logger = logging.getLogger(__name__)


def get_error_summary(district_id: str, hours: int = 24) -> dict:
    """Return error counts for the last N hours from audit and activity logs.

    Args:
        district_id: Tenant scope.
        hours:       Lookback window in hours (default 24).

    Returns:
        Dict with total_errors, error_by_action, recent_errors list.
    """
    since = datetime.utcnow() - timedelta(hours=hours)

    rows = (
        db.session.query(
            AuditLog.action,
            func.count(AuditLog.id).label('count'),
        )
        .filter(
            AuditLog.district_id == district_id,
            AuditLog.action.like('error.%'),
            AuditLog.created_at >= since,
        )
        .group_by(AuditLog.action)
        .all()
    )

    error_by_action = {r.action: r.count for r in rows}
    total_errors = sum(error_by_action.values())

    recent = (
        AuditLog.query
        .filter(
            AuditLog.district_id == district_id,
            AuditLog.action.like('error.%'),
            AuditLog.created_at >= since,
        )
        .order_by(AuditLog.created_at.desc())
        .limit(20)
        .all()
    )

    return {
        'period_hours': hours,
        'total_errors': total_errors,
        'error_by_action': error_by_action,
        'recent_errors': [e.to_dict() for e in recent],
    }


def get_activity_summary(district_id: str, hours: int = 24) -> dict:
    """Aggregate activity log counts by type for the last N hours.

    Args:
        district_id: Tenant scope.
        hours:       Lookback window in hours.

    Returns:
        Dict with total_activities, activity_by_type, top_users.
    """
    since = datetime.utcnow() - timedelta(hours=hours)

    by_type = (
        db.session.query(
            ActivityLog.activity_type,
            func.count(ActivityLog.id).label('count'),
        )
        .filter(
            ActivityLog.district_id == district_id,
            ActivityLog.created_at >= since,
        )
        .group_by(ActivityLog.activity_type)
        .order_by(func.count(ActivityLog.id).desc())
        .all()
    )

    by_user = (
        db.session.query(
            ActivityLog.user_id,
            func.count(ActivityLog.id).label('count'),
        )
        .filter(
            ActivityLog.district_id == district_id,
            ActivityLog.created_at >= since,
            ActivityLog.user_id.isnot(None),
        )
        .group_by(ActivityLog.user_id)
        .order_by(func.count(ActivityLog.id).desc())
        .limit(10)
        .all()
    )

    return {
        'period_hours': hours,
        'total_activities': sum(r.count for r in by_type),
        'activity_by_type': {r.activity_type: r.count for r in by_type},
        'top_users': [{'user_id': r.user_id, 'count': r.count} for r in by_user],
    }


def get_audit_summary(district_id: str, hours: int = 24) -> dict:
    """Summarise audit log entries grouped by action prefix.

    Args:
        district_id: Tenant scope.
        hours:       Lookback window in hours.

    Returns:
        Dict with total_entries, action_breakdown, recent_entries.
    """
    since = datetime.utcnow() - timedelta(hours=hours)

    by_action = (
        db.session.query(
            AuditLog.action,
            func.count(AuditLog.id).label('count'),
        )
        .filter(
            AuditLog.district_id == district_id,
            AuditLog.created_at >= since,
        )
        .group_by(AuditLog.action)
        .order_by(func.count(AuditLog.id).desc())
        .limit(20)
        .all()
    )

    recent = (
        AuditLog.query
        .filter(
            AuditLog.district_id == district_id,
            AuditLog.created_at >= since,
        )
        .order_by(AuditLog.created_at.desc())
        .limit(20)
        .all()
    )

    return {
        'period_hours': hours,
        'total_entries': sum(r.count for r in by_action),
        'action_breakdown': {r.action: r.count for r in by_action},
        'recent_entries': [e.to_dict() for e in recent],
    }
