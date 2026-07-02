"""Unit tests for authentication endpoints and service.

Covers:
  - Successful login
  - Invalid credentials
  - Inactive account
  - Token refresh
  - Logout / token revocation
  - Change password
  - Password strength validation
"""
import pytest


class TestLogin:
    """POST /api/v1/auth/login"""

    def test_login_success(self, client, admin_user, district):
        """Valid credentials return 200 with access and refresh tokens."""
        resp = client.post('/api/v1/auth/login', json={
            'district_id': district.id,
            'email': 'admin@test.example',
            'password': 'Admin1234',
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert 'access_token'  in data['data']
        assert 'refresh_token' in data['data']
        assert data['data']['user']['email'] == 'admin@test.example'

    def test_login_wrong_password(self, client, admin_user, district):
        """Wrong password returns 401."""
        resp = client.post('/api/v1/auth/login', json={
            'district_id': district.id,
            'email': 'admin@test.example',
            'password': 'WrongPassword1',
        })
        assert resp.status_code == 401
        assert resp.get_json()['success'] is False

    def test_login_unknown_email(self, client, district):
        """Unknown email returns 401."""
        resp = client.post('/api/v1/auth/login', json={
            'district_id': district.id,
            'email': 'nobody@example.com',
            'password': 'Password1',
        })
        assert resp.status_code == 401

    def test_login_missing_district_id(self, client):
        """Missing district_id returns 400."""
        resp = client.post('/api/v1/auth/login', json={
            'email': 'a@b.com',
            'password': 'Abc12345',
        })
        assert resp.status_code == 400

    def test_login_inactive_user(self, client, db_session, admin_user, district):
        """Inactive account is rejected with 401."""
        admin_user.status = 'inactive'
        db_session.flush()
        resp = client.post('/api/v1/auth/login', json={
            'district_id': district.id,
            'email': 'admin@test.example',
            'password': 'Admin1234',
        })
        assert resp.status_code == 401


class TestRefresh:
    """POST /api/v1/auth/refresh"""

    def _get_refresh_token(self, client, admin_user, district):
        resp = client.post('/api/v1/auth/login', json={
            'district_id': district.id,
            'email': 'admin@test.example',
            'password': 'Admin1234',
        })
        return resp.get_json()['data']['refresh_token']

    def test_refresh_success(self, client, admin_user, district):
        """Valid refresh token returns a new access token."""
        refresh_token = self._get_refresh_token(client, admin_user, district)
        resp = client.post('/api/v1/auth/refresh', headers={
            'Authorization': f'Bearer {refresh_token}',
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert 'access_token' in data['data']

    def test_refresh_with_access_token_fails(self, client, auth_headers):
        """Using an access token on the refresh endpoint returns 422."""
        resp = client.post('/api/v1/auth/refresh', headers=auth_headers)
        assert resp.status_code == 422


class TestLogout:
    """POST /api/v1/auth/logout"""

    def test_logout_success(self, client, auth_headers):
        """Logout revokes the token; subsequent requests get 401."""
        resp = client.post('/api/v1/auth/logout', headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

        # Revoked token should now be rejected
        resp2 = client.post('/api/v1/auth/logout', headers=auth_headers)
        assert resp2.status_code == 401

    def test_logout_without_token(self, client):
        """Missing token returns 401."""
        resp = client.post('/api/v1/auth/logout')
        assert resp.status_code == 401


class TestChangePassword:
    """POST /api/v1/auth/change-password"""

    def test_change_password_success(self, client, auth_headers, admin_user, district, db_session):
        """Correct old password + strong new password returns 200."""
        resp = client.post('/api/v1/auth/change-password', headers=auth_headers, json={
            'old_password': 'Admin1234',
            'new_password': 'NewAdmin5678',
        })
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_change_password_wrong_old(self, client, auth_headers):
        """Wrong old password returns 400."""
        resp = client.post('/api/v1/auth/change-password', headers=auth_headers, json={
            'old_password': 'WrongOld1',
            'new_password': 'NewAdmin5678',
        })
        assert resp.status_code == 400

    def test_change_password_weak_new(self, client, auth_headers):
        """Weak new password returns 400."""
        resp = client.post('/api/v1/auth/change-password', headers=auth_headers, json={
            'old_password': 'Admin1234',
            'new_password': 'weak',
        })
        assert resp.status_code == 400
