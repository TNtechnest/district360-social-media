"""Content management endpoints.

Routes
------
GET    /api/v1/social/posts
POST   /api/v1/social/posts
GET    /api/v1/social/posts/<id>
PATCH  /api/v1/social/posts/<id>
DELETE /api/v1/social/posts/<id>
POST   /api/v1/social/posts/<id>/publish
"""
from flask import Blueprint, request, g
from flask_jwt_extended import get_jwt
from app.services.social import content_service
from app.services.rbac_service import require_permission
from app.utils.responses import success_response, error_response, paginated_response
from app.utils.validators import validate_pagination_params

content_bp = Blueprint('social_content', __name__, url_prefix='/posts')


def _district():
    return get_jwt().get('district_id', '')


@content_bp.route('', methods=['GET'])
@require_permission('social_post', 'read')
def list_posts():
    page, per_page = validate_pagination_params(request.args.get('page', 1), request.args.get('per_page', 20))
    pagination = content_service.get_posts(
        _district(), page=page, per_page=per_page,
        status=request.args.get('status'),
        platform=request.args.get('platform'),
        account_id=request.args.get('account_id'),
    )
    return paginated_response([p.to_dict() for p in pagination.items], pagination)


@content_bp.route('', methods=['POST'])
@require_permission('social_post', 'create')
def create_post():
    data = request.get_json(silent=True) or {}
    if not data.get('account_id'):
        return error_response('account_id is required.', 400, 'VALIDATION_ERROR')
    if not data.get('content', '').strip():
        return error_response('content is required.', 400, 'VALIDATION_ERROR')
    try:
        post = content_service.create_draft(
            district_id=_district(),
            account_id=data['account_id'],
            content=data['content'],
            author_id=g.current_user.id,
            scheduled_at=data.get('scheduled_at'),
            meta=data.get('meta', {}),
            media_ids=data.get('media_ids', []),
        )
        return success_response(data=post.to_dict(), status_code=201, message='Post created.')
    except ValueError as exc:
        return error_response(str(exc), 400, 'VALIDATION_ERROR')


@content_bp.route('/<post_id>', methods=['GET'])
@require_permission('social_post', 'read')
def get_post(post_id):
    try:
        return success_response(data=content_service.get_post(_district(), post_id).to_dict())
    except ValueError as exc:
        return error_response(str(exc), 404, 'NOT_FOUND')


@content_bp.route('/<post_id>', methods=['PATCH'])
@require_permission('social_post', 'update')
def update_post(post_id):
    data = request.get_json(silent=True) or {}
    allowed = {'content', 'scheduled_at', 'meta', 'status'}
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return error_response('No updatable fields.', 400, 'VALIDATION_ERROR')
    try:
        post = content_service.update_post(_district(), post_id, actor_id=g.current_user.id, **updates)
        return success_response(data=post.to_dict(), message='Post updated.')
    except ValueError as exc:
        return error_response(str(exc), 400, 'VALIDATION_ERROR')


@content_bp.route('/<post_id>', methods=['DELETE'])
@require_permission('social_post', 'delete')
def delete_post(post_id):
    try:
        content_service.delete_post(_district(), post_id, actor_id=g.current_user.id)
        return success_response(message='Post deleted.')
    except ValueError as exc:
        return error_response(str(exc), 400, 'VALIDATION_ERROR')


@content_bp.route('/<post_id>/publish', methods=['POST'])
@require_permission('social_post', 'publish')
def publish_post(post_id):
    try:
        post = content_service.publish_now(_district(), post_id, actor_id=g.current_user.id)
        if post.status == 'published':
            return success_response(data=post.to_dict(), message='Post published successfully.')
        return error_response(post.error_message or 'Publish failed.', 502, 'PUBLISH_FAILED')
    except ValueError as exc:
        return error_response(str(exc), 400, 'VALIDATION_ERROR')
