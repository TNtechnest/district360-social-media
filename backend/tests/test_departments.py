"""Unit tests for department management endpoints and service.

Covers:
  - List departments
  - Create department (validation, duplicate code)
  - Get department by ID
  - Update department
  - Deactivate department
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


@pytest.fixture
def department(db_session, district):
    """A minimal active department in the test district."""
    from app.models import Department
    dept = Department(
        district_id=district.id,
        name='Water & Sanitation',
        code='WATER',
        description='Water dept',
        wards=['north'],
        status='active',
    )
    db_session.add(dept)
    db_session.flush()
    return dept


class TestListDepartments:
    """GET /api/v1/departments"""

    def test_list_requires_auth(self, client):
        resp = client.get('/api/v1/departments')
        assert resp.status_code == 401

    def test_list_success(self, client, auth_headers, admin_role, db_session, department):
        _grant(db_session, admin_role, 'department', 'read')
        resp = client.get('/api/v1/departments', headers=auth_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert body['meta']['total'] >= 1


class TestCreateDepartment:
    """POST /api/v1/departments"""

    def test_create_success(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'department', 'create')
        _grant(db_session, admin_role, 'department', 'read')
        resp = client.post('/api/v1/departments', headers=auth_headers, json={
            'name': 'Roads & Infrastructure',
            'code': 'ROADS',
            'description': 'Road maintenance',
            'wards': ['east-ward'],
        })
        assert resp.status_code == 201
        body = resp.get_json()
        assert body['data']['code'] == 'ROADS'

    def test_create_duplicate_code(self, client, auth_headers, admin_role, db_session, department):
        _grant(db_session, admin_role, 'department', 'create')
        resp = client.post('/api/v1/departments', headers=auth_headers, json={
            'name': 'Another Water',
            'code': 'WATER',  # duplicate
        })
        assert resp.status_code == 400

    def test_create_missing_name(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'department', 'create')
        resp = client.post('/api/v1/departments', headers=auth_headers, json={'code': 'NOPE'})
        assert resp.status_code == 400

    def test_create_missing_code(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'department', 'create')
        resp = client.post('/api/v1/departments', headers=auth_headers, json={'name': 'Roads'})
        assert resp.status_code == 400


class TestGetDepartment:
    """GET /api/v1/departments/<id>"""

    def test_get_success(self, client, auth_headers, admin_role, db_session, department):
        _grant(db_session, admin_role, 'department', 'read')
        resp = client.get(f'/api/v1/departments/{department.id}', headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()['data']['id'] == department.id

    def test_get_not_found(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'department', 'read')
        resp = client.get('/api/v1/departments/nonexistent', headers=auth_headers)
        assert resp.status_code == 404


class TestUpdateDepartment:
    """PATCH /api/v1/departments/<id>"""

    def test_update_name(self, client, auth_headers, admin_role, db_session, department):
        _grant(db_session, admin_role, 'department', 'update')
        resp = client.patch(f'/api/v1/departments/{department.id}', headers=auth_headers, json={
            'name': 'Updated Water Services',
        })
        assert resp.status_code == 200
        assert resp.get_json()['data']['name'] == 'Updated Water Services'

    def test_update_empty_body(self, client, auth_headers, admin_role, db_session, department):
        _grant(db_session, admin_role, 'department', 'update')
        resp = client.patch(f'/api/v1/departments/{department.id}', headers=auth_headers, json={})
        assert resp.status_code == 400


class TestDeactivateDepartment:
    """DELETE /api/v1/departments/<id>"""

    def test_deactivate(self, client, auth_headers, admin_role, db_session, department):
        _grant(db_session, admin_role, 'department', 'delete')
        _grant(db_session, admin_role, 'department', 'read')
        resp = client.delete(f'/api/v1/departments/{department.id}', headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()['data']['status'] == 'inactive'
