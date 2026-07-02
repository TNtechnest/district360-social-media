"""AI Collector Assistant service.

Orchestrates:
  1. Collecting recent content from all active social accounts.
  2. Persisting new items as CollectedPost rows.
  3. Running the AI pipeline on each collected item.
  4. Updating the CollectedPost with AI labels.

Designed to be called from a scheduled task (Celery / APScheduler) or
triggered manually via the API.
"""
import logging
from dataclasses import dataclass

from app.extensions import db
from app.models.social_account import SocialAccount
from app.models.collected_post import CollectedPost
from app.services.social.base_connector import CollectedItem
from app.services.social.connector_factory import ConnectorFactory
from app.services.ai.ai_engine import analyze as ai_analyze
from app.utils.db import paginate_query

logger = logging.getLogger(__name__)


@dataclass
class CollectionSummary:
    """Result of one collector run."""
    posts: int = 0
    comments: int = 0
    updated: int = 0
    errors: int = 0

    @property
    def new_items(self) -> int:
        return self.posts + self.comments

    def to_dict(self) -> dict:
        return {
            'new_items': self.new_items,
            'posts': self.posts,
            'comments': self.comments,
            'updated': self.updated,
            'errors': self.errors,
        }


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------

def collect_for_account(
    account: SocialAccount,
    limit: int = 50,
    comment_limit: int = 100,
    include_comments: bool = True,
) -> int:
    """Collect recent posts and comments for a single social account.

    Args:
        account: Active :class:`SocialAccount` model instance.
        limit: Max posts to collect per run.
        comment_limit: Max comments to fetch for each collected/fetched post.
        include_comments: Whether to fetch comment threads after fetching posts.

    Returns:
        Number of newly stored rows, including posts and comments.
    """
    return collect_for_account_detailed(
        account,
        limit=limit,
        comment_limit=comment_limit,
        include_comments=include_comments,
    ).new_items


def collect_for_account_detailed(
    account: SocialAccount,
    limit: int = 50,
    comment_limit: int = 100,
    include_comments: bool = True,
) -> CollectionSummary:
    """Collect recent posts/comments for one account with a detailed summary."""
    summary = CollectionSummary()

    try:
        connector = ConnectorFactory.get(account)
    except ValueError as exc:
        logger.error('collect_for_account: %s', exc)
        summary.errors += 1
        return summary

    try:
        posts = connector.collect_recent(limit=limit)
    except Exception:
        logger.exception('collect_recent failed for account %s', account.id)
        summary.errors += 1
        return summary

    fetched_posts: list[CollectedItem] = []
    for item in posts:
        created, updated = _upsert_collected_item(account, item)
        if created and item.content_type == 'post':
            summary.posts += 1
        elif created:
            summary.comments += 1
        elif updated:
            summary.updated += 1

        if item.content_type == 'post' and item.platform_content_id:
            fetched_posts.append(item)

    if include_comments and hasattr(connector, 'collect_comments'):
        for post in fetched_posts:
            try:
                comments = connector.collect_comments(post.platform_content_id, limit=comment_limit)
            except Exception:
                logger.exception(
                    'collect_comments failed for account %s content %s',
                    account.id,
                    post.platform_content_id,
                )
                summary.errors += 1
                continue

            for comment in comments:
                created, updated = _upsert_collected_item(account, comment)
                if created:
                    summary.comments += 1
                elif updated:
                    summary.updated += 1

    if summary.new_items or summary.updated:
        db.session.commit()
        logger.info(
            'Collected account=%s platform=%s posts=%d comments=%d updated=%d',
            account.id,
            account.platform,
            summary.posts,
            summary.comments,
            summary.updated,
        )

    return summary


