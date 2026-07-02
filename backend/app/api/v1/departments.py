"""Department management endpoints.

All routes are tenant-scoped via the caller's JWT district_id claim.

Routes
------
GET    /api/v1/departments          — list departments
POST   /api/v1/departments          — create a department
GET    /api/v1/departments/<id>     — get department detail
PATCH  /api/v1/departments/<id>     — update department
DELETE /api/v1/departments/<id>     — deactivate department
"""
import logging

from flask import Blueprint, request, g
from flask_jwt_extended import get_jwt

from app.services import department_service
from app.services.rbac_service import require_permission
from app.utils.responses import success_response, error_response, paginated_response
from app.utils.validators import validate_pagination_params

logger = logging.getLogger(__name__)
departments_bp = Blueprint('departments', __name__, url_prefix='/departments')


def _caller_district_id() -> str:
    return get_jwt().get('district_id', '')


@departments_bp.route('', methods=['GET'])
@require_permission('department', 'read')
def list_departments():
    """List departments in the caller's district (paginated).

    Query params: ``page``, ``per_page``, ``status``, ``search``.
    """
    district_id = _caller_district_id()
    page, per_page = validate_pagination_params(
        request.args.get('page', 1),
        request.args.get('per_page', 20),
    )
    pagination = department_service.get_departments(
        district_id=district_id,
        page=page,
        per_page=per_page,
        status=request.args.get('status'),
        search=request.args.get('search'),
    )
    return paginated_response(
        [d.to_dict() for d in pagination.items],
        pagination,
    )


@departments_bp.route('', methods=['POST'])
@require_permission('department', 'create')
def create_department():
    """Create a new department.

    Request body (JSON)::

        {
          "name": "Water & Sanitation",
          "code": "WATER",
          "description": "Manages water supply and sewage.",
          "wards": ["north-ward", "south-ward"],
          "head_id": "<user_uuid>"
        }
    """
    district_id = _caller_district_id()
    data = request.get_json(silent=True) or {}

    name        = data.get('name', '').strip()
    code        = data.get('code', '').strip()
    description = data.get('description')
    wards       = data.get('wards', [])
    head_id     = data.get('head_id')

    if not name:
        return error_response('name is required.', 400, 'VALIDATION_ERROR')
    if not code:
        return error_response('code is required.', 400, 'VALIDATION_ERROR')

    try:
        dept = department_service.create_department(
            district_id=district_id,
            name=name,
            code=code,
            description=description,
            wards=wards,
            head_id=head_id,
            actor_id=g.current_user.id,
        )
        return success_response(data=dept.to_dict(), status_code=201, message='Department created.')
    except ValueError as exc:
        return error_response(str(exc), 400, 'VALIDATION_ERROR')


@departments_bp.route('/<department_id>', methods=['GET'])
@require_permission('department', 'read')
def get_department(department_id):
    """Get department details by ID."""
    district_id = _caller_district_id()
    try:
        dept = department_service.get_department_by_id(district_id, department_id)
        return success_response(data=dept.to_dict())
    except ValueError as exc:
        return error_response(str(exc), 404, 'NOT_FOUND')


@departments_bp.route('/<department_id>', methods=['PATCH'])
@require_permission('department', 'update')
def update_department(department_id):
    """Update department fields (name, description, wards, head_id, status).

    Request body (JSON): supply only the fields you want to change.
    """
    district_id = _caller_district_id()
    data = request.get_json(silent=True) or {}
    allowed_keys = {'name', 'description', 'wards', 'head_id', 'status'}
    updates = {k: v for k, v in data.items() if k in allowed_keys}

    if not updates:
        return error_response('No updatable fields provided.', 400, 'VALIDATION_ERROR')

    try:
        dept = department_service.update_department(
            district_id, department_id, actor_id=g.current_user.id, **updates
        )
        return success_response(data=dept.to_dict(), message='Department updated.')
    except ValueError as exc:
        return error_response(str(exc), 400, 'VALIDATION_ERROR')


@departments_bp.route('/<department_id>', methods=['DELETE'])
@require_permission('department', 'delete')
def deactivate_department(department_id):
    """Deactivate a department (soft delete)."""
    district_id = _caller_district_id()
    try:
        dept = department_service.deactivate_department(
            district_id, department_id, actor_id=g.current_user.id
        )
        return success_response(data=dept.to_dict(), message='Department deactivated.')
    except ValueError as exc:
        return error_response(str(exc), 404, 'NOT_FOUND')
