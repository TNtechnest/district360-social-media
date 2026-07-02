"""Content management service — draft, publish, and track social posts."""
import logging
from datetime import datetime, timezone

from app.extensions import db
from app.models.social_post import SocialPost
from app.models.social_account import SocialAccount
from app.services.audit_service import write_audit_log
from app.services.social.connector_factory import ConnectorFactory
from app.services.ai.ai_engine import analyze as ai_analyze
from app.utils.db import paginate_query

logger = logging.getLogger(__name__)


def get_posts(district_id: str, page: int = 1, per_page: int = 20,
              status: str | None = None, platform: str | None = None,
              account_id: str | None = None) -> object:
    query = SocialPost.query.filter_by(district_id=district_id)
    if status:
        query = query.filter(SocialPost.status == status)
    if platform:
        query = query.filter(SocialPost.platform == platform)
    if account_id:
        query = query.filter(SocialPost.account_id == account_id)
    return paginate_query(query.order_by(SocialPost.created_at.desc()), page, per_page)


def get_post(district_id: str, post_id: str) -> SocialPost:
    post = SocialPost.query.filter_by(id=post_id, district_id=district_id).first()
    if not post:
        raise ValueError('Post not found.')
    return post


def create_draft(
    district_id: str,
    account_id: str,
    content: str,
    author_id: str | None = None,
    scheduled_at: str | None = None,
    meta: dict | None = None,
    media_ids: list[str] | None = None,
) -> SocialPost:
    """Create a draft or scheduled post."""
    account = SocialAccount.query.filter_by(id=account_id, district_id=district_id).first()
    if not account:
        raise ValueError('Social account not found in this district.')

    status = 'scheduled' if scheduled_at else 'draft'

    post = SocialPost(
        district_id=district_id,
        account_id=account_id,
        author_id=author_id,
        content=content,
        platform=account.platform,
        scheduled_at=scheduled_at,
        status=status,
        meta=meta or {},
    )

    # Run AI analysis on the outbound content
    try:
        ai_result = ai_analyze(content)
        post.ai_analysis = ai_result.to_dict()
    except Exception:
        logger.warning('AI analysis failed for draft post — continuing without.')

    db.session.add(post)
    db.session.flush()

    # Attach media items if provided
    if media_ids:
        from app.models.media_item import MediaItem
        for mid in media_ids:
            item = MediaItem.query.filter_by(id=mid, district_id=district_id).first()
            if item:
                item.post_id = post.id

    write_audit_log(district_id=district_id, actor_id=author_id,
                    action='social_post.drafted', resource_type='social_post',
                    resource_id=post.id, after_state={'content': content[:200], 'status': status})
    db.session.commit()
    return post


def publish_now(district_id: str, post_id: str, actor_id: str | None = None) -> SocialPost:
    """Immediately publish a draft or scheduled post to its platform."""
    post = get_post(district_id, post_id)

    if post.status not in ('draft', 'scheduled'):
        raise ValueError(f"Cannot publish a post with status '{post.status}'.")

    account = SocialAccount.query.get(post.account_id)
    if not account or not account.is_active:
        raise ValueError('The associated social account is not active.')

    connector = ConnectorFactory.get(account)

    media_urls = [m.url for m in post.media_items if m.url]

    result = connector.publish_post(post.content, media_urls=media_urls, meta=post.meta)

    if result.success:
        post.status = 'published'
        post.platform_post_id = result.platform_post_id
        post.published_at = datetime.now(timezone.utc).isoformat()
        post.error_message = None
    else:
        post.status = 'failed'
        post.error_message = result.error_message

    write_audit_log(district_id=district_id, actor_id=actor_id,
                    action=f'social_post.{"published" if result.success else "failed"}',
                    resource_type='social_post', resource_id=post.id,
                    after_state={'status': post.status, 'platform_post_id': post.platform_post_id})
    db.session.commit()
    return post


def update_post(district_id: str, post_id: str, actor_id: str | None = None, **fields) -> SocialPost:
    """Update a draft post (only before publishing)."""
    post = get_post(district_id, post_id)
    if post.status not in ('draft', 'scheduled'):
        raise ValueError('Only draft or scheduled posts can be edited.')

    allowed = {'content', 'scheduled_at', 'meta', 'status'}
    before = post.to_dict()
    for k, v in fields.items():
        if k not in allowed:
            raise ValueError(f"Field '{k}' cannot be updated.")
        setattr(post, k, v)

    write_audit_log(district_id=district_id, actor_id=actor_id,
                    action='social_post.updated', resource_type='social_post',
                    resource_id=post_id, before_state=before, after_state=post.to_dict())
    db.session.commit()
    return post


def delete_post(district_id: str, post_id: str, actor_id: str | None = None) -> None:
    post = get_post(district_id, post_id)
    if post.status == 'published':
        raise ValueError('Published posts cannot be deleted. Use cancel status instead.')
    write_audit_log(district_id=district_id, actor_id=actor_id,
                    action='social_post.deleted', resource_type='social_post',
                    resource_id=post_id, before_state=post.to_dict())
    db.session.delete(post)
    db.session.commit()
