"""RBAC service — permission checking, role assignment, and seeding.

Design:
  - Permissions are stored as (resource, action) pairs in the ``permission`` table.
  - Roles are collections of permissions, optionally scoped to a district.
  - Users have many roles via the ``user_roles`` association table.
  - System roles (``is_system=True``) are global and shared across all tenants.

Usage example::

    from app.services.rbac_service import require_permission

    @app.route('/api/v1/users')
    @require_permission('user', 'read')
    def list_users():
        ...
"""
import logging
from functools import wraps

from flask import g
from flask_jwt_extended import get_jwt, verify_jwt_in_request
from app.utils.responses import error_response

from app.extensions import db
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User, user_roles

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Permission check helpers
# ---------------------------------------------------------------------------

def user_has_permission(user: User, resource: str, action: str) -> bool:
    """Return True if *user* holds a role that grants ``resource:action``.

    Args:
        user:     The authenticated User model instance.
        resource: Permission resource, e.g. ``'user'``.
        action:   Permission action, e.g. ``'read'``.

    Returns:
        bool
    """
    for role in user.roles:
        for perm in role.permissions:
            if perm.resource == resource and perm.action == action:
                return True
    return False


def user_has_any_role(user: User, *role_names: str) -> bool:
    """Return True if *user* holds at least one of the given role names.

    Args:
        user:       The User model instance.
        role_names: One or more role name strings.

    Returns:
        bool
    """
    user_role_names = {r.name for r in user.roles}
    return bool(user_role_names & set(role_names))


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------

def require_permission(resource: str, action: str):
    """View decorator — returns 403 if the JWT holder lacks ``resource:action``.

    The decorator also validates the JWT and loads the user from the DB,
    making it available as ``g.current_user``.

    Usage::

        @bp.route('/users')
        @require_permission('user', 'read')
        def list_users():
            user = g.current_user
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            user_id = claims.get('sub')

            user = User.query.get(user_id)
            if not user or user.status != 'active':
                return error_response('User not found or inactive.', 401, 'UNAUTHORIZED')

            if not user_has_permission(user, resource, action):
                logger.warning(
                    'Permission denied: user=%s resource=%s action=%s',
                    user_id, resource, action,
                )
                return error_response(
                    f"You need the '{resource}:{action}' permission.",
                    403,
                    'FORBIDDEN',
                )

            g.current_user = user
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def require_any_role(*role_names: str):
    """View decorator — returns 403 unless the JWT holder has one of the given roles."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            user_id = claims.get('sub')

            user = User.query.get(user_id)
            if not user or user.status != 'active':
                return error_response('User not found or inactive.', 401, 'UNAUTHORIZED')

            if not user_has_any_role(user, *role_names):
                return error_response(
                    f"One of the following roles is required: {', '.join(role_names)}.",
                    403,
                    'FORBIDDEN',
                )

            g.current_user = user
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Role / permission management
# ---------------------------------------------------------------------------

def get_or_create_permission(resource: str, action: str, description: str = '') -> Permission:
    """Return an existing Permission or create it.

    Args:
        resource:    Resource name.
        action:      Action name.
        description: Optional human-readable description.

    Returns:
        Permission model instance (not yet committed).
    """
    perm = Permission.query.filter_by(resource=resource, action=action).first()
    if not perm:
        perm = Permission(resource=resource, action=action, description=description)
        db.session.add(perm)
    return perm


def assign_role_to_user(user: User, role: Role) -> None:
    """Assign *role* to *user* if not already assigned.

    The caller must commit the session.

    Args:
        user: User model instance.
        role: Role model instance.
    """
    if role not in user.roles:
        user.roles.append(role)


def remove_role_from_user(user: User, role: Role) -> None:
    """Remove *role* from *user* if currently assigned.

    The caller must commit the session.

    Args:
        user: User model instance.
        role: Role model instance.
    """
    if role in user.roles:
        user.roles.remove(role)


# ---------------------------------------------------------------------------
# System permission seed data
# ---------------------------------------------------------------------------

