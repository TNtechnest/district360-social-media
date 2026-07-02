"""Social comment endpoints.

Routes
------
GET    /api/v1/social/comments                   — list all comments in district
GET    /api/v1/social/posts/<post_id>/comments   — list comments on one post
POST   /api/v1/social/posts/<post_id>/comments   — ingest a comment (webhook / manual)
GET    /api/v1/social/comments/<id>              — get single comment + analysis
GET    /api/v1/social/comments/<id>/replies      — get replies to a comment
POST   /api/v1/social/comments/<id>/reply        — send a staff reply
POST   /api/v1/social/comments/<id>/moderate     — moderate (hide / spam / visible)
POST   /api/v1/social/comments/<id>/analyse      — re-run AI analysis
POST   /api/v1/social/comments/analyse           — bulk AI analysis (pending batch)
POST   /api/v1/social/posts/<post_id>/sync-comments — sync comments from platform
"""
import logging

from flask import Blueprint, request, g
from flask_jwt_extended import get_jwt

from app.services.social import comment_service
from app.services.rbac_service import require_permission
from app.schemas.social_comment_schema import (
    SocialCommentSchema,
    SocialCommentListSchema,
    CommentAnalysisSchema,
    CreateCommentSchema,
    ReplyCommentSchema,
    ModerateCommentSchema,
)
from app.utils.responses import success_response, error_response, paginated_response
from app.utils.validators import validate_pagination_params
from marshmallow import ValidationError

logger = logging.getLogger(__name__)
comments_bp = Blueprint('social_comments', __name__)

_comment_schema      = SocialCommentSchema()
_comment_list_schema = SocialCommentListSchema()
_analysis_schema     = CommentAnalysisSchema()
_create_schema       = CreateCommentSchema()
_reply_schema        = ReplyCommentSchema()
_moderate_schema     = ModerateCommentSchema()


def _district() -> str:
    return get_jwt().get('district_id', '')


def _bool_param(key: str) -> bool | None:
    v = request.args.get(key)
    if v is None:
        return None
    return v.lower() in ('1', 'true', 'yes')


# ─────────────────────────────────────────────────────────────────────────────
# List all comments in the district
# ─────────────────────────────────────────────────────────────────────────────

@comments_bp.route('/comments', methods=['GET'])
@require_permission('social_comment', 'read')
def list_all_comments():
    """List all comments in the caller's district (paginated, filterable).

    Query params: ``page``, ``per_page``, ``post_id``, ``platform``,
    ``sentiment``, ``is_complaint``, ``is_emergency``, ``is_spam``,
    ``moderation_status``, ``is_replied``, ``parent_only``, ``search``.
    """
    page, per_page = validate_pagination_params(
        request.args.get('page', 1), request.args.get('per_page', 30)
    )
    parent_only = request.args.get('parent_only', 'true').lower() != 'false'

    pagination = comment_service.get_comments(
        district_id=_district(),
        post_id=request.args.get('post_id'),
        page=page,
        per_page=per_page,
        platform=request.args.get('platform'),
        sentiment=request.args.get('sentiment'),
        is_complaint=_bool_param('is_complaint'),
        is_emergency=_bool_param('is_emergency'),
        is_spam=_bool_param('is_spam'),
        moderation_status=request.args.get('moderation_status'),
        is_replied=_bool_param('is_replied'),
        parent_only=parent_only,
        search=request.args.get('search'),
    )
    return paginated_response(
        [c.to_dict() for c in pagination.items], pagination
    )


# ─────────────────────────────────────────────────────────────────────────────
# Comments scoped to one post
# ─────────────────────────────────────────────────────────────────────────────

