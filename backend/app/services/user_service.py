"""User management service.

Handles CRUD operations for user accounts within a district tenant.
All write operations emit audit log entries.
"""
import logging

from app.extensions import db
from app.models.user import User
from app.models.role import Role
from app.services.auth_service import set_password
from app.services.audit_service import write_audit_log
from app.utils.db import paginate_query
from app.utils.validators import is_valid_email

logger = logging.getLogger(__name__)


def get_users(district_id: str, page: int = 1, per_page: int = 20,
              status: str | None = None, search: str | None = None):
    """Return a paginated list of users in the given district.

    Args:
        district_id: Tenant scope.
        page:        Page number (1-based).
        per_page:    Page size (max 100).
        status:      Optional status filter (``'active'``, ``'inactive'``).
        search:      Optional substring search against email / full_name.

    Returns:
        SQLAlchemy Pagination object.
    """
    query = User.query.filter_by(district_id=district_id)

    if status:
        query = query.filter(User.status == status)

    if search:
        like = f'%{search}%'
        query = query.filter(
            db.or_(
                User.email.ilike(like),
                User.full_name.ilike(like),
            )
        )

    query = query.order_by(User.created_at.desc())
    return paginate_query(query, page=page, per_page=per_page)


def get_user_by_id(district_id: str, user_id: str) -> User:
    """Fetch a single user, enforcing tenant scope.

    Args:
        district_id: Tenant scope.
        user_id:     User UUID.

    Returns:
        User model instance.

    Raises:
        ValueError: If the user is not found in this district.
    """
    user = User.query.filter_by(id=user_id, district_id=district_id).first()
    if not user:
        raise ValueError('User not found.')
    return user


def create_user(
    district_id: str,
    email: str,
    full_name: str,
    password: str,
    actor_id: str | None = None,
    phone: str | None = None,
    role_names: list[str] | None = None,
) -> User:
    """Create a new user in the given district.

    Args:
        district_id: Tenant scope.
        email:       Must be unique within the district.
        full_name:   Display name.
        password:    Plain-text password (will be hashed).
        actor_id:    UUID of the admin performing the action.
        phone:       Optional phone number.
        role_names:  List of role names to assign (must exist in district or as system roles).

    Returns:
        The newly created User model instance.

    Raises:
        ValueError: On validation failure or duplicate email.
    """
    email = email.lower().strip()

    if not is_valid_email(email):
        raise ValueError(f"'{email}' is not a valid email address.")

    existing = User.query.filter_by(district_id=district_id, email=email).first()
    if existing:
        raise ValueError('A user with this email already exists in this district.')

    user = User(
        district_id=district_id,
        email=email,
        full_name=full_name.strip(),
        phone=phone,
        auth_provider='local',
        status='active',
    )
    set_password(user, password)
    db.session.add(user)
    db.session.flush()

    if role_names:
        _assign_roles(user, district_id, role_names)

    write_audit_log(
        district_id=district_id,
        actor_id=actor_id,
        action='user.created',
        resource_type='user',
        resource_id=user.id,
        after_state=user.to_dict(),
    )
    db.session.commit()
    logger.info('User created: %s (district=%s)', user.id, district_id)
    return user


def update_user(
    district_id: str,
    user_id: str,
    actor_id: str | None = None,
    **fields,
) -> User:
    """Update allowed fields on a user.

    Allowed fields: ``full_name``, ``phone``, ``status``, ``email_verified``,
    ``phone_verified``.  Pass only the fields you want to change.

    Args:
        district_id: Tenant scope.
        user_id:     User UUID.
        actor_id:    UUID of the admin performing the action.
        **fields:    Key/value pairs of fields to update.

    Returns:
        Updated User model instance.

    Raises:
        ValueError: If user not found or an invalid field is provided.
    """
    user = get_user_by_id(district_id, user_id)
    before = user.to_dict()

    allowed = {'full_name', 'phone', 'status', 'email_verified', 'phone_verified'}
    for key, value in fields.items():
        if key not in allowed:
            raise ValueError(f"Field '{key}' cannot be updated via this method.")
        setattr(user, key, value)

    write_audit_log(
        district_id=district_id,
        actor_id=actor_id,
        action='user.updated',
        resource_type='user',
        resource_id=user.id,
        before_state=before,
        after_state=user.to_dict(),
    )
    db.session.commit()
    return user


def deactivate_user(district_id: str, user_id: str, actor_id: str | None = None) -> User:
    """Set a user's status to ``'inactive'``.

    Args:
        district_id: Tenant scope.
        user_id:     User UUID.
        actor_id:    UUID of the admin performing the action.

    Returns:
        Updated User model instance.
    """
    return update_user(district_id, user_id, actor_id=actor_id, status='inactive')


def assign_roles_to_user(
    district_id: str,
    user_id: str,
    role_names: list[str],
    actor_id: str | None = None,
) -> User:
    """Replace the user's current roles with the given list.

    Args:
        district_id: Tenant scope.
        user_id:     User UUID.
        role_names:  Full replacement list of role name strings.
        actor_id:    UUID of the admin performing the action.

    Returns:
        Updated User model instance.

    Raises:
        ValueError: If any role name does not exist.
    """
    user = get_user_by_id(district_id, user_id)
    before = user.to_dict()

    user.roles.clear()
    _assign_roles(user, district_id, role_names)

    write_audit_log(
        district_id=district_id,
        actor_id=actor_id,
        action='user.roles_updated',
        resource_type='user',
        resource_id=user.id,
        before_state=before,
        after_state=user.to_dict(),
    )
    db.session.commit()
    return user


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _assign_roles(user: User, district_id: str, role_names: list[str]) -> None:
    """Look up roles by name and append them to *user.roles*.

    Searches district-specific roles first, then system (global) roles.

    Raises:
        ValueError: If a named role does not exist.
    """
    for name in role_names:
        role = (
            Role.query.filter_by(district_id=district_id, name=name).first()
            or Role.query.filter_by(district_id=None, name=name, is_system=True).first()
        )
        if not role:
            raise ValueError(f"Role '{name}' does not exist.")
        if role not in user.roles:
            user.roles.append(role)
