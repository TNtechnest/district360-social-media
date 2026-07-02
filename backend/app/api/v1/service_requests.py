"""Service Request API endpoints.

Routes
------
GET    /api/v1/service-requests               — list service requests
POST   /api/v1/service-requests               — create a service request
GET    /api/v1/service-requests/<id>          — get single request
PATCH  /api/v1/service-requests/<id>          — update request fields
DELETE /api/v1/service-requests/<id>          — delete a request
POST   /api/v1/service-requests/<id>/assign   — assign to an officer
POST   /api/v1/service-requests/<id>/status   — transition status
GET    /api/v1/service-requests/<id>/comments — list comments
POST   /api/v1/service-requests/<id>/comments — add comment
GET    /api/v1/service-requests/categories    — list categories
POST   /api/v1/service-requests/categories    — create category
PATCH  /api/v1/service-requests/categories/<id> — update category
"""

import logging

from flask import Blueprint, request, g
from flask_jwt_extended import get_jwt

from app.services.service_request_service import (
    create_service_request, get_service_requests, get_service_request,
    update_service_request, delete_service_request,
    assign_service_request, transition_status,
    add_comment, get_comments,
    create_category, get_categories, update_category,
)
from app.services.rbac_service import require_permission
from app.utils.responses import success_response, error_response, paginated_response
from app.utils.validators import validate_pagination_params

logger = logging.getLogger(__name__)
sr_bp = Blueprint('service_requests', __name__, url_prefix='/service-requests')


def _district():
    return get_jwt().get('district_id', '')


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

@sr_bp.route('/categories', methods=['GET'])
@require_permission('service_request', 'read')
def list_categories():
    page, per_page = validate_pagination_params(
        request.args.get('page', 1), request.args.get('per_page', 100)
    )
    pagination = get_categories(_district(), page=page, per_page=per_page)
    return paginated_response([c.to_dict() for c in pagination.items], pagination)


@sr_bp.route('/categories', methods=['POST'])
@require_permission('service_request', 'create')
def create_category_endpoint():
    data = request.get_json(silent=True) or {}
    for field in ('name', 'code'):
        if not data.get(field):
            return error_response(f"'{field}' is required.", 400, 'VALIDATION_ERROR')
    try:
        cat = create_category(
            district_id=_district(),
            name=data['name'],
            code=data['code'],
            description=data.get('description'),
            parent_id=data.get('parent_id'),
            department_id=data.get('department_id'),
            default_priority=data.get('default_priority', 'medium'),
            sla_hours=int(data.get('sla_hours', 48)),
        )
        return success_response(data=cat.to_dict(), status_code=201, message='Category created.')
    except ValueError as exc:
        return error_response(str(exc), 400, 'VALIDATION_ERROR')


@sr_bp.route('/categories/<category_id>', methods=['PATCH'])
@require_permission('service_request', 'update')
def update_category_endpoint(category_id):
    data = {k: v for k, v in (request.get_json(silent=True) or {}).items() if v is not None}
    try:
        cat = update_category(_district(), category_id, **data)
        return success_response(data=cat.to_dict(), message='Category updated.')
    except ValueError as exc:
        return error_response(str(exc), 404, 'NOT_FOUND')


# ---------------------------------------------------------------------------
# Service Requests — CRUD
# ---------------------------------------------------------------------------

@sr_bp.route('', methods=['GET'])
@require_permission('service_request', 'read')
def list_requests():
    page, per_page = validate_pagination_params(
        request.args.get('page', 1), request.args.get('per_page', 20)
    )
    pagination = get_service_requests(
        _district(), page=page, per_page=per_page,
        status=request.args.get('status'),
        priority=request.args.get('priority'),
        category_id=request.args.get('category_id'),
        department_id=request.args.get('department_id'),
        assigned_to=request.args.get('assigned_to'),
        citizen_id=request.args.get('citizen_id'),
        ward=request.args.get('ward'),
    )
    return paginated_response([r.to_dict() for r in pagination.items], pagination)