@comments_bp.route('/posts/<post_id>/comments', methods=['GET'])
@require_permission('social_comment', 'read')
def list_post_comments(post_id: str):
    """List comments on a specific post.

    Query params: same as list_all_comments (post_id is forced from URL).
    """
    page, per_page = validate_pagination_params(
        request.args.get('page', 1), request.args.get('per_page', 30)
    )
    parent_only = request.args.get('parent_only', 'true').lower() != 'false'

    pagination = comment_service.get_comments(
        district_id=_district(),
        post_id=post_id,
        page=page,
        per_page=per_page,
        platform=request.args.get('platform'),
        sentiment=request.args.get('sentiment'),
        is_complaint=_bool_param('is_complaint'),
        is_emergency=_bool_param('is_emergency'),
        is_spam=_bool_param('is_spam'),
        moderation_status=request.args.get('moderation_status'),
        is_replied=_bool_param('is_replied'),
        parent_only=parent_only,
        search=request.args.get('search'),
    )
    return paginated_response(
        [c.to_dict() for c in pagination.items], pagination
    )


@comments_bp.route('/posts/<post_id>/comments', methods=['POST'])
@require_permission('social_comment', 'create')
def ingest_comment(post_id: str):
    """Ingest a comment from a platform webhook or manual sync.

    Request body (JSON)::

        {
          "platform":            "facebook",
          "platform_comment_id": "12345_67890",
          "text":                "Great post!",
          "author_name":         "Jane Citizen",
          "platform_created_at": "2026-06-27T10:00:00+0000",
          "likes":               3
        }
    """
    data = request.get_json(silent=True) or {}
    data['post_id'] = post_id   # enforce from URL

    try:
        validated = _create_schema.load(data)
    except ValidationError as err:
        return error_response('Validation failed.', 400, 'VALIDATION_ERROR',
                              details=err.messages)

    comment, created = comment_service.upsert_comment(
        district_id=_district(),
        post_id=validated['post_id'],
        platform=validated['platform'],
        platform_comment_id=validated['platform_comment_id'],
        text=validated['text'],
        parent_comment_id=validated.get('parent_comment_id'),
        author_platform_id=validated.get('author_platform_id'),
        author_name=validated.get('author_name'),
        author_username=validated.get('author_username'),
        author_profile_url=validated.get('author_profile_url'),
        platform_created_at=validated.get('platform_created_at'),
        likes=validated.get('likes', 0),
        reply_count=validated.get('reply_count', 0),
        run_ai=True,
    )
    status_code = 201 if created else 200
    message = 'Comment stored.' if created else 'Comment updated.'
    return success_response(data=comment.to_dict(), status_code=status_code, message=message)


# ─────────────────────────────────────────────────────────────────────────────
# Single comment operations
# ─────────────────────────────────────────────────────────────────────────────

@comments_bp.route('/comments/<comment_id>', methods=['GET'])
@require_permission('social_comment', 'read')
def get_comment(comment_id: str):
    """Get a single comment with full AI analysis."""
    try:
        comment = comment_service.get_comment(_district(), comment_id)
        return success_response(data=comment.to_dict(include_analysis=True))
    except ValueError as exc:
        return error_response(str(exc), 404, 'NOT_FOUND')


@comments_bp.route('/comments/<comment_id>/replies', methods=['GET'])
@require_permission('social_comment', 'read')
def get_replies(comment_id: str):
    """Get all direct replies to a comment."""
    try:
        replies = comment_service.get_replies(_district(), comment_id)
        return success_response(data=[r.to_dict() for r in replies])
    except ValueError as exc:
        return error_response(str(exc), 404, 'NOT_FOUND')


@comments_bp.route('/comments/<comment_id>/reply', methods=['POST'])
@require_permission('social_comment', 'reply')
def reply_comment(comment_id: str):
    """Send a staff reply to a comment via the platform API.

    Request body (JSON)::

        { "reply_text": "Thank you for your feedback. We will fix it soon." }
    """
    data = request.get_json(silent=True) or {}
    try:
        validated = _reply_schema.load(data)
    except ValidationError as err:
        return error_response('Validation failed.', 400, 'VALIDATION_ERROR',
                              details=err.messages)
    try:
        comment = comment_service.reply_to_comment(
            district_id=_district(),
            comment_id=comment_id,
            reply_text=validated['reply_text'],
            actor_id=g.current_user.id,
        )
        return success_response(data=comment.to_dict(), message='Reply sent.')
    except ValueError as exc:
        return error_response(str(exc), 400, 'VALIDATION_ERROR')
    except RuntimeError as exc:
        return error_response(str(exc), 502, 'PLATFORM_ERROR')


