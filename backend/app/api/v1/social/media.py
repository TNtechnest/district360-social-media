"""Media library endpoints.

Routes
------
GET    /api/v1/social/media
POST   /api/v1/social/media
GET    /api/v1/social/media/<id>
PATCH  /api/v1/social/media/<id>
DELETE /api/v1/social/media/<id>
"""
from flask import Blueprint, request, g
from flask_jwt_extended import get_jwt
from app.services.social import media_service
from app.services.rbac_service import require_permission
from app.utils.responses import success_response, error_response, paginated_response
from app.utils.validators import validate_pagination_params

media_bp = Blueprint('social_media', __name__, url_prefix='/media')


def _district():
    return get_jwt().get('district_id', '')


@media_bp.route('', methods=['GET'])
@require_permission('media', 'read')
def list_media():
    page, per_page = validate_pagination_params(request.args.get('page', 1), request.args.get('per_page', 20))
    pagination = media_service.get_media(
        _district(), page=page, per_page=per_page,
        media_type=request.args.get('media_type'),
        folder=request.args.get('folder'),
        search=request.args.get('search'),
    )
    return paginated_response([m.to_dict() for m in pagination.items], pagination)


@media_bp.route('', methods=['POST'])
@require_permission('media', 'create')
def add_media():
    """Register a media asset that was uploaded to object storage.

    Request body (JSON)::

        {
          "filename": "banner.jpg",
          "url": "https://storage.example.com/...",
          "media_type": "image",
          "mime_type": "image/jpeg",
          "file_size": 204800,
          "alt_text": "District banner",
          "folder": "/banners",
          "tags": ["banner", "2026"]
        }
    """
    data = request.get_json(silent=True) or {}
    for field in ('filename', 'url', 'media_type'):
        if not data.get(field):
            return error_response(f"'{field}' is required.", 400, 'VALIDATION_ERROR')
    item = media_service.add_media_item(
        district_id=_district(),
        filename=data['filename'],
        url=data['url'],
        media_type=data['media_type'],
        uploaded_by=g.current_user.id,
        mime_type=data.get('mime_type'),
        file_size=data.get('file_size', 0),
        alt_text=data.get('alt_text'),
        folder=data.get('folder', '/'),
        tags=data.get('tags', []),
        width=data.get('width'),
        height=data.get('height'),
        thumbnail_url=data.get('thumbnail_url'),
    )
    return success_response(data=item.to_dict(), status_code=201, message='Media item added.')


@media_bp.route('/<item_id>', methods=['GET'])
@require_permission('media', 'read')
def get_media_item(item_id):
    try:
        return success_response(data=media_service.get_media_item(_district(), item_id).to_dict())
    except ValueError as exc:
        return error_response(str(exc), 404, 'NOT_FOUND')


@media_bp.route('/<item_id>', methods=['PATCH'])
@require_permission('media', 'update')
def update_media(item_id):
    data = request.get_json(silent=True) or {}
    allowed = {'alt_text', 'folder', 'tags', 'thumbnail_url'}
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return error_response('No updatable fields.', 400, 'VALIDATION_ERROR')
    try:
        item = media_service.update_media_item(_district(), item_id, **updates)
        return success_response(data=item.to_dict(), message='Media item updated.')
    except ValueError as exc:
        return error_response(str(exc), 400, 'VALIDATION_ERROR')


@media_bp.route('/<item_id>', methods=['DELETE'])
@require_permission('media', 'delete')
def delete_media(item_id):
    try:
        media_service.soft_delete_media(_district(), item_id)
        return success_response(message='Media item deleted.')
    except ValueError as exc:
        return error_response(str(exc), 404, 'NOT_FOUND')
