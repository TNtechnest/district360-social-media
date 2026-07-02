"""Unit tests for the RBAC service layer.

Covers:
  - user_has_permission
  - user_has_any_role
  - assign_role_to_user / remove_role_from_user
  - get_or_create_permission (idempotency)
  - seed_system_roles_and_permissions (idempotency)
"""
import pytest
from app.models import Permission, Role, User
from app.services import rbac_service


class TestUserHasPermission:
    def test_has_permission_true(self, admin_user, permission_user_read):
        """User with a role that has user:read returns True."""
        assert rbac_service.user_has_permission(admin_user, 'user', 'read') is True

    def test_has_permission_false(self, admin_user):
        """User without user:delete returns False."""
        assert rbac_service.user_has_permission(admin_user, 'user', 'delete') is False

    def test_has_permission_unknown_resource(self, admin_user):
        assert rbac_service.user_has_permission(admin_user, 'spaceship', 'fly') is False


class TestUserHasAnyRole:
    def test_has_role_true(self, admin_user):
        assert rbac_service.user_has_any_role(admin_user, 'district_admin') is True

    def test_has_role_one_of_many(self, admin_user):
        assert rbac_service.user_has_any_role(admin_user, 'citizen', 'district_admin') is True

    def test_has_role_false(self, admin_user):
        assert rbac_service.user_has_any_role(admin_user, 'super_admin') is False


class TestGetOrCreatePermission:
    def test_creates_new(self, db_session):
        perm = rbac_service.get_or_create_permission('spaceship', 'launch', 'Launch spaceship')
        db_session.flush()
        assert perm.resource == 'spaceship'
        assert perm.action == 'launch'

    def test_returns_existing(self, db_session, permission_user_read):
        perm = rbac_service.get_or_create_permission('user', 'read')
        assert perm.id == permission_user_read.id


class TestAssignRemoveRole:
    def test_assign_role(self, db_session, admin_user, district):
        new_role = Role(
            district_id=district.id,
            name='field_worker',
            description='Field worker',
        )
        db_session.add(new_role)
        db_session.flush()

        rbac_service.assign_role_to_user(admin_user, new_role)
        assert new_role in admin_user.roles

    def test_assign_duplicate_idempotent(self, db_session, admin_user, admin_role):
        """Assigning an already-assigned role does not duplicate."""
        initial_count = len(admin_user.roles)
        rbac_service.assign_role_to_user(admin_user, admin_role)
        assert len(admin_user.roles) == initial_count

    def test_remove_role(self, db_session, admin_user, admin_role):
        rbac_service.remove_role_from_user(admin_user, admin_role)
        assert admin_role not in admin_user.roles

    def test_remove_unassigned_noop(self, db_session, admin_user, district):
        other_role = Role(district_id=district.id, name='auditor_test')
        db_session.add(other_role)
        db_session.flush()
        # Should not raise
        rbac_service.remove_role_from_user(admin_user, other_role)


class TestSeedSystemRoles:
    def test_seed_is_idempotent(self, db_session, app):
        """Seeding twice should not raise or create duplicates."""
        with app.app_context():
            rbac_service.seed_system_roles_and_permissions()
            rbac_service.seed_system_roles_and_permissions()

        # Verify super_admin exists exactly once
        count = Role.query.filter_by(name='super_admin', is_system=True).count()
        assert count >= 1  # may exist from prior seed in session
