"""Background task definitions for Celery beat.

Each task can also be called synchronously via ``run_sync()`` when Celery
is not available (development / testing).
"""

from __future__ import annotations
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _run_with_app_context(fn):
    from flask import has_app_context
    if has_app_context():
        return fn()

    from app import create_app
    app = create_app(os.getenv('FLASK_ENV', 'default'))
    with app.app_context():
        return fn()


try:
    from app.services.infrastructure.celery_app import celery_app

    @celery_app.task
    def check_sla_breaches_task():
        """Scan and escalate SLA-breached approval requests."""
        from app.services.workflow.escalation_service import check_sla_breaches
        count = check_sla_breaches()
        logger.info('[Beat] SLA breach check: %d escalated.', count)
        return count

    @celery_app.task
    def run_due_schedules_task():
        """Publish social posts whose scheduled time has arrived."""
        from app.services.social.schedule_service import run_due_schedules
        count = run_due_schedules()
        logger.info('[Beat] Run due schedules: %d published.', count)
        return count

    @celery_app.task
    def clean_expired_otps_task():
        """Mark expired OTP codes as used."""
        from app.extensions import db
        from app.models.auth_ext import OtpCode
        now = datetime.now(timezone.utc).isoformat()
        expired = OtpCode.query.filter(
            OtpCode.is_used == False,  # noqa: E712
            OtpCode.expires_at < now,
        ).all()
        for otp in expired:
            otp.is_used = True
        db.session.commit()
        logger.info('[Beat] Cleaned %d expired OTP codes.', len(expired))
        return len(expired)

    @celery_app.task
    def collect_social_comments_task():
        """Collect Facebook/Instagram posts, comments, and likes."""
        def _run():
            from app.services.social.collector_service import collect_all_districts
            summary = collect_all_districts(
                limit=int(os.getenv('SOCIAL_COLLECTOR_POST_LIMIT', 50)),
                comment_limit=int(os.getenv('SOCIAL_COLLECTOR_COMMENT_LIMIT', 100)),
            )
            logger.info('[Beat] Social collector: %s', summary.get('total', summary))
            return summary

        return _run_with_app_context(_run)

except (ImportError, AttributeError):
    # Define sync fallbacks for when Celery is not installed
    def check_sla_breaches_task():
        from app.services.workflow.escalation_service import check_sla_breaches
        return check_sla_breaches()

    def run_due_schedules_task():
        from app.services.social.schedule_service import run_due_schedules
        return run_due_schedules()

    def clean_expired_otps_task():
        from app.extensions import db
        from app.models.auth_ext import OtpCode
        now = datetime.now(timezone.utc).isoformat()
        expired = OtpCode.query.filter(
            OtpCode.is_used == False,  # noqa: E712
            OtpCode.expires_at < now,
        ).all()
        for otp in expired:
            otp.is_used = True
        db.session.commit()
        return len(expired)

    def collect_social_comments_task():
        def _run():
            from app.services.social.collector_service import collect_all_districts
            return collect_all_districts(
                limit=int(os.getenv('SOCIAL_COLLECTOR_POST_LIMIT', 50)),
                comment_limit=int(os.getenv('SOCIAL_COLLECTOR_COMMENT_LIMIT', 100)),
            )

        return _run_with_app_context(_run)
