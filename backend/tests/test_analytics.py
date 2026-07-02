"""Tests for Analytics Engine — reach, engagement, growth, campaign APIs.

All tests run against the in-memory/test DB. Because there is no real data,
we test that:
  - Endpoints return correct structure and 200 status.
  - Empty data returns zero-value dicts (no 500s).
  - Auth is enforced.
  - Date validation works.
"""
import pytest
from app.models import Permission


def _grant(db_session, role, resource, action):
    p = Permission.query.filter_by(resource=resource, action=action).first()
    if not p:
        p = Permission(resource=resource, action=action)
        db_session.add(p)
        db_session.flush()
    if p not in role.permissions:
        role.permissions.append(p)
        db_session.flush()


class TestReachAnalytics:
    def test_requires_auth(self, client):
        resp = client.get('/api/v1/analytics/reach')
        assert resp.status_code == 401

    def test_reach_summary_empty_data(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'analytics', 'read')
        resp = client.get('/api/v1/analytics/reach', headers=auth_headers)
        assert resp.status_code == 200
        body = resp.get_json()['data']
        assert 'total_posts_published' in body
        assert 'total_impressions' in body
        assert 'platform_breakdown' in body
        assert 'top_performing_posts' in body

    def test_reach_with_date_range(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'analytics', 'read')
        resp = client.get(
            '/api/v1/analytics/reach?start=2026-06-01&end=2026-06-30',
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_reach_invalid_date(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'analytics', 'read')
        resp = client.get(
            '/api/v1/analytics/reach?start=not-a-date&end=also-bad',
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_reach_trend(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'analytics', 'read')
        resp = client.get('/api/v1/analytics/reach/trend?days=7', headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()['data']
        assert isinstance(data, list)
        assert len(data) == 7
        assert 'date' in data[0]
        assert 'views' in data[0]
        assert 'posts' in data[0]

    def test_reach_trend_invalid_days(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'analytics', 'read')
        resp = client.get('/api/v1/analytics/reach/trend?days=abc', headers=auth_headers)
        assert resp.status_code == 400


class TestEngagementAnalytics:
    def test_engagement_summary_structure(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'analytics', 'read')
        resp = client.get('/api/v1/analytics/engagement', headers=auth_headers)
        assert resp.status_code == 200
        body = resp.get_json()['data']
        assert 'outbound' in body
        assert 'inbound' in body
        assert 'top_engaged_posts' in body
        assert 'engagement_rate_pct' in body['outbound']
        assert 'sentiment_distribution' in body['inbound']

    def test_platform_engagement_structure(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'analytics', 'read')
        resp = client.get('/api/v1/analytics/engagement/platform', headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.get_json()['data'], list)


class TestGrowthAnalytics:
    def test_growth_structure(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'analytics', 'read')
        resp = client.get('/api/v1/analytics/growth', headers=auth_headers)
        assert resp.status_code == 200
        body = resp.get_json()['data']
        assert 'current_period' in body
        assert 'prior_period' in body
        assert 'metrics' in body
        metrics = body['metrics']
        assert 'posts_published' in metrics
        assert 'impressions' in metrics
        assert 'growth_pct' in metrics['posts_published']


class TestCampaignAnalytics:
    def test_campaigns_returns_list(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'analytics', 'read')
        resp = client.get('/api/v1/analytics/campaigns', headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.get_json()['data'], list)

    def test_campaign_trend(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'analytics', 'read')
        resp = client.get(
            '/api/v1/analytics/campaigns/watercampaign/trend?days=7',
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()['data']
        assert isinstance(data, list)
        assert len(data) == 7
