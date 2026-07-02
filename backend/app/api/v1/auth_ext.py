"""Authentication extension endpoints — added to the existing auth blueprint.

Routes (added to /api/v1/auth/)
------
POST   /auth/otp/send              — send OTP to email or phone
POST   /auth/otp/verify            — verify OTP code
POST   /auth/otp/login             — login or register with OTP
POST   /auth/oauth/google          — login with Google OAuth
GET    /auth/sessions              — list active sessions for current user
GET    /auth/sessions/all          — list all sessions (admin)
POST   /auth/sessions/revoke       — revoke a session
"""

import logging

from flask import request, g
from flask_jwt_extended import get_jwt, get_jwt_identity

from app.api.v1.auth import auth_bp
from app.services.auth_ext_service import (
    send_otp, verify_otp, login_with_otp, oauth_login,
    end_session, get_active_sessions, get_all_sessions,
)
from app.services.auth_service import logout as revoke_token
from app.services.rbac_service import require_permission
from app.utils.responses import success_response, error_response, paginated_response
from app.utils.validators import validate_pagination_params

logger = logging.getLogger(__name__)


def _district():
    return get_jwt().get('district_id', '')


@auth_bp.route('/otp/send', methods=['POST'])
def send_otp_endpoint():
    """Send an OTP to the user's email or phone."""
    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip()
    phone = data.get('phone', '').strip()
    purpose = data.get('purpose', 'login').strip()
    try:
        result = send_otp(
            district_id=data.get('district_id', 'system'),
            email=email or None, phone=phone or None, purpose=purpose,
        )
        return success_response(data=result, message='OTP sent.')
    except ValueError as exc:
        return error_response(str(exc), 400, 'VALIDATION_ERROR')


@auth_bp.route('/otp/verify', methods=['POST'])
def verify_otp_endpoint():
    """Verify an OTP code (does not issue tokens)."""
    data = request.get_json(silent=True) or {}
    code = data.get('code', '').strip()
    if not code:
        return error_response('code is required.', 400, 'VALIDATION_ERROR')
    try:
        otp = verify_otp(
            district_id=data.get('district_id', 'system'),
            code=code,
            email=data.get('email', '').strip() or None,
            phone=data.get('phone', '').strip() or None,
            purpose=data.get('purpose', 'login'),
        )
        return success_response(data=otp.to_dict(), message='OTP verified.')
    except ValueError as exc:
        return error_response(str(exc), 400, 'OTP_VERIFICATION_FAILED')


@auth_bp.route('/otp/login', methods=['POST'])
def otp_login_endpoint():
    """Login or register using OTP."""
    data = request.get_json(silent=True) or {}
    district_id = data.get('district_id', '').strip()
    if not district_id:
        return error_response('district_id is required.', 400, 'VALIDATION_ERROR')
    try:
        result = login_with_otp(
            district_id=district_id,
            email=data.get('email', '').strip() or None,
            phone=data.get('phone', '').strip() or None,
            otp_code=data.get('otp_code', '').strip() or None,
        )
        return success_response(data=result, message='OTP login successful.')
    except ValueError as exc:
        return error_response(str(exc), 400, 'OTP_LOGIN_FAILED')


@auth_bp.route('/oauth/google', methods=['POST'])
def google_oauth_endpoint():
    """Login or register using Google OAuth."""
    data = request.get_json(silent=True) or {}
    token = data.get('access_token', '').strip()
    district_id = data.get('district_id', '').strip()
    if not token:
        return error_response('access_token is required.', 400, 'VALIDATION_ERROR')
    if not district_id:
        return error_response('district_id is required.', 400, 'VALIDATION_ERROR')
    try:
        result = oauth_login(district_id, 'google', token)
        return success_response(data=result, message='Google OAuth login successful.')
    except ValueError as exc:
        return error_response(str(exc), 400, 'OAUTH_FAILED')
    except Exception as exc:
        logger.exception('Google OAuth failed')
        return error_response('OAuth authentication failed.', 401, 'OAUTH_FAILED')


@auth_bp.route('/sessions', methods=['GET'])
@require_permission('user', 'read')
def list_my_sessions():
    """List active sessions for the current user."""
    user_id = get_jwt_identity()
    page, per_page = validate_pagination_params(
        request.args.get('page', 1), request.args.get('per_page', 20)
    )
    pagination = get_active_sessions(user_id, page=page, per_page=per_page)
    return paginated_response([s.to_dict() for s in pagination.items], pagination)


@auth_bp.route('/sessions/all', methods=['GET'])
@require_permission('audit_log', 'read')
def list_all_sessions():
    """List all sessions (admin)."""
    page, per_page = validate_pagination_params(
        request.args.get('page', 1), request.args.get('per_page', 20)
    )
    is_active = request.args.get('is_active')
    if is_active is not None:
        is_active = is_active.lower() in ('true', '1', 'yes')
    pagination = get_all_sessions(
        _district(), page=page, per_page=per_page,
        user_id=request.args.get('user_id'), is_active=is_active,
    )
    return paginated_response([s.to_dict() for s in pagination.items], pagination)


@auth_bp.route('/sessions/revoke', methods=['POST'])
@require_permission('user', 'update')
def revoke_session_endpoint():
    """Revoke a specific session by JTI."""
    data = request.get_json(silent=True) or {}
    token_jti = data.get('token_jti', '').strip()
    if not token_jti:
        return error_response('token_jti is required.', 400, 'VALIDATION_ERROR')
    end_session(token_jti)
    revoke_token(token_jti)
    return success_response(message='Session revoked.')