@sr_bp.route('', methods=['POST'])
@require_permission('service_request', 'create')
def create_request():
    data = request.get_json(silent=True) or {}
    for field in ('title', 'description'):
        if not data.get(field):
            return error_response(f"'{field}' is required.", 400, 'VALIDATION_ERROR')

    try:
        req = create_service_request(
            district_id=_district(),
            category_id=data.get('category_id'),
            title=data['title'],
            description=data['description'],
            citizen_id=data.get('citizen_id') or getattr(g.current_user, 'id', None),
            citizen_phone=data.get('citizen_phone'),
            citizen_email=data.get('citizen_email'),
            priority=data.get('priority'),
            location=data.get('location'),
            ward=data.get('ward'),
            landmark=data.get('landmark'),
            tags=data.get('tags'),
            department_id=data.get('department_id'),
        )
        return success_response(data=req.to_dict(), status_code=201, message='Service request created.')
    except ValueError as exc:
        return error_response(str(exc), 400, 'VALIDATION_ERROR')


@sr_bp.route('/<request_id>', methods=['GET'])
@require_permission('service_request', 'read')
def get_request(request_id):
    try:
        req = get_service_request(_district(), request_id)
        return success_response(data=req.to_dict())
    except ValueError as exc:
        return error_response(str(exc), 404, 'NOT_FOUND')


@sr_bp.route('/<request_id>', methods=['PATCH'])
@require_permission('service_request', 'update')
def update_request(request_id):
    data = request.get_json(silent=True) or {}
    try:
        req = update_service_request(
            _district(), request_id,
            actor_id=getattr(g.current_user, 'id', None),
            **{k: v for k, v in data.items() if v is not None},
        )
        return success_response(data=req.to_dict(), message='Request updated.')
    except ValueError as exc:
        return error_response(str(exc), 400, 'VALIDATION_ERROR')


@sr_bp.route('/<request_id>', methods=['DELETE'])
@require_permission('service_request', 'delete')
def delete_request(request_id):
    try:
        delete_service_request(
            _district(), request_id,
            actor_id=getattr(g.current_user, 'id', None),
        )
        return success_response(message='Service request deleted.')
    except ValueError as exc:
        return error_response(str(exc), 404, 'NOT_FOUND')


# ---------------------------------------------------------------------------
# Assignment & Status
# ---------------------------------------------------------------------------

@sr_bp.route('/<request_id>/assign', methods=['POST'])
@require_permission('service_request', 'assign')
def assign_request(request_id):
    data = request.get_json(silent=True) or {}
    assignee_id = data.get('assignee_id', '').strip()
    if not assignee_id:
        return error_response('assignee_id is required.', 400, 'VALIDATION_ERROR')
    try:
        req = assign_service_request(
            _district(), request_id, assignee_id,
            actor_id=getattr(g.current_user, 'id', None),
        )
        return success_response(data=req.to_dict(), message='Request assigned.')
    except ValueError as exc:
        return error_response(str(exc), 400, 'VALIDATION_ERROR')


@sr_bp.route('/<request_id>/status', methods=['POST'])
@require_permission('service_request', 'update')
def change_status(request_id):
    data = request.get_json(silent=True) or {}
    new_status = data.get('status', '').strip()
    if not new_status:
        return error_response('status is required.', 400, 'VALIDATION_ERROR')
    try:
        req = transition_status(
            _district(), request_id, new_status,
            comment=data.get('comment'),
            actor_id=getattr(g.current_user, 'id', None),
        )
        return success_response(data=req.to_dict(), message=f'Status changed to {new_status}.')
    except ValueError as exc:
        return error_response(str(exc), 400, 'VALIDATION_ERROR')


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

@sr_bp.route('/<request_id>/comments', methods=['GET'])
@require_permission('service_request', 'read')
def list_comments(request_id):
    page, per_page = validate_pagination_params(
        request.args.get('page', 1), request.args.get('per_page', 50)
    )
    pagination = get_comments(_district(), request_id, page=page, per_page=per_page)
    return paginated_response([c.to_dict() for c in pagination.items], pagination)


@sr_bp.route('/<request_id>/comments', methods=['POST'])
@require_permission('service_request', 'update')
def create_comment(request_id):
    data = request.get_json(silent=True) or {}
    comment = data.get('comment', '').strip()
    if not comment:
        return error_response('comment is required.', 400, 'VALIDATION_ERROR')
    try:
        c = add_comment(
            _district(), request_id,
            author_id=getattr(g.current_user, 'id', None),
            comment=comment,
            is_internal=bool(data.get('is_internal', False)),
        )
        return success_response(data=c.to_dict(), status_code=201, message='Comment added.')
    except ValueError as exc:
        return error_response(str(exc), 404, 'NOT_FOUND')
