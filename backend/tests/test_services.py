"""Service-layer unit tests (no HTTP layer).

Tests the service functions directly with the DB session, bypassing Flask routing.
Covers: auth_service, user_service, district_service, department_service, audit_service.
"""
import pytest
from app.services import auth_service, user_service, district_service, department_service
from app.services.audit_service import write_audit_log, write_activity_log
from app.models import AuditLog, ActivityLog, User, District


# ---------------------------------------------------------------------------
# auth_service
# ---------------------------------------------------------------------------

class TestAuthService:
    def test_set_password_and_login(self, db_session, admin_user, district):
        """set_password hashes correctly; login succeeds."""
        result = auth_service.login(district.id, 'admin@test.example', 'Admin1234')
        assert 'access_token' in result
        assert result['user']['email'] == 'admin@test.example'

    def test_login_invalid_password(self, db_session, admin_user, district):
        with pytest.raises(ValueError, match='Invalid email or password'):
            auth_service.login(district.id, 'admin@test.example', 'WRONG')

    def test_validate_password_too_short(self):
        with pytest.raises(ValueError, match='8 characters'):
            auth_service._validate_password_strength('Ab1')

    def test_validate_password_no_digit(self):
        with pytest.raises(ValueError, match='digit'):
            auth_service._validate_password_strength('NoDigitHere')

    def test_validate_password_no_uppercase(self):
        with pytest.raises(ValueError, match='uppercase'):
            auth_service._validate_password_strength('alllowecase1')

    def test_change_password_success(self, db_session, admin_user):
        auth_service.change_password(admin_user, 'Admin1234', 'NewPass5678')
        # Should now be able to verify with the new hash
        from app.extensions import bcrypt
        assert bcrypt.check_password_hash(admin_user.password_hash, 'NewPass5678')

    def test_change_password_wrong_old(self, db_session, admin_user):
        with pytest.raises(ValueError, match='Current password'):
            auth_service.change_password(admin_user, 'WrongOld1', 'NewPass5678')

    def test_token_blocklist(self):
        auth_service.logout('test-jti-123')
        assert auth_service.is_token_revoked({}, {'jti': 'test-jti-123'}) is True
        assert auth_service.is_token_revoked({}, {'jti': 'not-blocked'}) is False


# ---------------------------------------------------------------------------
# user_service
# ---------------------------------------------------------------------------

class TestUserService:
    def test_create_user(self, db_session, district):
        user = user_service.create_user(
            district_id=district.id,
            email='new@example.com',
            full_name='New Person',
            password='Pass1234A',
        )
        assert user.id is not None
        assert user.email == 'new@example.com'
        assert user.status == 'active'

    def test_create_user_duplicate_email(self, db_session, district, admin_user):
        with pytest.raises(ValueError, match='already exists'):
            user_service.create_user(
                district_id=district.id,
                email='admin@test.example',
                full_name='Dupe',
                password='Pass1234A',
            )

    def test_get_user_by_id(self, db_session, district, admin_user):
        found = user_service.get_user_by_id(district.id, admin_user.id)
        assert found.id == admin_user.id

    def test_get_user_wrong_district(self, db_session, admin_user):
        with pytest.raises(ValueError, match='not found'):
            user_service.get_user_by_id('wrong-district-id', admin_user.id)

    def test_update_user(self, db_session, district, admin_user):
        updated = user_service.update_user(district.id, admin_user.id, full_name='Changed Name')
        assert updated.full_name == 'Changed Name'

    def test_deactivate_user(self, db_session, district, admin_user):
        deactivated = user_service.deactivate_user(district.id, admin_user.id)
        assert deactivated.status == 'inactive'

    def test_get_users_paginated(self, db_session, district, admin_user):
        pagination = user_service.get_users(district.id)
        assert pagination.total >= 1


# ---------------------------------------------------------------------------
# district_service
# ---------------------------------------------------------------------------

class TestDistrictService:
    def test_create_district(self, db_session):
        d = district_service.create_district(name='New City', slug='new-city-svc')
        assert d.slug == 'new-city-svc'
        assert d.status == 'active'

    def test_create_district_duplicate_slug(self, db_session, district):
        with pytest.raises(ValueError, match='already exists'):
            district_service.create_district(name='Dup', slug=district.slug)

    def test_create_district_invalid_slug(self, db_session):
        with pytest.raises(ValueError, match='Slug must'):
            district_service.create_district(name='Bad', slug='INVALID SLUG!')

    def test_get_by_id(self, db_session, district):
        found = district_service.get_district_by_id(district.id)
        assert found.id == district.id

    def test_get_by_slug(self, db_session, district):
        found = district_service.get_district_by_slug(district.slug)
        assert found.slug == district.slug

    def test_update_district(self, db_session, district):
        updated = district_service.update_district(district.id, name='Renamed')
        assert updated.name == 'Renamed'

    def test_deactivate_district(self, db_session, district):
        d = district_service.deactivate_district(district.id)
        assert d.status == 'inactive'


# ---------------------------------------------------------------------------
# department_service
# ---------------------------------------------------------------------------

class TestDepartmentService:
    def test_create_department(self, db_session, district):
        dept = department_service.create_department(
            district_id=district.id,
            name='Health',
            code='HEALTH',
        )
        assert dept.code == 'HEALTH'
        assert dept.status == 'active'

    def test_create_department_duplicate_code(self, db_session, district):
        department_service.create_department(district.id, 'A', 'DUPCODE')
        with pytest.raises(ValueError, match='already exists'):
            department_service.create_department(district.id, 'B', 'DUPCODE')

    def test_update_department(self, db_session, district):
        dept = department_service.create_department(district.id, 'Roads', 'ROADS2')
        updated = department_service.update_department(
            district.id, dept.id, name='Roads & Bridges'
        )
        assert updated.name == 'Roads & Bridges'

    def test_deactivate_department(self, db_session, district):
        dept = department_service.create_department(district.id, 'Sanitation', 'SAN')
        result = department_service.deactivate_department(district.id, dept.id)
        assert result.status == 'inactive'


# ---------------------------------------------------------------------------
# audit_service
# ---------------------------------------------------------------------------

class TestAuditService:
    def test_write_audit_log(self, db_session, district, admin_user):
        write_audit_log(
            district_id=district.id,
            actor_id=admin_user.id,
            action='test.action',
            resource_type='test',
            resource_id='some-id',
            after_state={'key': 'value'},
        )
        db_session.flush()
        entry = AuditLog.query.filter_by(
            district_id=district.id, action='test.action'
        ).first()
        assert entry is not None
        assert entry.after_state == {'key': 'value'}

    def test_write_activity_log(self, db_session, district, admin_user):
        write_activity_log(
            district_id=district.id,
            user_id=admin_user.id,
            activity_type='test.activity',
            description='Testing',
            metadata={'x': 1},
        )
        db_session.flush()
        entry = ActivityLog.query.filter_by(
            district_id=district.id, activity_type='test.activity'
        ).first()
        assert entry is not None
        assert entry.metadata == {'x': 1}
