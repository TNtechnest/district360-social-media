"""Reach Analytics — total audience, impressions, follower trends.

Computes reach metrics from CollectedPost and SocialPost data stored
in the database.  No external API call is needed for historical data.
To get live follower counts, the connector's ``get_account_info()`` is
called at report-generation time (optional / async).
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import func

from app.extensions import db
from app.models.collected_post import CollectedPost
from app.models.social_post import SocialPost
from app.models.social_account import SocialAccount

logger = logging.getLogger(__name__)


def get_reach_summary(district_id: str, start: datetime, end: datetime) -> dict:
    """Aggregate reach metrics for the given period.

    Args:
        district_id: Tenant scope.
        start:       Period start (timezone-aware datetime).
        end:         Period end (timezone-aware datetime).

    Returns:
        Dict with total_posts_published, total_collected, total_impressions
        (views proxy), platform_breakdown, top_performing_posts.
    """
    start_iso = start.isoformat()
    end_iso   = end.isoformat()

    # Published posts in window
    published = (
        db.session.query(
            SocialPost.platform,
            func.count(SocialPost.id).label('count'),
            func.sum(SocialPost.views).label('total_views'),
            func.sum(SocialPost.likes).label('total_likes'),
        )
        .filter(
            SocialPost.district_id == district_id,
            SocialPost.status == 'published',
            SocialPost.published_at >= start_iso,
            SocialPost.published_at <= end_iso,
        )
        .group_by(SocialPost.platform)
        .all()
    )

    # Collected posts in window (inbound reach)
    collected = (
        db.session.query(
            CollectedPost.platform,
            func.count(CollectedPost.id).label('count'),
        )
        .filter(
            CollectedPost.district_id == district_id,
            CollectedPost.created_at >= start,
            CollectedPost.created_at <= end,
        )
        .group_by(CollectedPost.platform)
        .all()
    )

    platform_breakdown = {}
    total_views = 0
    total_posts = 0

    for row in published:
        platform_breakdown.setdefault(row.platform, {})
        platform_breakdown[row.platform]['published_posts'] = row.count
        platform_breakdown[row.platform]['total_views']     = int(row.total_views or 0)
        platform_breakdown[row.platform]['total_likes']     = int(row.total_likes or 0)
        total_views += int(row.total_views or 0)
        total_posts += row.count

    total_collected = 0
    for row in collected:
        platform_breakdown.setdefault(row.platform, {})
        platform_breakdown[row.platform]['collected_posts'] = row.count
        total_collected += row.count

    # Top 5 performing published posts by views
    top_posts = (
        SocialPost.query
        .filter(
            SocialPost.district_id == district_id,
            SocialPost.status == 'published',
            SocialPost.published_at >= start_iso,
            SocialPost.published_at <= end_iso,
        )
        .order_by(SocialPost.views.desc())
        .limit(5)
        .all()
    )

    return {
        'period': {'start': start_iso, 'end': end_iso},
        'total_posts_published': total_posts,
        'total_collected_posts': total_collected,
        'total_impressions': total_views,
        'platform_breakdown': platform_breakdown,
        'top_performing_posts': [
            {
                'id': p.id,
                'content_preview': p.content[:100],
                'platform': p.platform,
                'views': p.views,
                'likes': p.likes,
                'published_at': p.published_at,
            }
            for p in top_posts
        ],
    }


def get_reach_trend(district_id: str, days: int = 30) -> list[dict]:
    """Return daily view/impression counts for the last N days.

    Args:
        district_id: Tenant scope.
        days:        Number of trailing days to include.

    Returns:
        List of dicts: [{'date': 'YYYY-MM-DD', 'views': int, 'posts': int}]
    """
    result = []
    today = datetime.now(timezone.utc).date()
    for i in range(days - 1, -1, -1):
        day = today - timedelta(days=i)
        day_start = f'{day}T00:00:00'
        day_end   = f'{day}T23:59:59'

        row = (
            db.session.query(
                func.count(SocialPost.id).label('posts'),
                func.coalesce(func.sum(SocialPost.views), 0).label('views'),
            )
            .filter(
                SocialPost.district_id == district_id,
                SocialPost.status == 'published',
                SocialPost.published_at >= day_start,
                SocialPost.published_at <= day_end,
            )
            .one()
        )
        result.append({'date': str(day), 'posts': row.posts, 'views': int(row.views)})

    return result
