"""Campaign Analytics — aggregated metrics grouped by hashtag / campaign tag.

A "campaign" is identified by a tag stored in ``SocialPost.meta['campaign']``
or a hashtag extracted from post content. This module groups outbound posts
and their inbound engagement by campaign label.
"""
from __future__ import annotations
import re
import logging
from datetime import datetime

from sqlalchemy import func

from app.extensions import db
from app.models.social_post import SocialPost
from app.models.collected_post import CollectedPost

logger = logging.getLogger(__name__)

HASHTAG_RE = re.compile(r'#(\w+)', re.UNICODE)


def _extract_hashtags(text: str) -> list[str]:
    return [h.lower() for h in HASHTAG_RE.findall(text)]


def get_campaign_summary(district_id: str, start: datetime, end: datetime) -> list[dict]:
    """Group published posts by campaign tag and aggregate engagement.

    Campaign tag is read from ``SocialPost.meta['campaign']`` if present,
    otherwise from the first hashtag in content, otherwise ``'untagged'``.

    Returns:
        List of campaign dicts sorted by total_engagement desc.
    """
    start_iso = start.isoformat()
    end_iso   = end.isoformat()

    posts = (
        SocialPost.query
        .filter(
            SocialPost.district_id == district_id,
            SocialPost.status == 'published',
            SocialPost.published_at >= start_iso,
            SocialPost.published_at <= end_iso,
        )
        .all()
    )

    campaigns: dict[str, dict] = {}
    for post in posts:
        tag = (post.meta or {}).get('campaign')
        if not tag:
            tags = _extract_hashtags(post.content)
            tag = tags[0] if tags else 'untagged'

        if tag not in campaigns:
            campaigns[tag] = {
                'campaign': tag,
                'posts': 0,
                'likes': 0,
                'comments': 0,
                'shares': 0,
                'views': 0,
                'platforms': set(),
            }
        campaigns[tag]['posts']    += 1
        campaigns[tag]['likes']    += post.likes
        campaigns[tag]['comments'] += post.comments
        campaigns[tag]['shares']   += post.shares
        campaigns[tag]['views']    += post.views
        campaigns[tag]['platforms'].add(post.platform)

    result = []
    for tag, data in campaigns.items():
        total_eng = data['likes'] + data['comments'] + data['shares']
        result.append({
            'campaign': tag,
            'posts': data['posts'],
            'likes': data['likes'],
            'comments': data['comments'],
            'shares': data['shares'],
            'views': data['views'],
            'total_engagement': total_eng,
            'engagement_rate_pct': round(total_eng / data['views'] * 100, 2) if data['views'] else 0.0,
            'platforms': list(data['platforms']),
        })

    result.sort(key=lambda x: x['total_engagement'], reverse=True)
    return result


def get_campaign_trend(district_id: str, campaign_tag: str, days: int = 30) -> list[dict]:
    """Return daily engagement for a specific campaign over the last N days."""
    from datetime import timezone, timedelta
    today = datetime.now(timezone.utc).date()
    trend = []
    for i in range(days - 1, -1, -1):
        day = today - timedelta(days=i)
        day_start = f'{day}T00:00:00'
        day_end   = f'{day}T23:59:59'

        # We filter by post content hashtag or meta.campaign — approximate via ILIKE
        rows = (
            SocialPost.query
            .filter(
                SocialPost.district_id == district_id,
                SocialPost.status == 'published',
                SocialPost.published_at >= day_start,
                SocialPost.published_at <= day_end,
                db.or_(
                    SocialPost.content.ilike(f'%#{campaign_tag}%'),
                ),
            )
            .all()
        )
        trend.append({
            'date': str(day),
            'posts': len(rows),
            'likes': sum(r.likes for r in rows),
            'comments': sum(r.comments for r in rows),
            'shares': sum(r.shares for r in rows),
        })
    return trend
