"""Meta (Facebook + Instagram) OAuth 2.0 service.

Implements the full server-side OAuth flow for connecting district social
accounts via Facebook Login (which also covers Instagram Business accounts
linked to Facebook Pages).

Flow
----
1.  District admin calls  POST /api/v1/social/oauth/login
    → Service generates a CSRF state, stores it in MetaOAuthState,
      builds the Meta authorization URL and returns it.

2.  Admin is redirected to the Meta OAuth dialog in their browser.

3.  Meta redirects to   GET /api/v1/social/oauth/callback?code=...&state=...
    → Service validates state, exchanges code for a short-lived user token,
      extends it to a 60-day long-lived user token, then:

    a. Fetches all Facebook Pages the user administers.
    b. For each Page, fetches the linked Instagram Business account (if any).
    c. Creates or updates SocialAccount rows for each Page and IG account.
    d. Stores: access_token, refresh_token (for IG), page_id, instagram_id,
       token_expires_at, granted_scopes.

Multi-district support
----------------------
The ``district_id`` and ``initiated_by`` (user UUID) are captured in the
MetaOAuthState row at step 1.  The callback uses those values to scope
all created SocialAccount rows to the correct district — no cross-tenant
leakage is possible.

Required environment variables
-------------------------------
META_APP_ID              — Facebook App ID
META_APP_SECRET          — Facebook App Secret
META_REDIRECT_URI        — Full callback URL registered in the app
                           (e.g. https://api.district360.app/api/v1/social/oauth/callback)

Optional
--------
META_API_VERSION         — Graph API version (default: v19.0)
"""
from __future__ import annotations

import logging
import os
import secrets
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode, urljoin

import requests

from app.extensions import db
from app.models.meta_oauth_state import MetaOAuthState
from app.models.social_account import SocialAccount
from app.services.audit_service import write_audit_log

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

GRAPH_BASE  = 'https://graph.facebook.com'


def _api_version() -> str:
    return os.getenv('META_API_VERSION', 'v19.0')


def _app_id() -> str:
    v = os.getenv('META_APP_ID', '')
    if not v:
        raise RuntimeError('META_APP_ID environment variable is not set.')
    return v


def _app_secret() -> str:
    v = os.getenv('META_APP_SECRET', '')
    if not v:
        raise RuntimeError('META_APP_SECRET environment variable is not set.')
    return v


def _redirect_uri() -> str:
    return os.getenv(
        'META_REDIRECT_URI',
        'http://localhost:5000/api/v1/social/oauth/callback',
    )


# ---------------------------------------------------------------------------
# Scopes
# ---------------------------------------------------------------------------

FACEBOOK_SCOPES = [
    'pages_show_list',
    'pages_read_engagement',
    'pages_manage_posts',
    'pages_manage_engagement',   # reply to comments
    'pages_moderate',            # hide/delete comments
    'pages_messaging',           # optional: DMs
    'public_profile',
    'email',
]

INSTAGRAM_SCOPES = [
    'instagram_basic',
    'instagram_content_publish',
    'instagram_manage_comments',
    'instagram_manage_insights',
]

ALL_SCOPES = list(dict.fromkeys(FACEBOOK_SCOPES + INSTAGRAM_SCOPES))

_SCOPE_MAP = {
    'facebook':  FACEBOOK_SCOPES,
    'instagram': INSTAGRAM_SCOPES,
    'both':      ALL_SCOPES,
}

STATE_TTL_MINUTES = 10


# ---------------------------------------------------------------------------
# Step 1 — Generate authorization URL
# ---------------------------------------------------------------------------

