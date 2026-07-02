"""Collector dashboard analytics for social comments and routed requests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from app.extensions import db
from app.models.comment_analysis import CommentAnalysis
from app.models.department import Department
from app.models.service_request import ServiceRequest
from app.models.social_comment import SocialComment


def get_collector_dashboard(district_id: str, days: int = 30) -> dict:
    """Return Phase 8 Collector Dashboard aggregates."""
    days = max(1, min(days, 365))
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days - 1)
    start_day = start.date()

    comments = SocialComment.query.filter(
        SocialComment.district_id == district_id,
        SocialComment.created_at >= datetime.combine(start_day, datetime.min.time(), tzinfo=timezone.utc),
        SocialComment.created_at <= end,
    )

    total_comments = comments.count()
    positive = comments.filter(SocialComment.sentiment == 'positive').count()
    negative = comments.filter(SocialComment.sentiment == 'negative').count()
    complaints = comments.filter(SocialComment.is_complaint.is_(True)).count()

    daily_counts = _daily_comment_counts(district_id, start_day, end)
    sentiment_trend = _daily_sentiment_counts(district_id, start_day, end)
    department_trend = _department_request_counts(district_id, start_day, end)

    return {
        'period': {
            'days': days,
            'start': start_day.isoformat(),
            'end': end.date().isoformat(),
        },
        'widgets': {
            'total_comments': total_comments,
            'positive': positive,
            'negative': negative,
            'complaints': complaints,
        },
        'daily_trend': daily_counts,
        'sentiment_trend': sentiment_trend,
        'department_trend': department_trend,
    }


def _date_rows(start_day, end_day) -> list[str]:
    count = (end_day - start_day).days + 1
    return [(start_day + timedelta(days=offset)).isoformat() for offset in range(count)]


def _daily_comment_counts(district_id: str, start_day, end: datetime) -> list[dict]:
    rows = (
        db.session.query(
            func.date(SocialComment.created_at).label('day'),
            func.count(SocialComment.id).label('count'),
        )
        .filter(
            SocialComment.district_id == district_id,
            SocialComment.created_at >= datetime.combine(start_day, datetime.min.time(), tzinfo=timezone.utc),
            SocialComment.created_at <= end,
        )
        .group_by(func.date(SocialComment.created_at))
        .all()
    )
    counts = {str(row.day): int(row.count) for row in rows}
    return [{'date': day, 'comments': counts.get(day, 0)} for day in _date_rows(start_day, end.date())]


def _daily_sentiment_counts(district_id: str, start_day, end: datetime) -> list[dict]:
    rows = (
        db.session.query(
            func.date(SocialComment.created_at).label('day'),
            SocialComment.sentiment.label('sentiment'),
            func.count(SocialComment.id).label('count'),
        )
        .filter(
            SocialComment.district_id == district_id,
            SocialComment.created_at >= datetime.combine(start_day, datetime.min.time(), tzinfo=timezone.utc),
            SocialComment.created_at <= end,
        )
        .group_by(func.date(SocialComment.created_at), SocialComment.sentiment)
        .all()
    )

    by_day = {
        day: {'date': day, 'positive': 0, 'negative': 0, 'neutral': 0, 'complaints': 0}
        for day in _date_rows(start_day, end.date())
    }
    for row in rows:
        day = str(row.day)
        label = row.sentiment or 'neutral'
        if label not in ('positive', 'negative', 'neutral'):
            label = 'neutral'
        by_day[day][label] += int(row.count)

    complaint_rows = (
        db.session.query(
            func.date(SocialComment.created_at).label('day'),
            func.count(SocialComment.id).label('count'),
        )
        .filter(
            SocialComment.district_id == district_id,
            SocialComment.created_at >= datetime.combine(start_day, datetime.min.time(), tzinfo=timezone.utc),
            SocialComment.created_at <= end,
            SocialComment.is_complaint.is_(True),
        )
        .group_by(func.date(SocialComment.created_at))
        .all()
    )
    for row in complaint_rows:
        by_day[str(row.day)]['complaints'] = int(row.count)

    return list(by_day.values())


def _department_request_counts(district_id: str, start_day, end: datetime) -> list[dict]:
    rows = (
        db.session.query(
            Department.name.label('department'),
            Department.code.label('code'),
            func.count(ServiceRequest.id).label('requests'),
        )
        .join(Department, Department.id == ServiceRequest.department_id)
        .join(CommentAnalysis, CommentAnalysis.service_request_id == ServiceRequest.id)
        .filter(
            ServiceRequest.district_id == district_id,
            ServiceRequest.created_at >= datetime.combine(start_day, datetime.min.time(), tzinfo=timezone.utc),
            ServiceRequest.created_at <= end,
        )
        .group_by(Department.name, Department.code)
        .order_by(func.count(ServiceRequest.id).desc())
        .all()
    )
    return [
        {
            'department': row.department,
            'code': row.code,
            'requests': int(row.requests),
        }
        for row in rows
    ]
