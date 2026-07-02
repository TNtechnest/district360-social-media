"""File Upload API endpoints.

Routes
------
POST   /api/v1/uploads                    — upload a file
GET    /api/v1/uploads                    — list attachments
GET    /api/v1/uploads/<id>               — get attachment metadata
DELETE /api/v1/uploads/<id>               — soft-delete attachment
GET    /api/v1/uploads/<id>/download      — download file
"""

import logging
import mimetypes

from flask import Blueprint, request, g, send_file
from flask_jwt_extended import get_jwt

from app.services.file_upload_service import (
    upload_file, get_attachments, get_attachment,
    delete_attachment, get_file_path,
)
from app.services.rbac_service import require_permission
from app.utils.responses import success_response, error_response, paginated_response
from app.utils.validators import validate_pagination_params

logger = logging.getLogger(__name__)
uploads_bp = Blueprint('uploads', __name__, url_prefix='/uploads')

VALID_RESOURCE_TYPES = {'service_request', 'social_post', 'report', 'profile', 'general'}


def _district():
    return get_jwt().get('district_id', '')


@uploads_bp.route('', methods=['POST'])
@require_permission('file', 'create')
def upload():
    """Upload one file.

    Multipart form data::

        resource_type:  'service_request' | 'social_post' | 'report' | 'profile' | 'general'
        resource_id:    UUID of the parent resource (optional for 'general')
        file:           The file to upload
    """
    resource_type = request.form.get('resource_type', '').strip()
    resource_id   = request.form.get('resource_id', '').strip()

    if not resource_type:
        return error_response('resource_type is required.', 400, 'VALIDATION_ERROR')
    if resource_type not in VALID_RESOURCE_TYPES:
        return error_response(f"resource_type must be one of: {', '.join(VALID_RESOURCE_TYPES)}", 400, 'VALIDATION_ERROR')
    if not resource_id and resource_type != 'general':
        return error_response('resource_id is required for this resource_type.', 400, 'VALIDATION_ERROR')

    if 'file' not in request.files:
        return error_response('No file provided. Use form field name "file".', 400, 'VALIDATION_ERROR')

    file_obj = request.files['file']
    if not file_obj.filename:
        return error_response('Empty filename.', 400, 'VALIDATION_ERROR')

    try:
        att = upload_file(
            district_id=_district(),
            resource_type=resource_type,
            resource_id=resource_id or f'general-{_district()}',
            file_obj=file_obj,
            uploaded_by=getattr(g.current_user, 'id', None),
            run_virus_scan=bool(request.form.get('scan', True)),
        )
        return success_response(data=att.to_dict(), status_code=201, message='File uploaded.')
    except ValueError as exc:
        return error_response(str(exc), 400, 'VALIDATION_ERROR')
    except Exception as exc:
        logger.exception('File upload failed')
        return error_response(str(exc), 500, 'UPLOAD_FAILED')


@uploads_bp.route('', methods=['GET'])
@require_permission('file', 'read')
def list_attachments():
    """List attachments with optional filters.

    Query params: ``page``, ``per_page``, ``resource_type``, ``resource_id``, ``file_category``.
    """
    page, per_page = validate_pagination_params(
        request.args.get('page', 1), request.args.get('per_page', 20)
    )
    pagination = get_attachments(
        _district(),
        resource_type=request.args.get('resource_type'),
        resource_id=request.args.get('resource_id'),
        file_category=request.args.get('file_category'),
        page=page, per_page=per_page,
    )
    return paginated_response([a.to_dict() for a in pagination.items], pagination)


@uploads_bp.route('/<attachment_id>', methods=['GET'])
@require_permission('file', 'read')
def get_attachment_meta(attachment_id):
    try:
        att = get_attachment(_district(), attachment_id)
        return success_response(data=att.to_dict())
    except ValueError as exc:
        return error_response(str(exc), 404, 'NOT_FOUND')


@uploads_bp.route('/<attachment_id>', methods=['DELETE'])
@require_permission('file', 'delete')
def remove_attachment(attachment_id):
    try:
        delete_attachment(
            _district(), attachment_id,
            actor_id=getattr(g.current_user, 'id', None),
        )
        return success_response(message='Attachment deleted.')
    except ValueError as exc:
        return error_response(str(exc), 404, 'NOT_FOUND')


@uploads_bp.route('/<attachment_id>/download', methods=['GET'])
@require_permission('file', 'read')
def download_attachment(attachment_id):
    try:
        file_path = get_file_path(_district(), attachment_id)
        att = get_attachment(_district(), attachment_id)
        mime_type = att.mime_type or mimetypes.guess_type(att.original_filename)[0] or 'application/octet-stream'
        return send_file(
            file_path,
            mimetype=mime_type,
            as_attachment=True,
            download_name=att.original_filename,
        )
    except ValueError as exc:
        return error_response(str(exc), 404, 'NOT_FOUND')