def initiate_oauth(
    district_id: str,
    user_id: str,
    platform_scope: str = 'both',
    connection_label: str | None = None,
) -> dict:
    """Create a CSRF state, persist it, and return the Meta authorization URL.

    Args:
        district_id:      Tenant scope.
        user_id:          UUID of the district admin initiating the flow.
        platform_scope:   ``'facebook'`` | ``'instagram'`` | ``'both'``.
        connection_label: Optional friendly name for the connection.

    Returns:
        Dict with ``authorization_url``, ``state``, ``expires_at``.

    Raises:
        RuntimeError: If META_APP_ID is not configured.
        ValueError:   If platform_scope is invalid.
    """
    if platform_scope not in _SCOPE_MAP:
        raise ValueError(
            f"platform_scope must be one of: {', '.join(_SCOPE_MAP.keys())}"
        )

    state     = secrets.token_urlsafe(48)
    now       = datetime.now(timezone.utc)
    expires_at = (now + timedelta(minutes=STATE_TTL_MINUTES)).isoformat()

    state_row = MetaOAuthState(
        district_id=district_id,
        state=state,
        initiated_by=user_id,
        platform_scope=platform_scope,
        expires_at=expires_at,
        is_used=False,
        connection_label=connection_label,
    )
    db.session.add(state_row)
    db.session.commit()

    scopes = _SCOPE_MAP[platform_scope]
    params = {
        'client_id':     _app_id(),
        'redirect_uri':  _redirect_uri(),
        'scope':         ','.join(scopes),
        'state':         state,
        'response_type': 'code',
    }
    authorization_url = (
        f'https://www.facebook.com/{_api_version()}/dialog/oauth?{urlencode(params)}'
    )

    logger.info(
        'Meta OAuth initiated: district=%s user=%s scope=%s',
        district_id, user_id, platform_scope,
    )
    return {
        'authorization_url': authorization_url,
        'state': state,
        'expires_at': expires_at,
        'platform_scope': platform_scope,
    }


# ---------------------------------------------------------------------------
# Step 2 — Handle callback, exchange code, store tokens
# ---------------------------------------------------------------------------

def handle_callback(code: str, state: str, error: str | None = None) -> dict:
    """Process the Meta OAuth callback.

    Args:
        code:  Authorization code from Meta.
        state: CSRF state value to validate.
        error: Error parameter set by Meta on denied permission.

    Returns:
        Dict with ``connected_accounts`` list, ``district_id``, ``user_id``.

    Raises:
        ValueError: On invalid/expired state, permission denied, or API error.
    """
    # ---- Validate state ----
    state_row = MetaOAuthState.query.filter_by(state=state, is_used=False).first()
    if not state_row:
        raise ValueError('Invalid or already-used OAuth state. Please restart the connection.')

    now = datetime.now(timezone.utc).isoformat()
    if state_row.expires_at < now:
        raise ValueError('OAuth state has expired. Please restart the connection.')

    if error:
        state_row.is_used = True
        db.session.commit()
        raise ValueError(f'Meta returned an error: {error}')

    district_id = state_row.district_id
    user_id     = state_row.initiated_by
    scope       = state_row.platform_scope
    label_hint  = state_row.connection_label or 'Meta Account'

    # Mark state as consumed immediately
    state_row.is_used = True
    db.session.flush()

    # ---- Exchange code for short-lived user token ----
    short_token = _exchange_code_for_token(code)

    # ---- Extend to long-lived user token (60 days) ----
    long_token, token_expires_at = _extend_to_long_lived_token(short_token)

    # ---- Fetch user profile ----
    me = _graph_get(long_token, 'me', fields='id,name,email')
    meta_user_id   = me.get('id', '')
    meta_user_name = me.get('name', '')

    connected_accounts = []

    # ---- Facebook Pages ----
    if scope in ('facebook', 'both'):
        pages = _fetch_pages(long_token)
        for page in pages:
            account = _upsert_facebook_page(
                district_id=district_id,
                page=page,
                meta_user_id=meta_user_id,
                actor_id=user_id,
                label_hint=label_hint,
                token_expires_at=token_expires_at,
                refresh_token=long_token,
            )
            connected_accounts.append(account.to_dict())

            # ---- Instagram Business accounts linked to this page ----
            if scope in ('instagram', 'both'):
                ig_account = _fetch_instagram_for_page(page)
                if ig_account:
                    ig = _upsert_instagram_account(
                        district_id=district_id,
                        page=page,
                        ig_account=ig_account,
                        actor_id=user_id,
                        label_hint=label_hint,
                        token_expires_at=token_expires_at,
                        refresh_token=long_token,
                    )
                    connected_accounts.append(ig.to_dict())

    # ---- Instagram-only (no page required — use user token) ----
    elif scope == 'instagram':
        # Without page linking, use the user token to discover IG accounts
        ig_accounts = _fetch_instagram_accounts_direct(long_token)
        for ig_account in ig_accounts:
            ig = _upsert_instagram_account_direct(
                district_id=district_id,
                ig_account=ig_account,
                user_token=long_token,
                actor_id=user_id,
                label_hint=label_hint,
                token_expires_at=token_expires_at,
            )
            connected_accounts.append(ig.to_dict())

    db.session.commit()

    logger.info(
        'Meta OAuth complete: district=%s user=%s accounts_connected=%d',
        district_id, user_id, len(connected_accounts),
    )
    return {
        'district_id': district_id,
        'user_id': user_id,
        'meta_user_id': meta_user_id,
        'meta_user_name': meta_user_name,
        'connected_accounts': connected_accounts,
        'token_expires_at': token_expires_at,
    }


