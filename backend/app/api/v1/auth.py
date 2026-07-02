"""Authentication endpoints.

Routes
------
POST /api/v1/auth/login        — email + password → token pair
POST /api/v1/auth/refresh      — refresh token   → new access token
POST /api/v1/auth/logout       — revoke current token
POST /api/v1/auth/change-password — change own password
"""
import logging

from flask import Blueprint, request, g
from flask_jwt_extended import (
    jwt_required,
    get_jwt_identity,
    get_jwt,
    verify_jwt_in_request,
)

from app.services import auth_service
from app.utils.responses import success_response, error_response

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/login', methods=['POST'])
def login():
    """Authenticate a user and return a JWT token pair.

    Request body (JSON)::

        {
          "district_id": "<uuid>",
          "email": "user@example.com",
          "password": "Secret1!"
        }

    Returns 200 with ``{ access_token, refresh_token, user }`` on success.
    Returns 400 if the body is missing required fields.
    Returns 401 if credentials are invalid.
    """
    data = request.get_json(silent=True) or {}

    district_id = data.get('district_id', '').strip()
    email       = data.get('email', '').strip()
    password    = data.get('password', '')

    if not district_id:
        return error_response('district_id is required.', 400, 'VALIDATION_ERROR')
    if not email:
        return error_response('email is required.', 400, 'VALIDATION_ERROR')
    if not password:
        return error_response('password is required.', 400, 'VALIDATION_ERROR')

    try:
        result = auth_service.login(district_id, email, password)
        return success_response(data=result, message='Login successful.')
    except ValueError as exc:
        return error_response(str(exc), 401, 'AUTHENTICATION_FAILED')


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Issue a new access token using a valid refresh token.

    Requires ``Authorization: Bearer <refresh_token>`` header.

    Returns 200 with ``{ access_token }`` on success.
    """
    current_user_id = get_jwt_identity()
    try:
        result = auth_service.refresh_tokens(current_user_id)
        return success_response(data=result)
    except ValueError as exc:
        return error_response(str(exc), 401, 'TOKEN_REFRESH_FAILED')


@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """Revoke the current access token (add JTI to blocklist).

    Requires a valid access token in the ``Authorization`` header.

    Returns 200 on success.
    """
    jti = get_jwt().get('jti')
    auth_service.logout(jti)
    return success_response(message='Logged out successfully.')


@auth_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """Change the authenticated user's password.

    Request body (JSON)::

        {
          "old_password": "OldSecret1!",
          "new_password": "NewSecret2@"
        }

    Returns 200 on success.
    Returns 400 on validation failure.
    Returns 401 if old_password is wrong.
    """
    from app.models.user import User

    data = request.get_json(silent=True) or {}
    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')

    if not old_password:
        return error_response('old_password is required.', 400, 'VALIDATION_ERROR')
    if not new_password:
        return error_response('new_password is required.', 400, 'VALIDATION_ERROR')

    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return error_response('User not found.', 404, 'NOT_FOUND')

    try:
        auth_service.change_password(user, old_password, new_password)
        return success_response(message='Password changed successfully.')
    except ValueError as exc:
        return error_response(str(exc), 400, 'VALIDATION_ERROR')
