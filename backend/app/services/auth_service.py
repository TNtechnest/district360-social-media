"""Authentication service — login, token refresh, password management.

Handles:
  - Email/password login
  - JWT access + refresh token issuance
  - Token refresh
  - Logout (token blocklist via JWTManager callbacks)
  - Password hashing / verification
"""
import logging
from datetime import datetime, timezone

from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    get_jwt,
)

from app.extensions import db, bcrypt
from app.models.user import User
from app.services.audit_service import write_audit_log, write_activity_log

logger = logging.getLogger(__name__)

# Revoked token blocklist.  Uses Redis when available, otherwise falls back
# to an in-memory set (suitable for development / single-worker only).
from app.services.infrastructure.redis_service import block_token, is_token_blocked
_USE_REDIS_BLOCKLIST = True
_BLOCKLIST: set[str] = set()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def login(district_id: str, email: str, password: str) -> dict:
    """Validate credentials and return JWT token pair.

    Args:
        district_id: The tenant scope — only users in this district are considered.
        email:       The user's e-mail address.
        password:    The plain-text password.

    Returns:
        Dict with ``access_token``, ``refresh_token``, and ``user`` keys.

    Raises:
        ValueError: If credentials are invalid or account is not active.
    """
    user = User.query.filter_by(district_id=district_id, email=email.lower().strip()).first()

    if not user or not user.password_hash:
        raise ValueError('Invalid email or password.')

    if not bcrypt.check_password_hash(user.password_hash, password):
        raise ValueError('Invalid email or password.')

    if user.status != 'active':
        raise ValueError('Your account is not active. Please contact support.')

    # Stamp last login
    user.last_login_at = datetime.now(timezone.utc).isoformat()
    db.session.flush()

    access_token  = _make_access_token(user)
    refresh_token = _make_refresh_token(user)

    write_activity_log(
        district_id=district_id,
        user_id=user.id,
        activity_type='login',
        description=f'User {user.email} logged in.',
    )
    db.session.commit()

    logger.info('User %s logged in (district=%s)', user.id, district_id)
    return {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user': user.to_dict(),
    }


def refresh_tokens(current_user_id: str) -> dict:
    """Issue a new access token for a valid refresh token identity.

    Args:
        current_user_id: The ``sub`` claim from the verified refresh JWT.

    Returns:
        Dict with a new ``access_token``.

    Raises:
        ValueError: If the user cannot be found or is not active.
    """
    user = User.query.get(current_user_id)
    if not user:
        raise ValueError('User not found.')
    if user.status != 'active':
        raise ValueError('Account is not active.')

    access_token = _make_access_token(user)
    logger.info('Access token refreshed for user %s', current_user_id)
    return {'access_token': access_token}


def logout(jti: str) -> None:
    """Add a token JTI to the blocklist (logout / revoke).

    Uses Redis when available, falls back to in-memory set.

    Args:
        jti: The JWT ID claim of the token to revoke.
    """
    if _USE_REDIS_BLOCKLIST and is_token_blocked.__module__:
        try:
            block_token(jti)
        except Exception:
            _BLOCKLIST.add(jti)
    else:
        _BLOCKLIST.add(jti)
    logger.info('Token %s revoked (blocklisted).', jti)


def is_token_revoked(jwt_header: dict, jwt_payload: dict) -> bool:  # noqa: ARG001
    """Callback used by Flask-JWT-Extended to check if a token is revoked.

    Uses Redis when available, falls back to in-memory set.
    Registered via ``@jwt.token_in_blocklist_loader``.
    """
    jti = jwt_payload.get('jti')
    if not jti:
        return False
    if _USE_REDIS_BLOCKLIST:
        try:
            return is_token_blocked(jti)
        except Exception:
            pass
    return jti in _BLOCKLIST


def set_password(user: User, plain_password: str) -> None:
    """Hash and store a new password on *user*.

    Args:
        user:           The User model instance to update.
        plain_password: The new plain-text password.
    """
    _validate_password_strength(plain_password)
    user.password_hash = bcrypt.generate_password_hash(plain_password).decode('utf-8')


def change_password(user: User, old_password: str, new_password: str) -> None:
    """Verify *old_password* then replace it with *new_password*.

    Args:
        user:         The User model instance.
        old_password: Current plain-text password.
        new_password: New plain-text password.

    Raises:
        ValueError: If the old password is wrong or the new one is too weak.
    """
    if not bcrypt.check_password_hash(user.password_hash, old_password):
        raise ValueError('Current password is incorrect.')
    set_password(user, new_password)

    write_audit_log(
        district_id=user.district_id,
        actor_id=user.id,
        action='user.password_changed',
        resource_type='user',
        resource_id=user.id,
    )
    db.session.commit()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _make_access_token(user: User) -> str:
    """Build a JWT access token with role / district claims."""
    additional_claims = {
        'district_id': user.district_id,
        'roles': [r.name for r in user.roles],
        'email': user.email,
    }
    return create_access_token(identity=user.id, additional_claims=additional_claims)


def _make_refresh_token(user: User) -> str:
    """Build a JWT refresh token."""
    return create_refresh_token(identity=user.id)


def _validate_password_strength(password: str) -> None:
    """Enforce minimum password policy.

    Rules:
        - At least 8 characters long.
        - Contains at least one digit.
        - Contains at least one uppercase letter.

    Raises:
        ValueError: If the password does not meet the policy.
    """
    if len(password) < 8:
        raise ValueError('Password must be at least 8 characters long.')
    if not any(c.isdigit() for c in password):
        raise ValueError('Password must contain at least one digit.')
    if not any(c.isupper() for c in password):
        raise ValueError('Password must contain at least one uppercase letter.')