@comments_bp.route('/comments/<comment_id>/moderate', methods=['POST'])
@require_permission('social_comment', 'moderate')
def moderate_comment(comment_id: str):
    """Update the moderation status of a comment.

    Request body (JSON)::

        {
          "moderation_status": "hidden",
          "reason":            "Abusive language"
        }
    """
    data = request.get_json(silent=True) or {}
    try:
        validated = _moderate_schema.load(data)
    except ValidationError as err:
        return error_response('Validation failed.', 400, 'VALIDATION_ERROR',
                              details=err.messages)
    try:
        comment = comment_service.moderate_comment(
            district_id=_district(),
            comment_id=comment_id,
            moderation_status=validated['moderation_status'],
            actor_id=g.current_user.id,
            reason=validated.get('reason'),
        )
        return success_response(data=comment.to_dict(), message='Moderation status updated.')
    except ValueError as exc:
        return error_response(str(exc), 400, 'VALIDATION_ERROR')


@comments_bp.route('/comments/<comment_id>/analyse', methods=['POST'])
@require_permission('social_comment', 'update')
def analyse_single(comment_id: str):
    """Re-run AI analysis on a specific comment."""
    try:
        analysis = comment_service.analyse_comment(_district(), comment_id)
        return success_response(data=analysis.to_dict(), message='Analysis complete.')
    except ValueError as exc:
        return error_response(str(exc), 404, 'NOT_FOUND')


@comments_bp.route('/comments/analyse', methods=['POST'])
@require_permission('social_comment', 'update')
def bulk_analyse():
    """Run AI analysis on all pending comments in this district.

    Request body (JSON, optional)::

        { "batch_size": 100 }
    """
    data = request.get_json(silent=True) or {}
    batch_size = min(int(data.get('batch_size', 50)), 200)
    count = comment_service.bulk_analyse(_district(), batch_size=batch_size)
    return success_response(
        data={'processed': count},
        message=f'{count} comment(s) analysed.',
    )


# ─────────────────────────────────────────────────────────────────────────────
# Platform sync
# ─────────────────────────────────────────────────────────────────────────────

@comments_bp.route('/posts/<post_id>/sync-comments', methods=['POST'])
@require_permission('social_comment', 'create')
def sync_comments(post_id: str):
    """Sync comments from the platform for a published post.

    Reads the platform (facebook | instagram) from the associated SocialPost
    and calls the appropriate connector's ``sync_post_comments`` method.

    Request body (JSON, optional)::

        { "limit": 100 }
    """
    from app.models.social_post import SocialPost
    from app.models.social_account import SocialAccount
    from app.services.social.connector_factory import ConnectorFactory

    data  = request.get_json(silent=True) or {}
    limit = min(int(data.get('limit', 100)), 500)

    post = SocialPost.query.filter_by(id=post_id, district_id=_district()).first()
    if not post:
        return error_response('Post not found.', 404, 'NOT_FOUND')
    if post.status != 'published':
        return error_response(
            f"Post status is '{post.status}' — only published posts can be synced.",
            400, 'VALIDATION_ERROR',
        )
    if not post.platform_post_id:
        return error_response('Post has no platform_post_id — publish it first.', 400, 'VALIDATION_ERROR')

    account = SocialAccount.query.get(post.account_id)
    if not account:
        return error_response('Social account not found.', 404, 'NOT_FOUND')

    try:
        connector = ConnectorFactory.get(account)
        if not hasattr(connector, 'sync_post_comments'):
            return error_response(
                f"Comment sync is not supported for platform '{post.platform}'.",
                400, 'NOT_SUPPORTED',
            )
        new_count = connector.sync_post_comments(
            post_id=post.id,
            platform_post_id=post.platform_post_id,
            district_id=_district(),
            limit=limit,
        )
        return success_response(
            data={'new_comments': new_count, 'post_id': post_id},
            message=f'{new_count} new comment(s) synced.',
        )
    except Exception as exc:
        logger.exception('Comment sync failed for post %s', post_id)
        return error_response(str(exc), 502, 'PLATFORM_ERROR')