# ---------------------------------------------------------------------------
# Token exchange helpers
# ---------------------------------------------------------------------------

def _exchange_code_for_token(code: str) -> str:
    """Exchange authorization code for a short-lived user access token."""
    resp = requests.get(
        f'{GRAPH_BASE}/{_api_version()}/oauth/access_token',
        params={
            'client_id':     _app_id(),
            'client_secret': _app_secret(),
            'redirect_uri':  _redirect_uri(),
            'code':          code,
        },
        timeout=15,
    )
    data = resp.json()
    if 'error' in data:
        raise ValueError(f"Token exchange failed: {data['error'].get('message', str(data))}")
    return data['access_token']


def _extend_to_long_lived_token(short_token: str) -> tuple[str, str]:
    """Extend a short-lived user token to a 60-day long-lived token.

    Returns:
        Tuple (long_lived_token: str, expires_at_iso: str).
    """
    resp = requests.get(
        f'{GRAPH_BASE}/{_api_version()}/oauth/access_token',
        params={
            'grant_type':        'fb_exchange_token',
            'client_id':         _app_id(),
            'client_secret':     _app_secret(),
            'fb_exchange_token': short_token,
        },
        timeout=15,
    )
    data = resp.json()
    if 'error' in data:
        logger.warning('Token extension failed, using short-lived token: %s', data)
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        return short_token, expires_at

    token = data['access_token']
    expires_in = data.get('expires_in', 5183944)   # ~60 days default
    expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
    ).isoformat()
    return token, expires_at


def _get_page_long_lived_token(page_id: str, user_token: str) -> str:
    """Get the long-lived Page Access Token for a specific page.

    Page tokens never expire as long as the user token that generated them
    is valid.  They are also not the same as user tokens.
    """
    resp = requests.get(
        f'{GRAPH_BASE}/{_api_version()}/{page_id}',
        params={'fields': 'access_token', 'access_token': user_token},
        timeout=10,
    )
    data = resp.json()
    return data.get('access_token', user_token)


# ---------------------------------------------------------------------------
# Facebook Page helpers
# ---------------------------------------------------------------------------

def _fetch_pages(user_token: str) -> list[dict]:
    """Fetch all pages the user manages."""
    resp = requests.get(
        f'{GRAPH_BASE}/{_api_version()}/me/accounts',
        params={
            'fields': 'id,name,category,tasks,access_token,instagram_business_account',
            'access_token': user_token,
        },
        timeout=15,
    )
    data = resp.json()
    if 'error' in data:
        logger.warning('Failed to fetch pages: %s', data['error'])
        return []
    return data.get('data', [])


def _upsert_facebook_page(
    district_id: str,
    page: dict,
    meta_user_id: str,
    actor_id: str,
    label_hint: str,
    token_expires_at: str,
    refresh_token: str,
) -> SocialAccount:
    """Create or update a SocialAccount for a Facebook Page."""
    page_id          = page['id']
    page_name        = page.get('name', page_id)
    page_token       = page.get('access_token', '')

    existing = SocialAccount.query.filter_by(
        district_id=district_id,
        platform='facebook',
        platform_account_id=page_id,
    ).first()

    if existing:
        existing.credentials = {
            'access_token':      page_token,
            'refresh_token':     refresh_token,
            'page_id':           page_id,
            'instagram_id':      None,
            'page_access_token': page_token,
            'meta_user_id':      meta_user_id,
            'token_expires_at':  token_expires_at,
        }
        existing.username  = page_name
        existing.is_active = True
        existing.config    = {
            **existing.config,
            'page_id':          page_id,
            'page_name':        page_name,
            'page_category':    page.get('category', ''),
            'granted_scopes':   FACEBOOK_SCOPES,
            'token_expires_at': token_expires_at,
        }
        write_audit_log(
            district_id=district_id, actor_id=actor_id,
            action='social_account.facebook.reconnected',
            resource_type='social_account', resource_id=existing.id,
        )
        return existing

    account = SocialAccount(
        district_id=district_id,
        platform='facebook',
        label=f'{label_hint} – {page_name}',
        platform_account_id=page_id,
        username=page_name,
        is_active=True,
        credentials={
            'access_token':      page_token,
            'refresh_token':     refresh_token,
            'page_id':           page_id,
            'instagram_id':      None,
            'page_access_token': page_token,
            'meta_user_id':      meta_user_id,
            'token_expires_at':  token_expires_at,
        },
        config={
            'page_id':          page_id,
            'page_name':        page_name,
            'page_category':    page.get('category', ''),
            'granted_scopes':   FACEBOOK_SCOPES,
            'token_expires_at': token_expires_at,
        },
    )
    db.session.add(account)
    db.session.flush()
    write_audit_log(
        district_id=district_id, actor_id=actor_id,
        action='social_account.facebook.connected',
        resource_type='social_account', resource_id=account.id,
        after_state={'page_id': page_id, 'page_name': page_name},
    )
    return account


