"""Meta (Facebook + Instagram) OAuth endpoints.

Routes
------
POST /api/v1/social/oauth/login
    Start the OAuth flow. Returns the Meta authorization URL.
    The district admin opens this URL in their browser.

GET  /api/v1/social/oauth/callback
    Meta redirects here with ?code=&state=
    Exchanges code for tokens, discovers pages/IG accounts,
    creates SocialAccount rows, returns connected account list.

GET  /api/v1/social/oauth/accounts/<id>/token-status
    Check whether a connected account's token is still valid.

POST /api/v1/social/oauth/accounts/<id>/refresh-token
    Force-refresh a long-lived page token before it expires.

GET  /api/v1/social/oauth/debug-token
    Validate a user-supplied access token via Meta's debug endpoint (dev only).
"""
import logging
import os

from flask import Blueprint, request, redirect, g
from flask_jwt_extended import get_jwt

from app.services.social.meta_oauth_service import (
    initiate_oauth,
    handle_callback,
    refresh_page_token,
    get_token_status,
    _app_id, _app_secret, GRAPH_BASE, _api_version,
)
from app.models.social_account import SocialAccount
from app.services.rbac_service import require_permission
from app.utils.responses import success_response, error_response

logger = logging.getLogger(__name__)
meta_oauth_bp = Blueprint('social_meta_oauth', __name__, url_prefix='/oauth')


def _district() -> str:
    return get_jwt().get('district_id', '')


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — Initiate OAuth
# ─────────────────────────────────────────────────────────────────────────────

@meta_oauth_bp.route('/login', methods=['POST'])
@require_permission('social_account', 'create')
def oauth_login():
    """Start the Meta OAuth flow for the calling district.

    Request body (JSON, all optional)::

        {
          "platform_scope":    "both",
          "connection_label":  "Main District Page"
        }

    Returns the ``authorization_url`` the district admin must visit in a
    browser to grant permission.

    ``platform_scope`` options:
    - ``"facebook"``  — Facebook Pages only
    - ``"instagram"`` — Instagram Business only (requires Page link in practice)
    - ``"both"``      — Facebook + Instagram (recommended, default)
    """
    data             = request.get_json(silent=True) or {}
    platform_scope   = data.get('platform_scope', 'both').strip()
    connection_label = data.get('connection_label', '').strip() or None

    try:
        result = initiate_oauth(
            district_id=_district(),
            user_id=g.current_user.id,
            platform_scope=platform_scope,
            connection_label=connection_label,
        )
        return success_response(data=result, message='Visit authorization_url to connect your account.')
    except RuntimeError as exc:
        # META_APP_ID not configured
        return error_response(str(exc), 503, 'META_NOT_CONFIGURED')
    except ValueError as exc:
        return error_response(str(exc), 400, 'VALIDATION_ERROR')


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — OAuth Callback
# ─────────────────────────────────────────────────────────────────────────────

@meta_oauth_bp.route('/callback', methods=['GET'])
def oauth_callback():
    """Handle the Meta OAuth redirect.

    Meta redirects here with ``?code=<code>&state=<state>`` on success,
    or ``?error=<error>&state=<state>`` on denial.

    This endpoint is called by the browser (GET redirect), not by the
    frontend JS — it completes the server-side token exchange and then
    redirects the browser to the configured frontend success/failure URL.

    In development (no FRONTEND_URL set), it returns JSON directly so you
    can test with curl / Postman.
    """
    code  = request.args.get('code', '').strip()
    state = request.args.get('state', '').strip()
    error = request.args.get('error', '').strip() or None

    frontend_url  = os.getenv('FRONTEND_URL', '')
    success_path  = os.getenv('META_OAUTH_SUCCESS_PATH', '/dashboard/social?connected=1')
    failure_path  = os.getenv('META_OAUTH_FAILURE_PATH', '/dashboard/social?error=oauth_failed')

    if not state:
        if frontend_url:
            return redirect(f'{frontend_url}{failure_path}&reason=missing_state')
        return error_response('Missing state parameter.', 400, 'INVALID_STATE')

    try:
        result = handle_callback(code=code, state=state, error=error or None)

        if frontend_url:
            count = len(result['connected_accounts'])
            return redirect(f'{frontend_url}{success_path}&accounts={count}')

        return success_response(
            data=result,
            message=f"{len(result['connected_accounts'])} account(s) connected successfully.",
        )

    except ValueError as exc:
        logger.warning('Meta OAuth callback error: %s', exc)
        if frontend_url:
            return redirect(f'{frontend_url}{failure_path}&reason=oauth_error')
        return error_response(str(exc), 400, 'OAUTH_CALLBACK_FAILED')

    except Exception as exc:
        logger.exception('Unexpected error in Meta OAuth callback')
        if frontend_url:
            return redirect(f'{frontend_url}{failure_path}&reason=server_error')
        return error_response('OAuth processing failed.', 500, 'OAUTH_SERVER_ERROR')