SYSTEM_PERMISSIONS = [
    # Districts
    ('district', 'create',  'Create a new district tenant'),
    ('district', 'read',    'Read district details'),
    ('district', 'update',  'Update district configuration'),
    ('district', 'delete',  'Delete / deactivate a district'),
    # Users
    ('user', 'create',  'Invite or create users'),
    ('user', 'read',    'List and view user profiles'),
    ('user', 'update',  'Update user details and roles'),
    ('user', 'delete',  'Deactivate or delete users'),
    # Roles
    ('role', 'create', 'Create roles'),
    ('role', 'read',   'Read role definitions'),
    ('role', 'update', 'Update role permissions'),
    ('role', 'delete', 'Delete roles'),
    # Departments
    ('department', 'create', 'Create departments'),
    ('department', 'read',   'Read department details'),
    ('department', 'update', 'Update department info'),
    ('department', 'delete', 'Delete departments'),
    # Audit
    ('audit_log',    'read', 'Read audit logs'),
    ('activity_log', 'read', 'Read activity logs'),
    # Social accounts
    ('social_account', 'create', 'Connect social accounts'),
    ('social_account', 'read',   'View social accounts'),
    ('social_account', 'update', 'Update social account credentials'),
    ('social_account', 'delete', 'Disconnect social accounts'),
    # Social posts
    ('social_post', 'create',  'Draft social posts'),
    ('social_post', 'read',    'View social posts'),
    ('social_post', 'update',  'Edit social posts'),
    ('social_post', 'delete',  'Delete social posts'),
    ('social_post', 'publish', 'Publish social posts'),
    # Media library
    ('media', 'create', 'Upload media assets'),
    ('media', 'read',   'View media library'),
    ('media', 'update', 'Update media metadata'),
    ('media', 'delete', 'Delete media assets'),
    # Schedules
    ('schedule', 'create', 'Create post schedules'),
    ('schedule', 'read',   'View schedules'),
    ('schedule', 'update', 'Update / pause schedules'),
    ('schedule', 'delete', 'Delete schedules'),
    # Collected posts (AI Collector)
    ('collected_post', 'create', 'Trigger collection runs'),
    ('collected_post', 'read',   'View collected posts'),
    ('collected_post', 'update', 'Update review status / re-analyse'),
    # Analytics
    ('analytics', 'read', 'View analytics dashboards'),
    # Reports
    ('report', 'create', 'Generate reports'),
    ('report', 'read',   'View and download reports'),
    # Workflow / Approvals
    ('approval',      'create', 'Submit approval requests'),
    ('approval',      'read',   'View approval requests'),
    ('approval',      'update', 'Review / escalate approvals'),
    ('workflow_rule', 'create', 'Create workflow rules'),
    ('workflow_rule', 'read',   'View workflow rules'),
    ('workflow_rule', 'update', 'Update workflow rules'),
    # Notifications
    ('notification', 'create', 'Send notifications'),
    ('notification', 'read',   'View notification history'),
    # Service Requests
    ('service_request', 'create', 'Create service requests'),
    ('service_request', 'read',   'View service requests'),
    ('service_request', 'update', 'Update service requests'),
    ('service_request', 'delete', 'Delete service requests'),
    ('service_request', 'assign', 'Assign service requests to officers'),
    # File Uploads
    ('file', 'create', 'Upload files'),
    ('file', 'read',   'View and download files'),
    ('file', 'delete', 'Delete uploaded files'),
    # Payments
    ('payment', 'create', 'Create payment orders and process payments'),
    ('payment', 'read',   'View payment transactions and plans'),
    # Social Comments
    ('social_comment', 'create',   'Ingest / sync comments from platforms'),
    ('social_comment', 'read',     'View comments and AI analysis'),
    ('social_comment', 'update',   'Re-run AI analysis on comments'),
    ('social_comment', 'reply',    'Send replies to comments via platform'),
    ('social_comment', 'moderate', 'Hide, delete, or mark comments as spam'),
]