# ---------------------------------------------------------------------------
# Instagram helpers
# ---------------------------------------------------------------------------

def _fetch_instagram_for_page(page: dict) -> dict | None:
    """Extract the Instagram Business Account linked to a Facebook Page."""
    ig = page.get('instagram_business_account')
    if not ig or not ig.get('id'):
        return None
    page_token = page.get('access_token', '')
    if not page_token:
        return ig
    # Enrich with profile details
    resp = requests.get(
        f'{GRAPH_BASE}/{_api_version()}/{ig["id"]}',
        params={
            'fields': 'id,name,username,followers_count,media_count,profile_picture_url',
            'access_token': page_token,
        },
        timeout=10,
    )
    data = resp.json()
    if 'error' not in data:
        return data
    return ig


def _upsert_instagram_account(
    district_id: str,
    page: dict,
    ig_account: dict,
    actor_id: str,
    label_hint: str,
    token_expires_at: str,
    refresh_token: str,
) -> SocialAccount:
    """Create or update a SocialAccount for an Instagram Business account."""
    ig_id       = ig_account['id']
    ig_username = ig_account.get('username', ig_id)
    page_id     = page['id']
    page_token  = page.get('access_token', '')

    existing = SocialAccount.query.filter_by(
        district_id=district_id,
        platform='instagram',
        platform_account_id=ig_id,
    ).first()

    if existing:
        existing.credentials = {
            'access_token':         page_token,
            'refresh_token':        refresh_token,
            'page_id':              page_id,
            'instagram_id':         ig_id,
            'instagram_account_id': ig_id,
            'page_access_token':    page_token,
            'token_expires_at':     token_expires_at,
        }
        existing.username  = ig_username
        existing.is_active = True
        existing.config    = {
            **existing.config,
            'instagram_account_id': ig_id,
            'linked_page_id':       page_id,
            'granted_scopes':       INSTAGRAM_SCOPES,
            'token_expires_at':     token_expires_at,
            'followers_count':      ig_account.get('followers_count', 0),
        }
        write_audit_log(
            district_id=district_id, actor_id=actor_id,
            action='social_account.instagram.reconnected',
            resource_type='social_account', resource_id=existing.id,
        )
        return existing

    account = SocialAccount(
        district_id=district_id,
        platform='instagram',
        label=f'{label_hint} – @{ig_username}',
        platform_account_id=ig_id,
        username=ig_username,
        is_active=True,
        credentials={
            'access_token':         page_token,
            'refresh_token':        refresh_token,
            'page_id':              page_id,
            'instagram_id':         ig_id,
            'instagram_account_id': ig_id,
            'page_access_token':    page_token,
            'token_expires_at':     token_expires_at,
        },
        config={
            'instagram_account_id': ig_id,
            'linked_page_id':       page_id,
            'granted_scopes':       INSTAGRAM_SCOPES,
            'token_expires_at':     token_expires_at,
            'followers_count':      ig_account.get('followers_count', 0),
            'media_count':          ig_account.get('media_count', 0),
        },
    )
    db.session.add(account)
    db.session.flush()
    write_audit_log(
        district_id=district_id, actor_id=actor_id,
        action='social_account.instagram.connected',
        resource_type='social_account', resource_id=account.id,
        after_state={'instagram_id': ig_id, 'username': ig_username},
    )
    return account


