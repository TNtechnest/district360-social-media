"""Authentication extensions — OTP login, OAuth, session & device tracking."""

from __future__ import annotations
import logging
import os
import secrets
from datetime import datetime, timezone, timedelta

from app.extensions import db
from app.models.user import User
from app.models.auth_ext import OtpCode, UserSession, OAuthConnection
from app.services.auth_service import _make_access_token, _make_refresh_token
from app.services.audit_service import write_audit_log, write_activity_log
from app.utils.db import paginate_query

logger = logging.getLogger(__name__)

OTP_LENGTH = 6
OTP_EXPIRY_MINUTES = 10
OTP_MAX_ATTEMPTS = 5


# ---------------------------------------------------------------------------
# OTP Generation & Verification
# ---------------------------------------------------------------------------

def _generate_otp() -> str:
    return ''.join(secrets.choice('0123456789') for _ in range(OTP_LENGTH))


def send_otp(
    district_id: str, email: str | None = None, phone: str | None = None,
    purpose: str = 'login', user_id: str | None = None,
) -> dict:
    """Generate and 'send' an OTP (logs in dev, dispatches in production).

    Args:
        district_id: Tenant scope.
        email:       Recipient email address.
        phone:       Recipient phone number.
        purpose:     ``'login'`` | ``'verify_email'`` | ``'verify_phone'`` | ``'reset_password'``.
        user_id:     Associated user (optional).

    Returns:
        Dict with delivery info.  **In dev the OTP is returned; in production it is not.**
    """
    if not email and not phone:
        raise ValueError('Either email or phone is required.')

    # Invalidate previous unused OTPs for this contact + purpose
    query = OtpCode.query.filter_by(
        district_id=district_id, purpose=purpose, is_used=False,
    )
    if email:
        query = query.filter(OtpCode.email == email)
    if phone:
        query = query.filter(OtpCode.phone == phone)
    for old in query.all():
        old.is_used = True

    code = _generate_otp()
    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(minutes=OTP_EXPIRY_MINUTES)).isoformat()

    otp = OtpCode(
        district_id=district_id,
        user_id=user_id,
        email=email,
        phone=phone,
        code=code,
        purpose=purpose,
        expires_at=expires_at,
        sent_to=email or phone,
    )
    db.session.add(otp)
    db.session.flush()

    # In production, dispatch via notification service
    _dispatch_otp(email, phone, code, purpose)

    db.session.commit()
    logger.info('OTP sent to %s for purpose=%s', email or phone, purpose)

    # Return OTP in dev only
    is_dev = not os.getenv('PRODUCTION', False)
    result = {'message': f'OTP sent to {email or phone}', 'expires_at': expires_at}
    if is_dev:
        result['otp'] = code
    return result


def _dispatch_otp(email: str | None, phone: str | None, code: str, purpose: str) -> None:
    """Dispatch OTP via email or SMS using the notification service."""
    try:
        from app.services.notifications.notification_service import send_notification
        if email:
            send_notification(
                district_id='system',
                channel='email',
                recipient=email,
                event_key=f'otp.{purpose}',
                variables={'otp': code},
            )
        if phone:
            send_notification(
                district_id='system',
                channel='sms',
                recipient=phone,
                event_key=f'otp.{purpose}',
                variables={'otp': code},
            )
    except Exception:
        logger.exception('OTP dispatch failed (non-blocking)')


def verify_otp(
    district_id: str, code: str,
    email: str | None = None, phone: str | None = None,
    purpose: str = 'login', mark_used: bool = True,
) -> OtpCode:
    """Verify an OTP code.

    Args:
        district_id: Tenant scope.
        code:        6-digit OTP.
        email:       Email the OTP was sent to.
        phone:       Phone the OTP was sent to.
        purpose:     Purpose of the OTP.
        mark_used:   Mark OTP as used after successful verification.

    Returns:
        Verified :class:`OtpCode`.

    Raises:
        ValueError: If invalid, expired, or too many attempts.
    """
    if not email and not phone:
        raise ValueError('Either email or phone is required.')

    query = OtpCode.query.filter_by(
        district_id=district_id, code=code, purpose=purpose, is_used=False,
    )
    if email:
        query = query.filter(OtpCode.email == email)
    if phone:
        query = query.filter(OtpCode.phone == phone)

    otp = query.order_by(OtpCode.created_at.desc()).first()
    if not otp:
        raise ValueError('Invalid OTP code.')

    otp.attempts += 1
    if otp.attempts > OTP_MAX_ATTEMPTS:
        otp.is_used = True
        db.session.commit()
        raise ValueError('OTP attempts exceeded. Request a new OTP.')

    now = datetime.now(timezone.utc).isoformat()
    if otp.expires_at < now:
        raise ValueError('OTP has expired. Request a new OTP.')

    if mark_used:
        otp.is_used = True
        otp.verified_at = now

    db.session.commit()
    logger.info('OTP verified for %s, purpose=%s', email or phone, purpose)
    return otp