def _upsert_collected_item(account: SocialAccount, item: CollectedItem) -> tuple[bool, bool]:
    """Insert a collected item or refresh its engagement snapshot.

    Returns:
        Tuple ``(created, updated)``.
    """
    if not item.platform_content_id:
        return False, False
    if not item.raw_text.strip() and item.content_type != 'post':
        return False, False

    existing = CollectedPost.query.filter_by(
        account_id=account.id,
        platform_content_id=item.platform_content_id,
    ).first()

    if existing:
        changed = False
        for field, value in {
            'likes': item.likes,
            'comments': item.comments,
            'shares': item.shares,
            'platform_created_at': item.platform_created_at,
        }.items():
            if value is not None and getattr(existing, field) != value:
                setattr(existing, field, value)
                changed = True
        if item.raw_text.strip() and existing.raw_text != item.raw_text:
            existing.raw_text = item.raw_text
            changed = True
        return False, changed

    raw_text = item.raw_text.strip()
    if not raw_text:
        raw_text = f'[{account.platform} post without text]'

    post = CollectedPost(
        district_id=account.district_id,
        account_id=account.id,
        platform=account.platform,
        content_type=item.content_type,
        platform_content_id=item.platform_content_id,
        author_platform_id=item.author_platform_id,
        author_username=item.author_username,
        raw_text=raw_text,
        platform_created_at=item.platform_created_at,
        likes=item.likes,
        comments=item.comments,
        shares=item.shares,
        ai_status='pending',
    )
    db.session.add(post)
    return True, False


def collect_all_districts(limit: int = 50, comment_limit: int = 100) -> dict:
    """Collect for every active social account across all districts.

    Returns:
        Dict with totals and per-account details.
    """
    accounts = SocialAccount.query.filter_by(is_active=True).all()
    total = CollectionSummary()
    per_account = {}

    for account in accounts:
        summary = collect_for_account_detailed(
            account,
            limit=limit,
            comment_limit=comment_limit,
            include_comments=account.platform in ('facebook', 'instagram'),
        )
        per_account[account.id] = summary.to_dict()
        total.posts += summary.posts
        total.comments += summary.comments
        total.updated += summary.updated
        total.errors += summary.errors

    return {'total': total.to_dict(), 'accounts': per_account}


# ---------------------------------------------------------------------------
# AI Processing
# ---------------------------------------------------------------------------

def process_pending(batch_size: int = 100) -> int:
    """Run AI analysis on all pending CollectedPost rows.

    Args:
        batch_size: Max rows to process per call.

    Returns:
        Number of posts processed.
    """
    pending = (
        CollectedPost.query
        .filter_by(ai_status='pending')
        .limit(batch_size)
        .all()
    )

    processed = 0
    for post in pending:
        try:
            result = ai_analyze(
                text=post.raw_text,
                district_name=f'district_{post.district_id[:8]}',
                ref_id=post.id,
            )
            fields = result.to_post_fields()
            for k, v in fields.items():
                setattr(post, k, v)
            processed += 1
        except Exception:
            logger.exception('AI processing failed for collected_post %s', post.id)
            post.ai_status = 'failed'

    if processed or pending:
        db.session.commit()

    logger.info('AI processed %d collected posts', processed)
    return processed


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def get_collected_posts(
    district_id: str,
    page: int = 1,
    per_page: int = 20,
    platform: str | None = None,
    sentiment: str | None = None,
    is_complaint: bool | None = None,
    is_emergency: bool | None = None,
    is_spam: bool | None = None,
    review_status: str | None = None,
    search: str | None = None,
) -> object:
    query = CollectedPost.query.filter_by(district_id=district_id)

    if platform:
        query = query.filter(CollectedPost.platform == platform)
    if sentiment:
        query = query.filter(CollectedPost.sentiment == sentiment)
    if is_complaint is not None:
        query = query.filter(CollectedPost.is_complaint == is_complaint)
    if is_emergency is not None:
        query = query.filter(CollectedPost.is_emergency == is_emergency)
    if is_spam is not None:
        query = query.filter(CollectedPost.is_spam == is_spam)
    if review_status:
        query = query.filter(CollectedPost.review_status == review_status)
    if search:
        query = query.filter(CollectedPost.raw_text.ilike(f'%{search}%'))

    return paginate_query(query.order_by(CollectedPost.created_at.desc()), page, per_page)


def get_collected_post(district_id: str, post_id: str) -> CollectedPost:
    post = CollectedPost.query.filter_by(id=post_id, district_id=district_id).first()
    if not post:
        raise ValueError('Collected post not found.')
    return post


def update_review_status(district_id: str, post_id: str, review_status: str) -> CollectedPost:
    valid = {'unreviewed', 'reviewed', 'actioned', 'ignored'}
    if review_status not in valid:
        raise ValueError(f"review_status must be one of: {', '.join(valid)}")
    post = get_collected_post(district_id, post_id)
    post.review_status = review_status
    db.session.commit()
    return post