def _fetch_instagram_accounts_direct(user_token: str) -> list[dict]:
    """Discover Instagram accounts via /me/instagram_accounts endpoint."""
    try:
        resp = requests.get(
            f'{GRAPH_BASE}/{_api_version()}/me/instagram_accounts',
            params={'fields': 'id,username,name,followers_count', 'access_token': user_token},
            timeout=10,
        )
        return resp.json().get('data', [])
    except Exception:
        return []


def _upsert_instagram_account_direct(
    district_id: str,
    ig_account: dict,
    user_token: str,
    actor_id: str,
    label_hint: str,
    token_expires_at: str,
) -> SocialAccount:
    """Create or update Instagram account without a linked Page."""
    ig_id       = ig_account['id']
    ig_username = ig_account.get('username', ig_id)

    existing = SocialAccount.query.filter_by(
        district_id=district_id,
        platform='instagram',
        platform_account_id=ig_id,
    ).first()

    if existing:
        existing.credentials = {
            **existing.credentials,
            'access_token':      user_token,
            'refresh_token':     user_token,
            'instagram_id':      ig_id,
            'page_access_token': user_token,
            'token_expires_at':  token_expires_at,
        }
        existing.is_active = True
        return existing

    account = SocialAccount(
        district_id=district_id,
        platform='instagram',
        label=f'{label_hint} – @{ig_username}',
        platform_account_id=ig_id,
        username=ig_username,
        is_active=True,
        credentials={
            'access_token':         user_token,
            'refresh_token':        user_token,
            'page_id':              None,
            'instagram_id':         ig_id,
            'instagram_account_id': ig_id,
            'page_access_token':    user_token,
            'token_expires_at':     token_expires_at,
        },
        config={
            'instagram_account_id': ig_id,
            'granted_scopes':       INSTAGRAM_SCOPES,
            'token_expires_at':     token_expires_at,
        },
    )
    db.session.add(account)
    db.session.flush()
    return account


# ---------------------------------------------------------------------------
# Token refresh (long-lived tokens can be refreshed before they expire)
# ---------------------------------------------------------------------------

def refresh_page_token(account: SocialAccount) -> SocialAccount:
    """Refresh the access token for a Facebook or Instagram SocialAccount.

    Args:
        account: The SocialAccount whose token should be refreshed.

    Returns:
        Updated SocialAccount with new token and expiry.

    Raises:
        ValueError: If credentials are missing or refresh fails.
    """
    page_token = account.credentials.get('page_access_token')
    if not page_token:
        raise ValueError('No page_access_token found in credentials.')

    new_token, expires_at = _extend_to_long_lived_token(page_token)
    account.credentials = {
        **account.credentials,
        'access_token':      new_token,
        'page_access_token': new_token,
        'token_expires_at':  expires_at,
    }
    account.config = {
        **account.config,
        'token_expires_at': expires_at,
    }
    db.session.commit()
    logger.info('Token refreshed for account %s (platform=%s)', account.id, account.platform)
    return account


def get_token_status(account: SocialAccount) -> dict:
    """Return the token validity status for an account.

    Returns:
        Dict with ``is_valid``, ``expires_at``, ``days_remaining``.
    """
    expires_at_str = account.credentials.get('token_expires_at') or \
                     account.config.get('token_expires_at')

    if not expires_at_str:
        return {'is_valid': True, 'expires_at': None, 'days_remaining': None}

    try:
        expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
        now        = datetime.now(timezone.utc)
        delta      = expires_at - now
        days_left  = delta.days
        is_valid   = delta.total_seconds() > 0
        return {
            'is_valid':       is_valid,
            'expires_at':     expires_at_str,
            'days_remaining': max(days_left, 0) if is_valid else 0,
        }
    except (ValueError, TypeError):
        return {'is_valid': True, 'expires_at': expires_at_str, 'days_remaining': None}


# ---------------------------------------------------------------------------
# Graph API generic helper
# ---------------------------------------------------------------------------

def _graph_get(token: str, endpoint: str, **params) -> dict:
    """Make a GET request to the Graph API."""
    resp = requests.get(
        f'{GRAPH_BASE}/{_api_version()}/{endpoint}',
        params={'access_token': token, **params},
        timeout=10,
    )
    data = resp.json()
    if 'error' in data:
        raise ValueError(f"Graph API error: {data['error'].get('message', str(data))}")
    return data
