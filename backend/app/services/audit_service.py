"""Service layer for writing audit and activity log entries.

Audit logs are immutable records of significant data-change events.
Activity logs are higher-volume behavioural records used for analytics.
Both are written inside the current SQLAlchemy session so that they are
committed together with the data change (or rolled back together).
"""
import logging
from flask import request as flask_request

from app.extensions import db
from app.models.audit_log import AuditLog
from app.models.activity_log import ActivityLog

logger = logging.getLogger(__name__)


def write_audit_log(
    district_id: str,
    actor_id: str | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    before_state: dict | None = None,
    after_state: dict | None = None,
):
    """Append an audit log entry to the current session.

    The caller is responsible for committing (or rolling back) the session.

    Args:
        district_id:   Tenant scope.
        actor_id:      UUID of the user performing the action, or None for system.
        action:        Verb string, e.g. ``'user.created'``, ``'role.updated'``.
        resource_type: Model name / table name, e.g. ``'user'``, ``'department'``.
        resource_id:   UUID of the affected row.
        before_state:  Snapshot before the change (dict or None).
        after_state:   Snapshot after the change (dict or None).
    """
    try:
        entry = AuditLog(
            district_id=district_id,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            before_state=before_state,
            after_state=after_state,
            ip_address=_get_ip(),
            user_agent=_get_ua(),
        )
        db.session.add(entry)
    except Exception:  # pragma: no cover
        logger.exception('Failed to write audit log entry — action=%s resource=%s', action, resource_id)


def write_activity_log(
    district_id: str,
    user_id: str | None,
    activity_type: str,
    description: str | None = None,
    metadata: dict | None = None,
):
    """Append an activity log entry to the current session.

    Args:
        district_id:   Tenant scope.
        user_id:       UUID of the acting user, or None for anonymous / system.
        activity_type: Short camelCase label, e.g. ``'login'``, ``'request.viewed'``.
        description:   Human-readable narrative.
        metadata:      Arbitrary extra data (keep small).
    """
    try:
        entry = ActivityLog(
            district_id=district_id,
            user_id=user_id,
            activity_type=activity_type,
            description=description,
            metadata_=metadata or {},
            ip_address=_get_ip(),
            user_agent=_get_ua(),
        )
        db.session.add(entry)
    except Exception:  # pragma: no cover
        logger.exception(
            'Failed to write activity log entry — type=%s user=%s', activity_type, user_id
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_ip() -> str | None:
    """Extract the client IP from the current request context, if any."""
    try:
        return flask_request.remote_addr
    except RuntimeError:
        return None


def _get_ua() -> str | None:
    """Extract the User-Agent header from the current request context, if any."""
    try:
        return flask_request.headers.get('User-Agent')
    except RuntimeError:
        return None
