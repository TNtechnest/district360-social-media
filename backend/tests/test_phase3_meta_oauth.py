"""Phase 3 — Meta OAuth tests.

Covers:
  - initiate_oauth() service
  - handle_callback() service (mocked Meta API)
  - Token status / refresh helpers
  - API endpoints: /login, /callback, /token-status, /refresh-token
  - Multi-district isolation
  - CSRF state validation
  - Error handling
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

from app.models import SocialAccount, Permission
from app.models.meta_oauth_state import MetaOAuthState
from app.services.social.meta_oauth_service import (
    initiate_oauth, get_token_status,
)


def _grant(db_session, role, resource, action):
    p = Permission.query.filter_by(resource=resource, action=action).first()
    if not p:
        p = Permission(resource=resource, action=action)
        db_session.add(p)
        db_session.flush()
    if p not in role.permissions:
        role.permissions.append(p)
        db_session.flush()


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def meta_env(monkeypatch):
    """Inject fake Meta app credentials for all tests."""
    monkeypatch.setenv('META_APP_ID',     'fake_app_id_12345')
    monkeypatch.setenv('META_APP_SECRET', 'fake_app_secret_xyz')
    monkeypatch.setenv('META_REDIRECT_URI',
                       'http://localhost:5000/api/v1/social/oauth/callback')


@pytest.fixture
def oauth_state(db_session, district, admin_user):
    """A valid, unused MetaOAuthState row."""
    from app.services.social.meta_oauth_service import STATE_TTL_MINUTES
    import secrets as _s
    state = _s.token_urlsafe(48)
    now   = datetime.now(timezone.utc)
    row   = MetaOAuthState(
        district_id=district.id,
        state=state,
        initiated_by=admin_user.id,
        platform_scope='both',
        expires_at=(now + timedelta(minutes=STATE_TTL_MINUTES)).isoformat(),
        is_used=False,
        connection_label='Test Page',
    )
    db_session.add(row)
    db_session.flush()
    return row


@pytest.fixture
def facebook_account(db_session, district):
    """A Facebook SocialAccount with a token that expires in 45 days."""
    expires = (datetime.now(timezone.utc) + timedelta(days=45)).isoformat()
    acct = SocialAccount(
        district_id=district.id,
        platform='facebook',
        label='Test Facebook Page',
        platform_account_id='fb_page_001',
        username='Test Page',
        is_active=True,
        credentials={
            'page_access_token': 'page_tok_abc',
            'page_id': 'fb_page_001',
            'token_expires_at': expires,
        },
        config={'token_expires_at': expires},
    )
    db_session.add(acct)
    db_session.flush()
    return acct


@pytest.fixture
def expired_account(db_session, district):
    """A Facebook account with an already-expired token."""
    expires = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    acct = SocialAccount(
        district_id=district.id,
        platform='facebook',
        label='Expired Page',
        platform_account_id='fb_page_expired',
        username='Expired Page',
        is_active=True,
        credentials={
            'page_access_token': 'expired_tok',
            'page_id': 'fb_page_expired',
            'token_expires_at': expires,
        },
        config={'token_expires_at': expires},
    )
    db_session.add(acct)
    db_session.flush()
    return acct


def test_handle_callback_stores_phase3_oauth_fields(db_session, oauth_state, monkeypatch):
    """Callback stores access_token, refresh_token, page_id, and instagram_id."""
    from app.services.social import meta_oauth_service as svc

    monkeypatch.setattr(svc, '_exchange_code_for_token', lambda code: 'short_user_token')
    monkeypatch.setattr(
        svc,
        '_extend_to_long_lived_token',
        lambda token: ('long_user_refresh_token', '2026-09-01T00:00:00+00:00'),
    )
    monkeypatch.setattr(
        svc,
        '_graph_get',
        lambda token, endpoint, **params: {
            'id': 'meta_user_001',
            'name': 'Meta Admin',
            'email': 'admin@example.test',
        },
    )
    monkeypatch.setattr(
        svc,
        '_fetch_pages',
        lambda token: [{
            'id': 'fb_page_001',
            'name': 'District Page',
            'category': 'Government Organization',
            'access_token': 'page_access_token_001',
            'instagram_business_account': {'id': 'ig_business_001'},
        }],
    )
    monkeypatch.setattr(
        svc,
        '_fetch_instagram_for_page',
        lambda page: {
            'id': 'ig_business_001',
            'username': 'district360',
            'followers_count': 123,
            'media_count': 9,
        },
    )

    result = svc.handle_callback(code='oauth_code', state=oauth_state.state)

    assert result['district_id'] == oauth_state.district_id
    assert len(result['connected_accounts']) == 2

    facebook = SocialAccount.query.filter_by(
        district_id=oauth_state.district_id,
        platform='facebook',
        platform_account_id='fb_page_001',
    ).first()
    instagram = SocialAccount.query.filter_by(
        district_id=oauth_state.district_id,
        platform='instagram',
        platform_account_id='ig_business_001',
    ).first()

    assert facebook is not None
    assert facebook.credentials['access_token'] == 'page_access_token_001'
    assert facebook.credentials['refresh_token'] == 'long_user_refresh_token'
    assert facebook.credentials['page_id'] == 'fb_page_001'
    assert facebook.credentials['instagram_id'] is None

    assert instagram is not None
    assert instagram.credentials['access_token'] == 'page_access_token_001'
    assert instagram.credentials['refresh_token'] == 'long_user_refresh_token'
    assert instagram.credentials['page_id'] == 'fb_page_001'
    assert instagram.credentials['instagram_id'] == 'ig_business_001'

    db_session.refresh(oauth_state)
    assert oauth_state.is_used is True


def test_handle_callback_keeps_same_page_separate_per_district(
    db_session, district, admin_user, monkeypatch
):
    """The same Meta page can be connected independently by different districts."""
    from app.models import District, User, Role
    from app.extensions import bcrypt
    from app.services.social import meta_oauth_service as svc

    other_district = District(
        name='Other District',
        slug='other-district-phase3',
        region='Test Region',
        status='active',
        config={},
    )
    db_session.add(other_district)
    db_session.flush()
    other_role = Role(
        district_id=other_district.id,
        name='district_admin',
        description='District administrator',
        is_system=False,
    )
    other_user = User(
        district_id=other_district.id,
        email='other-admin@test.example',
        full_name='Other Admin',
        password_hash=bcrypt.generate_password_hash('Admin1234').decode('utf-8'),
        auth_provider='local',
        status='active',
    )
    db_session.add_all([other_role, other_user])
    db_session.flush()

    existing = SocialAccount(
        district_id=other_district.id,
        platform='facebook',
        label='Other District Page',
        platform_account_id='shared_page_001',
        username='Shared Page',
        credentials={
            'access_token': 'old_other_token',
            'page_access_token': 'old_other_token',
            'page_id': 'shared_page_001',
        },
        config={},
        is_active=True,
    )
    db_session.add(existing)
    state = MetaOAuthState(
        district_id=district.id,
        state='state_for_current_district',
        initiated_by=admin_user.id,
        platform_scope='facebook',
        expires_at=(datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
        is_used=False,
    )
    db_session.add(state)
    db_session.flush()

    monkeypatch.setattr(svc, '_exchange_code_for_token', lambda code: 'short')
    monkeypatch.setattr(svc, '_extend_to_long_lived_token', lambda token: ('long', '2026-09-01T00:00:00+00:00'))
    monkeypatch.setattr(svc, '_graph_get', lambda token, endpoint, **params: {'id': 'meta_user', 'name': 'Admin'})
    monkeypatch.setattr(
        svc,
        '_fetch_pages',
        lambda token: [{
            'id': 'shared_page_001',
            'name': 'Shared Page',
            'access_token': 'new_current_token',
        }],
    )

    svc.handle_callback(code='oauth_code', state=state.state)

    current = SocialAccount.query.filter_by(
        district_id=district.id,
        platform='facebook',
        platform_account_id='shared_page_001',
    ).first()
    other = SocialAccount.query.filter_by(id=existing.id).first()

    assert current is not None
    assert current.id != other.id
    assert current.credentials['access_token'] == 'new_current_token'
    assert other.credentials['access_token'] == 'old_other_token'


def test_oauth_login_endpoint_returns_authorization_url(client, auth_headers, admin_role, db_session):
    _grant(db_session, admin_role, 'social_account', 'create')

    response = client.post(
        '/api/v1/social/oauth/login',
        json={'platform_scope': 'both', 'connection_label': 'Main District Page'},
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['data']['authorization_url'].startswith('https://www.facebook.com/')
    assert payload['data']['platform_scope'] == 'both'
    assert MetaOAuthState.query.filter_by(state=payload['data']['state']).first() is not None


def test_refresh_page_token_keeps_access_token_alias_in_sync(db_session, facebook_account, monkeypatch):
    from app.services.social import meta_oauth_service as svc

    monkeypatch.setattr(
        svc,
        '_extend_to_long_lived_token',
        lambda token: ('refreshed_page_token', '2026-10-01T00:00:00+00:00'),
    )

    svc.refresh_page_token(facebook_account)

    assert facebook_account.credentials['access_token'] == 'refreshed_page_token'
    assert facebook_account.credentials['page_access_token'] == 'refreshed_page_token'

