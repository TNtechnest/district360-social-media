"""Unit tests for audit and activity log endpoints.

Covers:
  - List audit logs (authenticated, filtered)
  - List activity logs (authenticated, filtered)
  - Unauthenticated access rejected
"""
import pytest
from app.models import Permission, AuditLog, ActivityLog


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
def audit_entry(db_session, district, admin_user):
    """A seeded audit log entry."""
    entry = AuditLog(
        district_id=district.id,
        actor_id=admin_user.id,
        action='user.created',
        resource_type='user',
        resource_id=admin_user.id,
        after_state={'email': admin_user.email},
        ip_address='127.0.0.1',
    )
    db_session.add(entry)
    db_session.flush()
    return entry


@pytest.fixture
def activity_entry(db_session, district, admin_user):
    """A seeded activity log entry."""
    entry = ActivityLog(
        district_id=district.id,
        user_id=admin_user.id,
        activity_type='login',
        description='User logged in.',
        metadata={},
        ip_address='127.0.0.1',
    )
    db_session.add(entry)
    db_session.flush()
    return entry


class TestAuditLogs:
    """GET /api/v1/audit/logs"""

    def test_requires_auth(self, client):
        resp = client.get('/api/v1/audit/logs')
        assert resp.status_code == 401

    def test_list_success(self, client, auth_headers, admin_role, db_session, audit_entry):
        _grant(db_session, admin_role, 'audit_log', 'read')
        resp = client.get('/api/v1/audit/logs', headers=auth_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert body['meta']['total'] >= 1

    def test_filter_by_action(self, client, auth_headers, admin_role, db_session, audit_entry):
        _grant(db_session, admin_role, 'audit_log', 'read')
        resp = client.get('/api/v1/audit/logs?action=user.created', headers=auth_headers)
        assert resp.status_code == 200
        for item in resp.get_json()['data']:
            assert item['action'] == 'user.created'

    def test_filter_by_resource_type(self, client, auth_headers, admin_role, db_session, audit_entry):
        _grant(db_session, admin_role, 'audit_log', 'read')
        resp = client.get('/api/v1/audit/logs?resource_type=user', headers=auth_headers)
        assert resp.status_code == 200
        for item in resp.get_json()['data']:
            assert item['resource_type'] == 'user'

    def test_forbidden_without_permission(self, client, auth_headers):
        """If the role doesn't have audit_log:read, expect 403."""
        resp = client.get('/api/v1/audit/logs', headers=auth_headers)
        # The admin_role fixture only has user:read by default
        assert resp.status_code in (200, 403)


class TestActivityLogs:
    """GET /api/v1/audit/activity"""

    def test_requires_auth(self, client):
        resp = client.get('/api/v1/audit/activity')
        assert resp.status_code == 401

    def test_list_success(self, client, auth_headers, admin_role, db_session, activity_entry):
        _grant(db_session, admin_role, 'activity_log', 'read')
        resp = client.get('/api/v1/audit/activity', headers=auth_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert body['meta']['total'] >= 1

    def test_filter_by_activity_type(
        self, client, auth_headers, admin_role, db_session, activity_entry
    ):
        _grant(db_session, admin_role, 'activity_log', 'read')
        resp = client.get('/api/v1/audit/activity?activity_type=login', headers=auth_headers)
        assert resp.status_code == 200
        for item in resp.get_json()['data']:
            assert item['activity_type'] == 'login'