SYSTEM_ROLES = {
    'super_admin': [
        # Districts
        ('district', 'create'), ('district', 'read'), ('district', 'update'), ('district', 'delete'),
        # Users / Roles
        ('user', 'create'), ('user', 'read'), ('user', 'update'), ('user', 'delete'),
        ('role', 'create'), ('role', 'read'), ('role', 'update'), ('role', 'delete'),
        # Departments
        ('department', 'create'), ('department', 'read'), ('department', 'update'), ('department', 'delete'),
        # Audit / Activity
        ('audit_log', 'read'), ('activity_log', 'read'),
        # Social media
        ('social_account', 'create'), ('social_account', 'read'), ('social_account', 'update'), ('social_account', 'delete'),
        ('social_post', 'create'), ('social_post', 'read'), ('social_post', 'update'), ('social_post', 'delete'), ('social_post', 'publish'),
        ('media', 'create'), ('media', 'read'), ('media', 'update'), ('media', 'delete'),
        ('schedule', 'create'), ('schedule', 'read'), ('schedule', 'update'), ('schedule', 'delete'),
        ('collected_post', 'create'), ('collected_post', 'read'), ('collected_post', 'update'),
        # Analytics & Reports
        ('analytics', 'read'),
        ('report', 'create'), ('report', 'read'),
        # Workflow / Approvals
        ('approval', 'create'), ('approval', 'read'), ('approval', 'update'),
        ('workflow_rule', 'create'), ('workflow_rule', 'read'), ('workflow_rule', 'update'),
        # Notifications
        ('notification', 'create'), ('notification', 'read'),
        # Service Requests
        ('service_request', 'create'), ('service_request', 'read'),
        ('service_request', 'update'), ('service_request', 'delete'), ('service_request', 'assign'),
        # Files & Payments
        ('file', 'create'), ('file', 'read'), ('file', 'delete'),
        ('payment', 'create'), ('payment', 'read'),
        # Social Comments
        ('social_comment', 'create'), ('social_comment', 'read'),
        ('social_comment', 'update'), ('social_comment', 'reply'),
        ('social_comment', 'moderate'),
    ],
    'district_admin': [
        ('district', 'read'), ('district', 'update'),
        ('user', 'create'), ('user', 'read'), ('user', 'update'), ('user', 'delete'),
        ('role', 'read'),
        ('department', 'create'), ('department', 'read'), ('department', 'update'), ('department', 'delete'),
        ('audit_log', 'read'),
        ('social_account', 'create'), ('social_account', 'read'), ('social_account', 'update'), ('social_account', 'delete'),
        ('social_post', 'create'), ('social_post', 'read'), ('social_post', 'update'), ('social_post', 'delete'), ('social_post', 'publish'),
        ('media', 'create'), ('media', 'read'), ('media', 'update'), ('media', 'delete'),
        ('schedule', 'create'), ('schedule', 'read'), ('schedule', 'update'), ('schedule', 'delete'),
        ('collected_post', 'create'), ('collected_post', 'read'), ('collected_post', 'update'),
        ('analytics', 'read'),
        ('report', 'create'), ('report', 'read'),
        ('approval', 'create'), ('approval', 'read'), ('approval', 'update'),
        ('workflow_rule', 'create'), ('workflow_rule', 'read'), ('workflow_rule', 'update'),
        ('notification', 'create'), ('notification', 'read'),
        ('service_request', 'create'), ('service_request', 'read'),
        ('service_request', 'update'), ('service_request', 'delete'),
        ('service_request', 'assign'),
        ('file', 'create'), ('file', 'read'), ('file', 'delete'),
        ('payment', 'create'), ('payment', 'read'),
    ],
    'department_head': [
        ('user', 'read'),
        ('department', 'read'), ('department', 'update'),
        ('audit_log', 'read'),
    ],
    'officer': [
        ('user', 'read'),
        ('department', 'read'),
    ],
    'field_worker': [
        ('department', 'read'),
    ],
    'citizen': [],
    'auditor': [
        ('district', 'read'), ('user', 'read'), ('department', 'read'),
        ('audit_log', 'read'), ('activity_log', 'read'),
    ],
}


def seed_system_roles_and_permissions() -> None:
    """Create system-level permissions and roles if they do not exist.

    This is idempotent — safe to call on every startup or migration.
    """
    perm_map: dict[tuple, Permission] = {}
    for resource, action, description in SYSTEM_PERMISSIONS:
        perm = get_or_create_permission(resource, action, description)
        perm_map[(resource, action)] = perm

    db.session.flush()

    for role_name, role_perms in SYSTEM_ROLES.items():
        role = Role.query.filter_by(district_id=None, name=role_name, is_system=True).first()
        if not role:
            role = Role(
                district_id=None,
                name=role_name,
                description=f'System role: {role_name}',
                is_system=True,
            )
            db.session.add(role)
            db.session.flush()

        existing_perm_ids = {p.id for p in role.permissions}
        for resource, action in role_perms:
            perm = perm_map.get((resource, action))
            if perm and perm.id not in existing_perm_ids:
                role.permissions.append(perm)

    db.session.commit()
    logger.info('System roles and permissions seeded.')
