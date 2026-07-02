"""Tests for the Reports API — generate, list, get, export (PDF/Excel)."""
import pytest
from app.models import Permission, Report


def _grant(db_session, role, resource, action):
    p = Permission.query.filter_by(resource=resource, action=action).first()
    if not p:
        p = Permission(resource=resource, action=action)
        db_session.add(p)
        db_session.flush()
    if p not in role.permissions:
        role.permissions.append(p)
        db_session.flush()


@pytest.fixture
def ready_report(db_session, district, admin_user):
    """A pre-built ready report for export tests."""
    r = Report(
        district_id=district.id,
        report_type='daily',
        title='Daily Report Test',
        period_start='2026-06-23',
        period_end='2026-06-23',
        status='ready',
        generated_by=admin_user.id,
        generated_at='2026-06-23T10:00:00+00:00',
        data={
            'reach': {
                'total_posts_published': 5,
                'total_impressions': 1200,
                'total_collected_posts': 30,
                'platform_breakdown': {},
                'top_performing_posts': [],
            },
            'engagement': {
                'outbound': {
                    'posts': 5, 'likes': 100, 'comments': 20,
                    'shares': 10, 'views': 1200,
                    'total_engagement': 130, 'engagement_rate_pct': 10.83,
                },
                'inbound': {
                    'total_collected': 30, 'sentiment_distribution': {},
                    'complaints': 3, 'emergencies': 0, 'spam': 2,
                    'complaint_rate_pct': 10.0, 'emergency_rate_pct': 0.0,
                },
                'top_engaged_posts': [],
            },
            'growth': {
                'current_period': {}, 'prior_period': {},
                'metrics': {
                    'posts_published': {'current': 5, 'prior': 3, 'growth_pct': 66.67},
                },
                'platform_breakdown': {},
            },
            'campaigns': [],
            'platform_engagement': [],
        },
    )
    db_session.add(r)
    db_session.flush()
    return r


class TestReportList:
    def test_requires_auth(self, client):
        resp = client.get('/api/v1/reports')
        assert resp.status_code == 401

    def test_list_reports(self, client, auth_headers, admin_role, db_session, ready_report):
        _grant(db_session, admin_role, 'report', 'read')
        resp = client.get('/api/v1/reports', headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()['meta']['total'] >= 1

    def test_filter_by_type(self, client, auth_headers, admin_role, db_session, ready_report):
        _grant(db_session, admin_role, 'report', 'read')
        resp = client.get('/api/v1/reports?report_type=daily', headers=auth_headers)
        assert resp.status_code == 200
        for r in resp.get_json()['data']:
            assert r['report_type'] == 'daily'


class TestGenerateReport:
    def test_generate_daily(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'report', 'create')
        _grant(db_session, admin_role, 'report', 'read')
        resp = client.post('/api/v1/reports', headers=auth_headers, json={
            'report_type': 'daily',
        })
        assert resp.status_code == 201
        body = resp.get_json()['data']
        assert body['report_type'] == 'daily'
        assert body['status'] in ('ready', 'failed')

    def test_generate_weekly(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'report', 'create')
        resp = client.post('/api/v1/reports', headers=auth_headers, json={'report_type': 'weekly'})
        assert resp.status_code == 201

    def test_generate_monthly(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'report', 'create')
        resp = client.post('/api/v1/reports', headers=auth_headers, json={'report_type': 'monthly'})
        assert resp.status_code == 201

    def test_generate_executive_with_dates(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'report', 'create')
        resp = client.post('/api/v1/reports', headers=auth_headers, json={
            'report_type': 'executive',
            'period_start': '2026-06-01',
            'period_end': '2026-06-30',
        })
        assert resp.status_code == 201

    def test_generate_custom_missing_dates(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'report', 'create')
        resp = client.post('/api/v1/reports', headers=auth_headers, json={
            'report_type': 'custom',
            # period_start and period_end intentionally missing
        })
        assert resp.status_code == 400

    def test_generate_invalid_type(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'report', 'create')
        resp = client.post('/api/v1/reports', headers=auth_headers, json={
            'report_type': 'fortnightly',
        })
        assert resp.status_code == 400

    def test_missing_report_type(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'report', 'create')
        resp = client.post('/api/v1/reports', headers=auth_headers, json={})
        assert resp.status_code == 400


class TestGetReport:
    def test_get_report(self, client, auth_headers, admin_role, db_session, ready_report):
        _grant(db_session, admin_role, 'report', 'read')
        resp = client.get(f'/api/v1/reports/{ready_report.id}', headers=auth_headers)
        assert resp.status_code == 200
        body = resp.get_json()['data']
        assert body['id'] == ready_report.id
        assert 'data' in body
        assert 'reach' in body['data']

    def test_get_report_not_found(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'report', 'read')
        resp = client.get('/api/v1/reports/nonexistent-id', headers=auth_headers)
        assert resp.status_code == 404


class TestReportExport:
    def test_pdf_export(self, client, auth_headers, admin_role, db_session, ready_report):
        _grant(db_session, admin_role, 'report', 'read')
        resp = client.get(f'/api/v1/reports/{ready_report.id}/export/pdf', headers=auth_headers)
        assert resp.status_code == 200
        assert 'PDF' in resp.content_type.upper() or len(resp.data) > 0

    def test_excel_export(self, client, auth_headers, admin_role, db_session, ready_report):
        _grant(db_session, admin_role, 'report', 'read')
        resp = client.get(f'/api/v1/reports/{ready_report.id}/export/excel', headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.data) > 0

    def test_export_pending_report_fails(self, client, auth_headers, admin_role, db_session, district, admin_user):
        _grant(db_session, admin_role, 'report', 'read')
        pending = Report(
            district_id=district.id,
            report_type='daily',
            title='Pending',
            period_start='2026-06-23',
            period_end='2026-06-23',
            status='pending',
            data={},
        )
        db_session.add(pending)
        db_session.flush()
        resp = client.get(f'/api/v1/reports/{pending.id}/export/pdf', headers=auth_headers)
        assert resp.status_code == 400

class TestNamedSocialExports:
    def test_comments_report_excel_export(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'report', 'read')
        resp = client.get('/api/v1/reports/export/comments/excel', headers=auth_headers)
        assert resp.status_code == 200
        assert resp.data[:2] == b'PK'
        assert 'comments_report.xlsx' in resp.headers['Content-Disposition']

    def test_complaints_report_excel_export(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'report', 'read')
        resp = client.get('/api/v1/reports/export/complaints/excel', headers=auth_headers)
        assert resp.status_code == 200
        assert resp.data[:2] == b'PK'
        assert 'complaints_report.xlsx' in resp.headers['Content-Disposition']

    def test_monthly_social_report_pdf_export(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'report', 'read')
        resp = client.get('/api/v1/reports/export/monthly-social/pdf', headers=auth_headers)
        assert resp.status_code == 200
        assert resp.data.startswith(b'%PDF')
        assert 'monthly_social_report.pdf' in resp.headers['Content-Disposition']

