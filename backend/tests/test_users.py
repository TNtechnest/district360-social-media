"""Unit tests for user management endpoints and service.

Covers:
  - List users
  - Create user (validation, duplicate email, role assignment)
  - Get user by ID
  - Update user
  - Deactivate user
  - Assign roles
  - /me endpoint
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


class TestMe:
    """GET /api/v1/users/me"""

    def test_me_returns_current_user(self, client, auth_headers, admin_user):
        resp = client.get('/api/v1/users/me', headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()['data']
        assert data['email'] == 'admin@test.example'

    def test_me_requires_auth(self, client):
        resp = client.get('/api/v1/users/me')
        assert resp.status_code == 401


class TestListUsers:
    """GET /api/v1/users"""

    def test_list_success(self, client, auth_headers, admin_user, db_session, admin_role):
        _grant(db_session, admin_role, 'user', 'read')
        resp = client.get('/api/v1/users', headers=auth_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert isinstance(body['data'], list)
        assert body['meta']['total'] >= 1

    def test_list_requires_auth(self, client):
        resp = client.get('/api/v1/users')
        assert resp.status_code == 401


class TestCreateUser:
    """POST /api/v1/users"""

    def test_create_success(self, client, auth_headers, admin_role, db_session, district):
        _grant(db_session, admin_role, 'user', 'create')
        _grant(db_session, admin_role, 'user', 'read')
        resp = client.post('/api/v1/users', headers=auth_headers, json={
            'email': 'newuser@example.com',
            'full_name': 'New User',
            'password': 'NewPass1!',
        })
        assert resp.status_code == 201
        body = resp.get_json()
        assert body['data']['email'] == 'newuser@example.com'

    def test_create_duplicate_email(self, client, auth_headers, admin_role, db_session, admin_user):
        _grant(db_session, admin_role, 'user', 'create')
        resp = client.post('/api/v1/users', headers=auth_headers, json={
            'email': 'admin@test.example',   # already exists
            'full_name': 'Dupe',
            'password': 'Dupe1234A',
        })
        assert resp.status_code == 400

    def test_create_invalid_email(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'user', 'create')
        resp = client.post('/api/v1/users', headers=auth_headers, json={
            'email': 'not-an-email',
            'full_name': 'Bad Email',
            'password': 'Password1',
        })
        assert resp.status_code == 400

    def test_create_weak_password(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'user', 'create')
        resp = client.post('/api/v1/users', headers=auth_headers, json={
            'email': 'weakpass@example.com',
            'full_name': 'Weak',
            'password': '1234',
        })
        assert resp.status_code == 400

    def test_create_missing_email(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'user', 'create')
        resp = client.post('/api/v1/users', headers=auth_headers, json={
            'full_name': 'No Email',
            'password': 'Password1A',
        })
        assert resp.status_code == 400


class TestGetUser:
    """GET /api/v1/users/<id>"""

    def test_get_success(self, client, auth_headers, admin_role, db_session, admin_user):
        _grant(db_session, admin_role, 'user', 'read')
        resp = client.get(f'/api/v1/users/{admin_user.id}', headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()['data']['id'] == admin_user.id

    def test_get_not_found(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'user', 'read')
        resp = client.get('/api/v1/users/nonexistent-uuid', headers=auth_headers)
        assert resp.status_code == 404


class TestUpdateUser:
    """PATCH /api/v1/users/<id>"""

    def test_update_full_name(self, client, auth_headers, admin_role, db_session, admin_user):
        _grant(db_session, admin_role, 'user', 'update')
        resp = client.patch(f'/api/v1/users/{admin_user.id}', headers=auth_headers, json={
            'full_name': 'Updated Name',
        })
        assert resp.status_code == 200
        assert resp.get_json()['data']['full_name'] == 'Updated Name'

    def test_update_no_fields(self, client, auth_headers, admin_role, db_session, admin_user):
        _grant(db_session, admin_role, 'user', 'update')
        resp = client.patch(f'/api/v1/users/{admin_user.id}', headers=auth_headers, json={})
        assert resp.status_code == 400


class TestDeactivateUser:
    """DELETE /api/v1/users/<id>"""

    def test_deactivate(self, client, auth_headers, admin_role, db_session, admin_user):
        _grant(db_session, admin_role, 'user', 'delete')
        _grant(db_session, admin_role, 'user', 'read')
        resp = client.delete(f'/api/v1/users/{admin_user.id}', headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()['data']['status'] == 'inactive'


class TestAssignRoles:
    """PUT /api/v1/users/<id>/roles"""

    def test_assign_unknown_role(self, client, auth_headers, admin_role, db_session, admin_user):
        _grant(db_session, admin_role, 'user', 'update')
        resp = client.put(f'/api/v1/users/{admin_user.id}/roles', headers=auth_headers, json={
            'roles': ['ghost_role'],
        })
        assert resp.status_code == 400

    def test_assign_roles_not_a_list(self, client, auth_headers, admin_role, db_session, admin_user):
        _grant(db_session, admin_role, 'user', 'update')
        resp = client.put(f'/api/v1/users/{admin_user.id}/roles', headers=auth_headers, json={
            'roles': 'not-a-list',
        })
        assert resp.status_code == 400
