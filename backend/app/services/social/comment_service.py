"""SocialComment service — sync, store, analyse, and reply to comments.

Responsibilities:
  1. Persist comments collected from Facebook / Instagram.
  2. Run AI analysis pipeline on each comment.
  3. Send replies back to the platform via the appropriate connector.
  4. Moderate comments (hide / unhide / mark spam).
  5. Provide query helpers for the API layer.

All write operations emit audit log entries.
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone

from app.extensions import db
from app.models.social_comment import SocialComment
from app.models.comment_analysis import CommentAnalysis
from app.models.social_post import SocialPost
from app.services.audit_service import write_audit_log
from app.services.ai.ai_engine import analyze as ai_analyze
from app.utils.db import paginate_query

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Queries
# ─────────────────────────────────────────────────────────────────────────────

def get_comments(
    district_id: str,
    post_id: str | None = None,
    page: int = 1,
    per_page: int = 30,
    platform: str | None = None,
    sentiment: str | None = None,
    is_complaint: bool | None = None,
    is_emergency: bool | None = None,
    is_spam: bool | None = None,
    moderation_status: str | None = None,
    is_replied: bool | None = None,
    parent_only: bool = True,
    search: str | None = None,
) -> object:
    """Return a paginated list of comments, optionally scoped to one post.

    Args:
        district_id:       Tenant scope.
        post_id:           Restrict to a single post (optional).
        page:              1-based page number.
        per_page:          Page size (max 100).
        platform:          Filter by platform (facebook | instagram).
        sentiment:         Filter by sentiment label.
        is_complaint:      Flag filter.
        is_emergency:      Flag filter.
        is_spam:           Flag filter.
        moderation_status: Filter by moderation status.
        is_replied:        Filter by reply state.
        parent_only:       When True, exclude replies (parent_comment_id IS NULL).
        search:            Substring search in comment text.

    Returns:
        SQLAlchemy Pagination object.
    """
    q = SocialComment.query.filter_by(district_id=district_id)

    if post_id:
        q = q.filter(SocialComment.post_id == post_id)
    if platform:
        q = q.filter(SocialComment.platform == platform)
    if sentiment:
        q = q.filter(SocialComment.sentiment == sentiment)
    if is_complaint is not None:
        q = q.filter(SocialComment.is_complaint == is_complaint)
    if is_emergency is not None:
        q = q.filter(SocialComment.is_emergency == is_emergency)
    if is_spam is not None:
        q = q.filter(SocialComment.is_spam == is_spam)
    if moderation_status:
        q = q.filter(SocialComment.moderation_status == moderation_status)
    if is_replied is not None:
        q = q.filter(SocialComment.is_replied == is_replied)
    if parent_only:
        q = q.filter(SocialComment.parent_comment_id.is_(None))
    if search:
        q = q.filter(SocialComment.text.ilike(f'%{search}%'))

    q = q.order_by(SocialComment.platform_created_at.desc())
    return paginate_query(q, page=page, per_page=per_page)


def get_comment(district_id: str, comment_id: str) -> SocialComment:
    """Fetch a single comment within the tenant scope.

    Raises:
        ValueError: If not found.
    """
    c = SocialComment.query.filter_by(id=comment_id, district_id=district_id).first()
    if not c:
        raise ValueError('Comment not found.')
    return c


def get_replies(district_id: str, comment_id: str) -> list[SocialComment]:
    """Return all direct replies to a parent comment."""
    get_comment(district_id, comment_id)   # validates existence
    return (
        SocialComment.query
        .filter_by(district_id=district_id, parent_comment_id=comment_id)
        .order_by(SocialComment.platform_created_at.asc())
        .all()
    )


# ─────────────────────────────────────────────────────────────────────────────
# Write operations
# ─────────────────────────────────────────────────────────────────────────────

def upsert_comment(
    district_id: str,
    post_id: str,
    platform: str,
    platform_comment_id: str,
    text: str,
    parent_comment_id: str | None = None,
    author_platform_id: str | None = None,
    author_name: str | None = None,
    author_username: str | None = None,
    author_profile_url: str | None = None,
    platform_created_at: str | None = None,
    likes: int = 0,
    reply_count: int = 0,
    run_ai: bool = True,
) -> tuple[SocialComment, bool]:
    """Create or update a comment from platform data.

    Args:
        district_id:         Tenant scope.
        post_id:             FK to SocialPost.
        platform:            facebook | instagram.
        platform_comment_id: Native platform ID.
        text:                Comment body.
        parent_comment_id:   Internal FK for reply threading (optional).
        author_*:            Author info from the platform.
        platform_created_at: ISO timestamp from platform.
        likes:               Like count from platform.
        reply_count:         Reply count from platform.
        run_ai:              Whether to run AI analysis synchronously.

    Returns:
        Tuple (SocialComment, created: bool).
    """
    existing = SocialComment.query.filter_by(
        post_id=post_id, platform_comment_id=platform_comment_id
    ).first()

    if existing:
        # Update mutable engagement fields
        existing.likes       = likes
        existing.reply_count = reply_count
        existing.text        = text
        db.session.commit()
        return existing, False

    comment = SocialComment(
        id=str(uuid.uuid4()),
        district_id=district_id,
        post_id=post_id,
        parent_comment_id=parent_comment_id,
        platform=platform,
        platform_comment_id=platform_comment_id,
        text=text,
        author_platform_id=author_platform_id,
        author_name=author_name,
        author_username=author_username,
        author_profile_url=author_profile_url,
        platform_created_at=platform_created_at,
        likes=likes,
        reply_count=reply_count,
        moderation_status='visible',
        is_replied=False,
        ai_status='pending',
    )
    db.session.add(comment)
    db.session.flush()

    # Update denormalised count on the post
    _increment_post_comment_count(post_id)

    if run_ai:
        _run_ai_analysis(comment)

    db.session.commit()
    logger.info('Comment stored: %s (post=%s platform=%s)', comment.id, post_id, platform)
    return comment, True


def analyse_comment(district_id: str, comment_id: str) -> CommentAnalysis:
    """(Re-)run AI analysis on a comment and persist the result.

    Args:
        district_id: Tenant scope.
        comment_id:  UUID of the SocialComment.

    Returns:
        CommentAnalysis model instance.
    """
    comment = get_comment(district_id, comment_id)
    analysis = _run_ai_analysis(comment)
    db.session.commit()
    return analysis


def reply_to_comment(
    district_id: str,
    comment_id: str,
    reply_text: str,
    actor_id: str,
) -> SocialComment:
    """Post a reply to a comment via the platform API and record it.

    Args:
        district_id: Tenant scope.
        comment_id:  UUID of the SocialComment to reply to.
        reply_text:  Text of the reply.
        actor_id:    UUID of the staff user sending the reply.

    Returns:
        Updated SocialComment with reply fields populated.

    Raises:
        ValueError: If comment not found.
        RuntimeError: If platform publish fails.
    """
    comment = get_comment(district_id, comment_id)

    if comment.is_replied:
        raise ValueError('This comment has already been replied to.')

    post = SocialPost.query.get(comment.post_id)
    if not post:
        raise ValueError('Parent post not found.')

    # Dispatch via platform connector
    reply_platform_id = _send_platform_reply(comment, post, reply_text)

    comment.is_replied       = True
    comment.reply_text       = reply_text
    comment.reply_platform_id = reply_platform_id
    comment.replied_at       = datetime.now(timezone.utc).isoformat()
    comment.replied_by_id    = actor_id

    write_audit_log(
        district_id=district_id,
        actor_id=actor_id,
        action='social_comment.replied',
        resource_type='social_comment',
        resource_id=comment_id,
        after_state={'reply_text': reply_text[:200]},
    )
    db.session.commit()
    logger.info('Reply sent for comment %s (platform=%s)', comment_id, comment.platform)
    return comment


def moderate_comment(
    district_id: str,
    comment_id: str,
    moderation_status: str,
    actor_id: str,
    reason: str | None = None,
) -> SocialComment:
    """Change the moderation status of a comment.

    Valid statuses: visible | hidden | deleted | spam

    For Facebook / Instagram, also pushes the hide/unhide action to the
    platform API when possible.
    """
    valid = {'visible', 'hidden', 'deleted', 'spam'}
    if moderation_status not in valid:
        raise ValueError(f"moderation_status must be one of: {', '.join(sorted(valid))}")

    comment = get_comment(district_id, comment_id)
    before_status = comment.moderation_status
    comment.moderation_status = moderation_status

    # Attempt platform-level hide/unhide (best-effort, don't fail the request)
    if moderation_status in ('hidden', 'spam'):
        _try_platform_hide(comment)
    elif moderation_status == 'visible' and before_status in ('hidden', 'spam'):
        _try_platform_unhide(comment)

    write_audit_log(
        district_id=district_id,
        actor_id=actor_id,
        action='social_comment.moderated',
        resource_type='social_comment',
        resource_id=comment_id,
        before_state={'moderation_status': before_status},
        after_state={'moderation_status': moderation_status, 'reason': reason},
    )
    db.session.commit()
    return comment


def bulk_analyse(district_id: str, batch_size: int = 50) -> int:
    """Run AI analysis on all pending comments for a district.

    Args:
        district_id: Tenant scope.
        batch_size:  Max comments to process per call.

    Returns:
        Number of comments processed.
    """
    pending = (
        SocialComment.query
        .filter_by(district_id=district_id, ai_status='pending')
        .limit(batch_size)
        .all()
    )
    count = 0
    for comment in pending:
        try:
            _run_ai_analysis(comment)
            count += 1
        except Exception:
            logger.exception('AI failed for comment %s', comment.id)
            comment.ai_status = 'failed'

    if pending:
        db.session.commit()
    return count


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _run_ai_analysis(comment: SocialComment) -> CommentAnalysis:
    """Run the full AI pipeline on *comment* and persist/update CommentAnalysis."""
    start_ms = int(time.time() * 1000)

    try:
        result = ai_analyze(text=comment.text, ref_id=comment.id)

        # Sync summary fields back onto the comment for fast querying
        comment.language        = result.language
        comment.sentiment       = result.sentiment_label
        comment.sentiment_score = result.sentiment_score
        comment.is_complaint    = result.is_complaint
        comment.is_emergency    = result.is_emergency
        comment.is_spam         = result.is_spam
        comment.suggested_reply = result.suggested_reply
        comment.ai_status       = 'processed'

        elapsed = int(time.time() * 1000) - start_ms

        # Upsert CommentAnalysis
        analysis = CommentAnalysis.query.filter_by(comment_id=comment.id).first()
        if not analysis:
            analysis = CommentAnalysis(
                id=str(uuid.uuid4()),
                district_id=comment.district_id,
                comment_id=comment.id,
            )
            db.session.add(analysis)

        analysis.language             = result.language
        analysis.sentiment_label      = result.sentiment_label
        analysis.sentiment_score      = result.sentiment_score
        analysis.is_complaint         = result.is_complaint
        analysis.complaint_confidence = result.complaint_confidence
        analysis.complaint_keywords   = result.raw.get('complaint_keywords', [])
        analysis.is_emergency         = result.is_emergency
        analysis.emergency_confidence = result.emergency_confidence
        analysis.emergency_keywords   = result.raw.get('emergency_keywords', [])
        analysis.is_spam              = result.is_spam
        analysis.spam_confidence      = result.spam_confidence
        analysis.spam_reasons         = result.raw.get('spam_reasons', [])
        analysis.category             = result.category
        analysis.issue_type           = result.issue_type
        analysis.keywords             = result.keywords
        analysis.summary              = result.summary
        analysis.trend_tags           = result.trend_tags
        analysis.top_topic            = result.top_topic
        analysis.suggested_reply      = result.suggested_reply
        analysis.reply_category       = result.reply_category
        analysis.raw_result           = result.to_dict()
        analysis.status               = 'processed'
        analysis.processing_ms        = elapsed
        analysis.error_message        = None

        if result.issue_type:
            from app.services.service_request_service import create_service_request_from_social_comment
            create_service_request_from_social_comment(
                comment=comment,
                analysis=analysis,
                issue_type=result.issue_type,
            )

        return analysis

    except Exception as exc:
        comment.ai_status = 'failed'
        logger.exception('AI analysis failed for comment %s: %s', comment.id, exc)

        analysis = CommentAnalysis.query.filter_by(comment_id=comment.id).first()
        if not analysis:
            analysis = CommentAnalysis(
                id=str(uuid.uuid4()),
                district_id=comment.district_id,
                comment_id=comment.id,
            )
            db.session.add(analysis)

        analysis.status        = 'failed'
        analysis.error_message = str(exc)
        return analysis


def _increment_post_comment_count(post_id: str) -> None:
    """Increment social_comment_count on the parent post."""
    post = SocialPost.query.get(post_id)
    if post:
        post.social_comment_count = (post.social_comment_count or 0) + 1


def _send_platform_reply(
    comment: SocialComment,
    post: SocialPost,
    reply_text: str,
) -> str | None:
    """Attempt to post the reply via the platform connector.

    Returns the platform reply ID if successful, None if not (soft fail).
    """
    try:
        from app.services.social.connector_factory import ConnectorFactory
        from app.models.social_account import SocialAccount

        account = SocialAccount.query.get(post.account_id)
        if not account:
            raise RuntimeError('Social account not found for post.')

        connector = ConnectorFactory.get(account)

        if comment.platform == 'facebook':
            import requests as _requests
            page_token = account.credentials.get('page_access_token')
            if not page_token:
                raise RuntimeError('Missing page_access_token for Facebook reply.')
            resp = _requests.post(
                f'https://graph.facebook.com/v19.0/{comment.platform_comment_id}/comments',
                data={'message': reply_text, 'access_token': page_token},
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json().get('id')

        elif comment.platform == 'instagram':
            ig_id  = account.credentials.get('instagram_account_id') or account.config.get('instagram_account_id')
            token  = account.credentials.get('page_access_token')
            if not ig_id or not token:
                raise RuntimeError('Missing Instagram credentials for reply.')
            import requests as _requests
            resp = _requests.post(
                f'https://graph.facebook.com/v19.0/{comment.platform_comment_id}/replies',
                data={'message': reply_text, 'access_token': token},
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json().get('id')

        else:
            logger.warning('Reply not supported for platform: %s', comment.platform)
            return None

    except Exception as exc:
        logger.error('Platform reply failed (comment=%s): %s', comment.id, exc)
        return None


def _try_platform_hide(comment: SocialComment) -> None:
    """Best-effort: hide the comment on Facebook."""
    if comment.platform != 'facebook':
        return
    try:
        from app.models.social_post import SocialPost
        from app.models.social_account import SocialAccount
        import requests as _requests

        post    = SocialPost.query.get(comment.post_id)
        account = SocialAccount.query.get(post.account_id) if post else None
        token   = account.credentials.get('page_access_token') if account else None
        if not token:
            return
        _requests.post(
            f'https://graph.facebook.com/v19.0/{comment.platform_comment_id}',
            data={'is_hidden': True, 'access_token': token},
            timeout=10,
        )
    except Exception:
        pass   # best-effort, do not fail the request


def _try_platform_unhide(comment: SocialComment) -> None:
    """Best-effort: unhide the comment on Facebook."""
    if comment.platform != 'facebook':
        return
    try:
        from app.models.social_post import SocialPost
        from app.models.social_account import SocialAccount
        import requests as _requests

        post    = SocialPost.query.get(comment.post_id)
        account = SocialAccount.query.get(post.account_id) if post else None
        token   = account.credentials.get('page_access_token') if account else None
        if not token:
            return
        _requests.post(
            f'https://graph.facebook.com/v19.0/{comment.platform_comment_id}',
            data={'is_hidden': False, 'access_token': token},
            timeout=10,
        )
    except Exception:
        pass
