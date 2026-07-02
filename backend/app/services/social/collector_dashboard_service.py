"""Collector dashboard aggregates for Phase 8."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from app.models.collected_post import CollectedPost
from app.models.comment_analysis import CommentAnalysis
from app.models.department import Department
from app.models.service_request import ServiceRequest
from app.models.social_comment import SocialComment


COMMENT_LIKE_TYPES = ('comment', 'reel_comment', 'story_reply', 'dm', 'mention')
SENTIMENTS = ('positive', 'negative', 'neutral', 'mixed')


def _window(days: int) -> tuple[datetime, list[str]]:
    safe_days = max(1, min(days, 90))
    today = datetime.now(timezone.utc).date()
    start_date = today - timedelta(days=safe_days - 1)
    labels = [(start_date + timedelta(days=offset)).isoformat() for offset in range(safe_days)]
    return datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc), labels


def _date_key(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.date().isoformat()


def get_collector_dashboard(district_id: str, days: int = 14) -> dict:
    """Return widget and chart data for the collector dashboard."""
    start_at, labels = _window(days)

    comment_query = SocialComment.query.filter_by(district_id=district_id)
    collected_query = CollectedPost.query.filter(
        CollectedPost.district_id == district_id,
        CollectedPost.content_type.in_(COMMENT_LIKE_TYPES),
    )

    total_comments = comment_query.count() + collected_query.count()
    positive = (
        comment_query.filter(SocialComment.sentiment == 'positive').count()
        + collected_query.filter(CollectedPost.sentiment == 'positive').count()
    )
    negative = (
        comment_query.filter(SocialComment.sentiment == 'negative').count()
        + collected_query.filter(CollectedPost.sentiment == 'negative').count()
    )
    complaints = (
        comment_query.filter(SocialComment.is_complaint.is_(True)).count()
        + collected_query.filter(CollectedPost.is_complaint.is_(True)).count()
    )

    daily_counts = dict.fromkeys(labels, 0)
    sentiment_counts = {
        label: {'date': label, 'positive': 0, 'negative': 0, 'neutral': 0, 'mixed': 0}
        for label in labels
    }

    recent_comments = comment_query.filter(SocialComment.created_at >= start_at).all()
    recent_collected = collected_query.filter(CollectedPost.created_at >= start_at).all()

    for item in (*recent_comments, *recent_collected):
        key = _date_key(item.created_at)
        if key not in daily_counts:
            continue
        daily_counts[key] += 1
        sentiment = item.sentiment if item.sentiment in SENTIMENTS else 'neutral'
        sentiment_counts[key][sentiment] += 1

    department_counts = defaultdict(int)
    rows = (
        CommentAnalysis.query
        .join(ServiceRequest, CommentAnalysis.service_request_id == ServiceRequest.id)
        .outerjoin(Department, ServiceRequest.department_id == Department.id)
        .filter(
            CommentAnalysis.district_id == district_id,
            CommentAnalysis.is_complaint.is_(True),
        )
        .with_entities(func.coalesce(Department.name, 'Unassigned'), func.count(CommentAnalysis.id))
        .group_by(func.coalesce(Department.name, 'Unassigned'))
        .all()
    )
    for name, count in rows:
        department_counts[name] += count

    linked_count = sum(department_counts.values())
    unassigned_count = max(complaints - linked_count, 0)
    if unassigned_count:
        department_counts['Unassigned'] += unassigned_count

    department_trend = [
        {'department': name, 'complaints': count}
        for name, count in sorted(department_counts.items(), key=lambda item: item[1], reverse=True)
    ]

    if not department_trend:
        department_trend = [{'department': 'Unassigned', 'complaints': 0}]

    return {
        'widgets': {
            'total_comments': total_comments,
            'positive': positive,
            'negative': negative,
            'complaints': complaints,
        },
        'charts': {
            'daily_trend': [
                {'date': label, 'comments': daily_counts[label]}
                for label in labels
            ],
            'sentiment_trend': [sentiment_counts[label] for label in labels],
            'department_trend': department_trend,
        },
    }
