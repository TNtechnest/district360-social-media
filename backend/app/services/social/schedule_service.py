"""Scheduling engine service.

Manages PostSchedule records and triggers post creation when schedules fire.
In production, this should be driven by a Celery beat task (or APScheduler)
that calls ``run_due_schedules()`` every minute.
"""
import logging
from datetime import datetime, timezone

from app.extensions import db
from app.models.post_schedule import PostSchedule
from app.services.social.content_service import create_draft, publish_now
from app.utils.db import paginate_query

logger = logging.getLogger(__name__)


def get_schedules(district_id: str, page: int = 1, per_page: int = 20,
                  status: str | None = None) -> object:
    query = PostSchedule.query.filter_by(district_id=district_id)
    if status:
        query = query.filter(PostSchedule.status == status)
    return paginate_query(query.order_by(PostSchedule.next_run_at.asc()), page, per_page)


def get_schedule(district_id: str, schedule_id: str) -> PostSchedule:
    s = PostSchedule.query.filter_by(id=schedule_id, district_id=district_id).first()
    if not s:
        raise ValueError('Schedule not found.')
    return s


def create_schedule(
    district_id: str,
    account_id: str,
    name: str,
    content_template: str,
    next_run_at: str,
    recurrence: str = 'one_off',
    cron_expression: str | None = None,
    timezone_str: str = 'Asia/Kolkata',
    meta: dict | None = None,
    author_id: str | None = None,
) -> PostSchedule:
    valid_recurrences = {'one_off', 'daily', 'weekly', 'monthly'}
    if recurrence not in valid_recurrences:
        raise ValueError(f"recurrence must be one of: {', '.join(valid_recurrences)}")

    from app.models.social_account import SocialAccount
    account = SocialAccount.query.filter_by(id=account_id, district_id=district_id).first()
    if not account:
        raise ValueError('Social account not found in this district.')

    schedule = PostSchedule(
        district_id=district_id,
        account_id=account_id,
        author_id=author_id,
        name=name,
        platform=account.platform,
        content_template=content_template,
        recurrence=recurrence,
        next_run_at=next_run_at,
        cron_expression=cron_expression,
        timezone=timezone_str,
        meta=meta or {},
        status='active',
    )
    db.session.add(schedule)
    db.session.commit()
    return schedule


def update_schedule(district_id: str, schedule_id: str, **fields) -> PostSchedule:
    schedule = get_schedule(district_id, schedule_id)
    allowed = {'name', 'content_template', 'next_run_at', 'cron_expression',
               'timezone', 'is_active', 'meta', 'status'}
    for k, v in fields.items():
        if k not in allowed:
            raise ValueError(f"Field '{k}' cannot be updated.")
        setattr(schedule, k, v)
    db.session.commit()
    return schedule


def delete_schedule(district_id: str, schedule_id: str) -> None:
    schedule = get_schedule(district_id, schedule_id)
    db.session.delete(schedule)
    db.session.commit()


def run_due_schedules() -> int:
    """Fire all active schedules whose next_run_at <= now.

    Called by a scheduler (Celery beat / APScheduler).

    Returns:
        Number of posts triggered.
    """
    now = datetime.now(timezone.utc).isoformat()
    due = PostSchedule.query.filter(
        PostSchedule.status == 'active',
        PostSchedule.is_active.is_(True),
        PostSchedule.next_run_at <= now,
    ).all()

    triggered = 0
    for schedule in due:
        try:
            post = create_draft(
                district_id=schedule.district_id,
                account_id=schedule.account_id,
                content=schedule.content_template,
                author_id=schedule.author_id,
                meta=schedule.meta,
            )
            publish_now(schedule.district_id, post.id)
            triggered += 1

            if schedule.recurrence == 'one_off':
                schedule.status = 'completed'
                schedule.is_active = False
            else:
                schedule.next_run_at = _advance_next_run(schedule)

            db.session.commit()
        except Exception:
            logger.exception('Failed to fire schedule %s', schedule.id)
            schedule.status = 'failed'
            db.session.commit()

    return triggered


def _advance_next_run(schedule: PostSchedule) -> str:
    """Compute the next ISO run time for a recurring schedule."""
    from datetime import timedelta
    try:
        dt = datetime.fromisoformat(schedule.next_run_at.replace('Z', '+00:00'))
    except ValueError:
        dt = datetime.now(timezone.utc)

    if schedule.recurrence == 'daily':
        dt += timedelta(days=1)
    elif schedule.recurrence == 'weekly':
        dt += timedelta(weeks=1)
    elif schedule.recurrence == 'monthly':
        # Approximate: add 30 days
        dt += timedelta(days=30)
    return dt.isoformat()