# ─────────────────────────────────────────────────────────────────────────────
# Token management
# ─────────────────────────────────────────────────────────────────────────────

@meta_oauth_bp.route('/accounts/<account_id>/token-status', methods=['GET'])
@require_permission('social_account', 'read')
def token_status(account_id: str):
    """Check token validity for a connected Meta account.

    Returns:
        ``is_valid``, ``expires_at``, ``days_remaining``.
    """
    account = SocialAccount.query.filter_by(
        id=account_id,
        district_id=_district(),
    ).first()
    if not account:
        return error_response('Social account not found.', 404, 'NOT_FOUND')
    if account.platform not in ('facebook', 'instagram'):
        return error_response(
            f"Token status only applies to facebook/instagram accounts, not '{account.platform}'.",
            400, 'NOT_SUPPORTED',
        )
    status = get_token_status(account)
    return success_response(data={**status, 'account_id': account_id})


@meta_oauth_bp.route('/accounts/<account_id>/refresh-token', methods=['POST'])
@require_permission('social_account', 'update')
def refresh_token(account_id: str):
    """Refresh the long-lived page access token for a Meta account.

    Call this before ``days_remaining < 7`` to avoid service interruption.
    """
    account = SocialAccount.query.filter_by(
        id=account_id,
        district_id=_district(),
    ).first()
    if not account:
        return error_response('Social account not found.', 404, 'NOT_FOUND')
    if account.platform not in ('facebook', 'instagram'):
        return error_response('Token refresh only applies to Meta accounts.', 400, 'NOT_SUPPORTED')
    try:
        updated = refresh_page_token(account)
        new_status = get_token_status(updated)
        return success_response(
            data={**new_status, 'account_id': account_id},
            message='Token refreshed successfully.',
        )
    except ValueError as exc:
        return error_response(str(exc), 400, 'REFRESH_FAILED')
    except Exception as exc:
        logger.exception('Token refresh failed for account %s', account_id)
        return error_response('Token refresh failed.', 502, 'META_API_ERROR')


# ─────────────────────────────────────────────────────────────────────────────
# Debug / development helpers
# ─────────────────────────────────────────────────────────────────────────────

@meta_oauth_bp.route('/debug-token', methods=['POST'])
@require_permission('social_account', 'read')
def debug_token():
    """Validate a Meta access token using the Graph API debug endpoint.

    Useful for diagnosing token issues in development.

    Request body (JSON)::

        { "access_token": "<token_to_inspect>" }
    """
    data  = request.get_json(silent=True) or {}
    token = data.get('access_token', '').strip()
    if not token:
        return error_response('access_token is required.', 400, 'VALIDATION_ERROR')

    try:
        import requests as _requests
        resp = _requests.get(
            f'{GRAPH_BASE}/{_api_version()}/debug_token',
            params={
                'input_token':  token,
                'access_token': f'{_app_id()}|{_app_secret()}',
            },
            timeout=10,
        )
        data = resp.json()
        if 'error' in data:
            return error_response(
                data['error'].get('message', 'Token debug failed.'),
                400, 'META_DEBUG_ERROR',
            )
        return success_response(data=data.get('data', data))
    except RuntimeError as exc:
        return error_response(str(exc), 503, 'META_NOT_CONFIGURED')
    except Exception as exc:
        return error_response(str(exc), 502, 'META_API_ERROR')
