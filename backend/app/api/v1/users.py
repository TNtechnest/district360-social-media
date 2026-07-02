"""User management endpoints.

All routes are tenant-scoped — users belong to a specific district.
The ``district_id`` is extracted from the JWT claims of the caller.

Routes
------
GET    /api/v1/users               — list users in caller's district
POST   /api/v1/users               — create a user
GET    /api/v1/users/<id>          — get user detail
PATCH  /api/v1/users/<id>          — update user fields
DELETE /api/v1/users/<id>          — deactivate user
PUT    /api/v1/users/<id>/roles    — replace user roles
GET    /api/v1/users/me            — get authenticated user profile
"""
import logging

from flask import Blueprint, request, g
from flask_jwt_extended import jwt_required, get_jwt

from app.services import user_service
from app.services.rbac_service import require_permission
from app.utils.responses import success_response, error_response, paginated_response
from app.utils.validators import validate_pagination_params

logger = logging.getLogger(__name__)
users_bp = Blueprint('users', __name__, url_prefix='/users')


def _caller_district_id() -> str:
    """Extract district_id from the current JWT claims."""
    return get_jwt().get('district_id', '')


@users_bp.route('/me', methods=['GET'])
@jwt_required()
def get_me():
    """Return the profile of the currently authenticated user."""
    from app.models.user import User
    user_id = get_jwt().get('sub')
    user = User.query.get(user_id)
    if not user:
        return error_response('User not found.', 404, 'NOT_FOUND')
    return success_response(data=user.to_dict())


@users_bp.route('', methods=['GET'])
@require_permission('user', 'read')
def list_users():
    """List users in the caller's district (paginated).

    Query params: ``page``, ``per_page``, ``status``, ``search``.
    """
    district_id = _caller_district_id()
    page, per_page = validate_pagination_params(
        request.args.get('page', 1),
        request.args.get('per_page', 20),
    )
    pagination = user_service.get_users(
        district_id=district_id,
        page=page,
        per_page=per_page,
        status=request.args.get('status'),
        search=request.args.get('search'),
    )
    return paginated_response(
        [u.to_dict() for u in pagination.items],
        pagination,
    )


@users_bp.route('', methods=['POST'])
@require_permission('user', 'create')
def create_user():
    """Create a new user in the caller's district.

    Request body (JSON)::

        {
          "email": "officer@example.com",
          "full_name": "Jane Doe",
          "password": "Secret1!",
          "phone": "+911234567890",
          "roles": ["officer"]
        }
    """
    district_id = _caller_district_id()
    data = request.get_json(silent=True) or {}

    email     = data.get('email', '').strip()
    full_name = data.get('full_name', '').strip()
    password  = data.get('password', '')
    phone     = data.get('phone')
    roles     = data.get('roles', [])

    if not email:
        return error_response('email is required.', 400, 'VALIDATION_ERROR')
    if not full_name:
        return error_response('full_name is required.', 400, 'VALIDATION_ERROR')
    if not password:
        return error_response('password is required.', 400, 'VALIDATION_ERROR')

    try:
        user = user_service.create_user(
            district_id=district_id,
            email=email,
            full_name=full_name,
            password=password,
            phone=phone,
            role_names=roles,
            actor_id=g.current_user.id,
        )
        return success_response(data=user.to_dict(), status_code=201, message='User created.')
    except ValueError as exc:
        return error_response(str(exc), 400, 'VALIDATION_ERROR')


@users_bp.route('/<user_id>', methods=['GET'])
@require_permission('user', 'read')
def get_user(user_id):
    """Get user details by ID (must be in caller's district)."""
    district_id = _caller_district_id()
    try:
        user = user_service.get_user_by_id(district_id, user_id)
        return success_response(data=user.to_dict())
    except ValueError as exc:
        return error_response(str(exc), 404, 'NOT_FOUND')


@users_bp.route('/<user_id>', methods=['PATCH'])
@require_permission('user', 'update')
def update_user(user_id):
    """Update user fields (full_name, phone, status, email_verified, phone_verified).

    Request body (JSON): supply only the fields you want to change.
    """
    district_id = _caller_district_id()
    data = request.get_json(silent=True) or {}
    allowed_keys = {'full_name', 'phone', 'status', 'email_verified', 'phone_verified'}
    updates = {k: v for k, v in data.items() if k in allowed_keys}

    if not updates:
        return error_response('No updatable fields provided.', 400, 'VALIDATION_ERROR')

    try:
        user = user_service.update_user(
            district_id, user_id, actor_id=g.current_user.id, **updates
        )
        return success_response(data=user.to_dict(), message='User updated.')
    except ValueError as exc:
        return error_response(str(exc), 400, 'VALIDATION_ERROR')


@users_bp.route('/<user_id>', methods=['DELETE'])
@require_permission('user', 'delete')
def deactivate_user(user_id):
    """Deactivate a user (soft delete — sets status to inactive)."""
    district_id = _caller_district_id()
    try:
        user = user_service.deactivate_user(district_id, user_id, actor_id=g.current_user.id)
        return success_response(data=user.to_dict(), message='User deactivated.')
    except ValueError as exc:
        return error_response(str(exc), 404, 'NOT_FOUND')


@users_bp.route('/<user_id>/roles', methods=['PUT'])
@require_permission('user', 'update')
def update_user_roles(user_id):
    """Replace the user's roles with the provided list.

    Request body (JSON)::

        { "roles": ["officer", "field_worker"] }
    """
    district_id = _caller_district_id()
    data = request.get_json(silent=True) or {}
    roles = data.get('roles', [])

    if not isinstance(roles, list):
        return error_response('roles must be a list of role name strings.', 400, 'VALIDATION_ERROR')

    try:
        user = user_service.assign_roles_to_user(
            district_id, user_id, roles, actor_id=g.current_user.id
        )
        return success_response(data=user.to_dict(), message='Roles updated.')
    except ValueError as exc:
        return error_response(str(exc), 400, 'VALIDATION_ERROR')
