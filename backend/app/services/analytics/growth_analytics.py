"""Growth Analytics — week-over-week and month-over-month comparisons.

Compares current period metrics against the equivalent prior period to
produce growth rates and trend indicators.
"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta

from app.services.analytics.reach_analytics import get_reach_summary
from app.services.analytics.engagement_analytics import get_engagement_summary

logger = logging.getLogger(__name__)


def _period_delta(start: datetime, end: datetime) -> timedelta:
    return end - start


def get_growth_metrics(district_id: str, start: datetime, end: datetime) -> dict:
    """Compare current period vs the equivalent prior period.

    Args:
        district_id: Tenant scope.
        start:       Current period start.
        end:         Current period end.

    Returns:
        Dict with current metrics, prior metrics, and growth rates (%).
    """
    delta = _period_delta(start, end)
    prior_end   = start
    prior_start = start - delta

    current_reach      = get_reach_summary(district_id, start, end)
    prior_reach        = get_reach_summary(district_id, prior_start, prior_end)
    current_engagement = get_engagement_summary(district_id, start, end)
    prior_engagement   = get_engagement_summary(district_id, prior_start, prior_end)

    def _growth(curr, prev):
        if prev == 0:
            return 100.0 if curr > 0 else 0.0
        return round((curr - prev) / prev * 100, 2)

    c_posts  = current_reach['total_posts_published']
    p_posts  = prior_reach['total_posts_published']
    c_imp    = current_reach['total_impressions']
    p_imp    = prior_reach['total_impressions']
    c_eng    = current_engagement['outbound']['total_engagement']
    p_eng    = prior_engagement['outbound']['total_engagement']
    c_col    = current_reach['total_collected_posts']
    p_col    = prior_reach['total_collected_posts']

    return {
        'current_period': {
            'start': start.isoformat(),
            'end': end.isoformat(),
        },
        'prior_period': {
            'start': prior_start.isoformat(),
            'end': prior_end.isoformat(),
        },
        'metrics': {
            'posts_published': {
                'current': c_posts, 'prior': p_posts,
                'growth_pct': _growth(c_posts, p_posts),
            },
            'impressions': {
                'current': c_imp, 'prior': p_imp,
                'growth_pct': _growth(c_imp, p_imp),
            },
            'total_engagement': {
                'current': c_eng, 'prior': p_eng,
                'growth_pct': _growth(c_eng, p_eng),
            },
            'collected_posts': {
                'current': c_col, 'prior': p_col,
                'growth_pct': _growth(c_col, p_col),
            },
            'engagement_rate': {
                'current': current_engagement['outbound']['engagement_rate_pct'],
                'prior':   prior_engagement['outbound']['engagement_rate_pct'],
                'growth_pct': _growth(
                    current_engagement['outbound']['engagement_rate_pct'],
                    prior_engagement['outbound']['engagement_rate_pct'],
                ),
            },
        },
        'platform_breakdown': current_reach['platform_breakdown'],
    }