def login_with_otp(
    district_id: str, email: str | None = None, phone: str | None = None,
    otp_code: str | None = None, purpose: str = 'login',
) -> dict:
    """Login or register using OTP.

    If the user exists, returns tokens.  If not, creates a new user.

    Args:
        district_id: Tenant scope.
        email:       Email address.
        phone:       Phone number.
        otp_code:    6-digit OTP.
        purpose:     OTP purpose.

    Returns:
        Dict with ``access_token``, ``refresh_token``, ``user``, and ``is_new``.
    """
    if otp_code:
        verify_otp(district_id, otp_code, email=email, phone=phone, purpose=purpose)

    user = None
    if email:
        user = User.query.filter_by(district_id=district_id, email=email).first()
    elif phone:
        user = User.query.filter_by(district_id=district_id, phone=phone).first()

    is_new = False
    if not user:
        user = User(
            district_id=district_id,
            email=email or f'{phone}@otp.local',
            phone=phone,
            full_name=email or phone or 'Citizen',
            auth_provider='otp',
            status='active',
            email_verified=bool(email),
            phone_verified=bool(phone),
        )
        db.session.add(user)
        db.session.flush()
        is_new = True
        logger.info('New user created via OTP login: %s', email or phone)

    return {
        'access_token': _make_access_token(user),
        'refresh_token': _make_refresh_token(user),
        'user': user.to_dict(),
        'is_new': is_new,
    }


# ---------------------------------------------------------------------------
# OAuth (Google)
# ---------------------------------------------------------------------------

def oauth_login(
    district_id: str, provider: str, provider_token: str,
) -> dict:
    """Authenticate via OAuth provider (Google).

    Args:
        district_id:   Tenant scope.
        provider:      ``'google'`` (extensible to others).
        provider_token: OAuth access token from the provider.

    Returns:
        Dict with ``access_token``, ``refresh_token``, ``user``, and ``is_new``.
    """
    profile = _verify_oauth_token(provider, provider_token)
    provider_user_id = profile['sub']
    email = profile.get('email', '')
    name = profile.get('name', email.split('@')[0] if email else 'User')

    conn = OAuthConnection.query.filter_by(
        provider=provider, provider_user_id=provider_user_id,
    ).first()

    is_new = False
    user = None
    if conn:
        user = User.query.get(conn.user_id)
    if not user and email:
        user = User.query.filter_by(district_id=district_id, email=email).first()
    if not user:
        user = User(
            district_id=district_id,
            email=email or f'{provider_user_id}@oauth.{provider}',
            phone=None,
            full_name=name,
            auth_provider=provider,
            status='active',
            email_verified=True,
        )
        db.session.add(user)
        db.session.flush()
        is_new = True

    if not conn:
        conn = OAuthConnection(
            district_id=district_id,
            user_id=user.id,
            provider=provider,
            provider_user_id=provider_user_id,
            provider_email=email,
            access_token=provider_token,
            raw_profile=profile,
        )
        db.session.add(conn)
    else:
        conn.access_token = provider_token
        conn.raw_profile = profile

    db.session.commit()
    logger.info('OAuth login: provider=%s user=%s is_new=%s', provider, user.id, is_new)
    return {
        'access_token': _make_access_token(user),
        'refresh_token': _make_refresh_token(user),
        'user': user.to_dict(),
        'is_new': is_new,
    }


def _verify_oauth_token(provider: str, token: str) -> dict:
    """Verify an OAuth access token with the provider and return profile."""
    import requests

    if provider == 'google':
        resp = requests.get(
            'https://www.googleapis.com/oauth2/v3/userinfo',
            headers={'Authorization': f'Bearer {token}'},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    else:
        raise ValueError(f'Unsupported OAuth provider: {provider}')


# ---------------------------------------------------------------------------
# Session Tracking
# ---------------------------------------------------------------------------

def track_session(
    user_id: str, token_jti: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
    district_id: str | None = None,
) -> UserSession:
    """Record a new user session."""
    from app.utils.user_agent import parse_user_agent

    parsed = parse_user_agent(user_agent or '')
    session = UserSession(
        district_id=district_id or User.query.get(user_id).district_id,
        user_id=user_id,
        token_jti=token_jti,
        device_name=parsed.get('device', ''),
        device_type=parsed.get('device_type', ''),
        browser=parsed.get('browser', ''),
        os_info=parsed.get('os', ''),
        ip_address=ip_address,
        is_active=True,
        last_activity_at=datetime.now(timezone.utc).isoformat(),
    )
    db.session.add(session)
    db.session.commit()
    return session


def end_session(token_jti: str) -> None:
    """Mark a session as inactive on logout."""
    session = UserSession.query.filter_by(token_jti=token_jti, is_active=True).first()
    if session:
        session.is_active = False
        session.logged_out_at = datetime.now(timezone.utc).isoformat()
        db.session.commit()


def get_active_sessions(
    user_id: str, page: int = 1, per_page: int = 20,
):
    return paginate_query(
        UserSession.query.filter_by(user_id=user_id, is_active=True)
        .order_by(UserSession.last_activity_at.desc()),
        page, per_page,
    )


def get_all_sessions(
    district_id: str, page: int = 1, per_page: int = 20,
    user_id: str | None = None, is_active: bool | None = None,
):
    query = UserSession.query.filter_by(district_id=district_id)
    if user_id:
        query = query.filter(UserSession.user_id == user_id)
    if is_active is not None:
        query = query.filter(UserSession.is_active == is_active)
    return paginate_query(
        query.order_by(UserSession.last_activity_at.desc()), page, per_page,
    )
