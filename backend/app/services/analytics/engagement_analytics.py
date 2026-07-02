"""Engagement Analytics — likes, comments, shares, sentiment distribution,
complaint/emergency/spam rates from collected posts.
"""
from __future__ import annotations
import logging
from datetime import datetime

from sqlalchemy import func

from app.extensions import db
from app.models.collected_post import CollectedPost
from app.models.social_post import SocialPost

logger = logging.getLogger(__name__)


def get_engagement_summary(district_id: str, start: datetime, end: datetime) -> dict:
    """Aggregate engagement metrics.

    Returns:
        Dict with totals, rates, sentiment breakdown, AI flag breakdown,
        top engaged collected posts, and engagement rate.
    """
    start_iso = start.isoformat()
    end_iso   = end.isoformat()

    # Outbound engagement (published posts)
    out = (
        db.session.query(
            func.count(SocialPost.id).label('posts'),
            func.coalesce(func.sum(SocialPost.likes),    0).label('likes'),
            func.coalesce(func.sum(SocialPost.comments), 0).label('comments'),
            func.coalesce(func.sum(SocialPost.shares),   0).label('shares'),
            func.coalesce(func.sum(SocialPost.views),    0).label('views'),
        )
        .filter(
            SocialPost.district_id == district_id,
            SocialPost.status == 'published',
            SocialPost.published_at >= start_iso,
            SocialPost.published_at <= end_iso,
        )
        .one()
    )

    total_outbound_engagement = int(out.likes) + int(out.comments) + int(out.shares)
    engagement_rate = (
        round(total_outbound_engagement / int(out.views) * 100, 2)
        if int(out.views) > 0 else 0.0
    )

    # Inbound sentiment distribution
    sentiments = (
        db.session.query(
            CollectedPost.sentiment,
            func.count(CollectedPost.id).label('count'),
        )
        .filter(
            CollectedPost.district_id == district_id,
            CollectedPost.created_at >= start,
            CollectedPost.created_at <= end,
            CollectedPost.sentiment.isnot(None),
        )
        .group_by(CollectedPost.sentiment)
        .all()
    )
    sentiment_dist = {row.sentiment: row.count for row in sentiments}

    # AI flag counts
    flags = (
        db.session.query(
            func.count(CollectedPost.id).label('total'),
            func.sum(db.cast(CollectedPost.is_complaint, db.Integer)).label('complaints'),
            func.sum(db.cast(CollectedPost.is_emergency, db.Integer)).label('emergencies'),
            func.sum(db.cast(CollectedPost.is_spam,      db.Integer)).label('spam'),
        )
        .filter(
            CollectedPost.district_id == district_id,
            CollectedPost.created_at >= start,
            CollectedPost.created_at <= end,
        )
        .one()
    )

    total_collected = int(flags.total or 0)

    # Top 5 most engaged collected posts
    top_engaged = (
        CollectedPost.query
        .filter(
            CollectedPost.district_id == district_id,
            CollectedPost.created_at >= start,
            CollectedPost.created_at <= end,
        )
        .order_by((CollectedPost.likes + CollectedPost.comments + CollectedPost.shares).desc())
        .limit(5)
        .all()
    )

    return {
        'period': {'start': start_iso, 'end': end_iso},
        'outbound': {
            'posts': int(out.posts),
            'likes': int(out.likes),
            'comments': int(out.comments),
            'shares': int(out.shares),
            'views': int(out.views),
            'total_engagement': total_outbound_engagement,
            'engagement_rate_pct': engagement_rate,
        },
        'inbound': {
            'total_collected': total_collected,
            'sentiment_distribution': sentiment_dist,
            'complaints': int(flags.complaints or 0),
            'emergencies': int(flags.emergencies or 0),
            'spam': int(flags.spam or 0),
            'complaint_rate_pct': round(int(flags.complaints or 0) / total_collected * 100, 2) if total_collected else 0,
            'emergency_rate_pct': round(int(flags.emergencies or 0) / total_collected * 100, 2) if total_collected else 0,
        },
        'top_engaged_posts': [
            {
                'id': p.id,
                'platform': p.platform,
                'text_preview': p.raw_text[:100],
                'likes': p.likes,
                'comments': p.comments,
                'shares': p.shares,
                'sentiment': p.sentiment,
                'is_complaint': p.is_complaint,
            }
            for p in top_engaged
        ],
    }


def get_platform_engagement(district_id: str, start: datetime, end: datetime) -> list[dict]:
    """Engagement breakdown per platform."""
    rows = (
        db.session.query(
            CollectedPost.platform,
            func.count(CollectedPost.id).label('posts'),
            func.coalesce(func.sum(CollectedPost.likes),    0).label('likes'),
            func.coalesce(func.sum(CollectedPost.comments), 0).label('comments'),
            func.coalesce(func.sum(CollectedPost.shares),   0).label('shares'),
        )
        .filter(
            CollectedPost.district_id == district_id,
            CollectedPost.created_at >= start,
            CollectedPost.created_at <= end,
        )
        .group_by(CollectedPost.platform)
        .all()
    )
    return [
        {
            'platform': r.platform,
            'posts': r.posts,
            'likes': int(r.likes),
            'comments': int(r.comments),
            'shares': int(r.shares),
            'total_engagement': int(r.likes) + int(r.comments) + int(r.shares),
        }
        for r in rows
    ]
