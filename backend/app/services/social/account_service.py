"""Social account management service.

Handles CRUD for SocialAccount records (connecting / disconnecting platforms).
"""
import logging
from app.extensions import db
from app.models.social_account import SocialAccount
from app.services.audit_service import write_audit_log
from app.utils.db import paginate_query

logger = logging.getLogger(__name__)

VALID_PLATFORMS = {'facebook', 'instagram', 'youtube', 'x', 'telegram'}


def get_accounts(district_id: str, page: int = 1, per_page: int = 20,
                 platform: str | None = None) -> object:
    query = SocialAccount.query.filter_by(district_id=district_id)
    if platform:
        query = query.filter(SocialAccount.platform == platform)
    return paginate_query(query.order_by(SocialAccount.created_at.desc()), page, per_page)


def get_account(district_id: str, account_id: str) -> SocialAccount:
    account = SocialAccount.query.filter_by(id=account_id, district_id=district_id).first()
    if not account:
        raise ValueError('Social account not found.')
    return account


def connect_account(
    district_id: str,
    platform: str,
    label: str,
    platform_account_id: str,
    credentials: dict,
    username: str | None = None,
    config: dict | None = None,
    actor_id: str | None = None,
) -> SocialAccount:
    if platform not in VALID_PLATFORMS:
        raise ValueError(f"Platform '{platform}' is not supported. Choose from: {', '.join(VALID_PLATFORMS)}")

    existing = SocialAccount.query.filter_by(
        district_id=district_id, platform=platform, platform_account_id=platform_account_id
    ).first()
    if existing:
        raise ValueError(f"A {platform} account with this ID is already connected.")

    account = SocialAccount(
        district_id=district_id,
        platform=platform,
        label=label,
        platform_account_id=platform_account_id,
        credentials=credentials,
        username=username,
        config=config or {},
        is_active=True,
    )
    db.session.add(account)
    db.session.flush()

    write_audit_log(
        district_id=district_id, actor_id=actor_id,
        action=f'social_account.connected.{platform}',
        resource_type='social_account', resource_id=account.id,
        after_state=account.to_dict(),
    )
    db.session.commit()
    logger.info('Social account connected: %s %s (district=%s)', platform, account.id, district_id)
    return account


def update_account(district_id: str, account_id: str, actor_id: str | None = None, **fields) -> SocialAccount:
    account = get_account(district_id, account_id)
    allowed = {'label', 'credentials', 'config', 'is_active', 'username', 'webhook_secret'}
    before = account.to_dict()
    for k, v in fields.items():
        if k not in allowed:
            raise ValueError(f"Field '{k}' cannot be updated.")
        setattr(account, k, v)
    write_audit_log(district_id=district_id, actor_id=actor_id,
                    action='social_account.updated', resource_type='social_account',
                    resource_id=account_id, before_state=before, after_state=account.to_dict())
    db.session.commit()
    return account


def disconnect_account(district_id: str, account_id: str, actor_id: str | None = None) -> None:
    account = get_account(district_id, account_id)
    write_audit_log(district_id=district_id, actor_id=actor_id,
                    action='social_account.disconnected', resource_type='social_account',
                    resource_id=account_id, before_state=account.to_dict())
    db.session.delete(account)
    db.session.commit()
