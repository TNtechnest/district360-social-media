"""District management endpoints (Super Admin only).

Routes
------
GET  /api/v1/districts            — list all districts
POST /api/v1/districts            — create a district
GET  /api/v1/districts/<id>       — get district detail
PATCH /api/v1/districts/<id>      — update district
DELETE /api/v1/districts/<id>     — deactivate district
"""
import logging

from flask import Blueprint, request, g
from flask_jwt_extended import get_jwt

from app.services import district_service
from app.services.rbac_service import require_permission
from app.utils.responses import success_response, error_response, paginated_response
from app.utils.validators import validate_pagination_params

logger = logging.getLogger(__name__)
districts_bp = Blueprint('districts', __name__, url_prefix='/districts')


@districts_bp.route('', methods=['GET'])
@require_permission('district', 'read')
def list_districts():
    """List all districts (paginated).

    Query params: ``page``, ``per_page``, ``status``, ``search``.
    """
    page, per_page = validate_pagination_params(
        request.args.get('page', 1),
        request.args.get('per_page', 20),
    )
    pagination = district_service.get_districts(
        page=page,
        per_page=per_page,
        status=request.args.get('status'),
        search=request.args.get('search'),
    )
    return paginated_response(
        [d.to_dict() for d in pagination.items],
        pagination,
    )


@districts_bp.route('', methods=['POST'])
@require_permission('district', 'create')
def create_district():
    """Create a new district tenant.

    Request body (JSON)::

        {
          "name": "Metro North District",
          "slug": "metro-north",
          "region": "Northern Province",
          "config": {}
        }
    """
    data = request.get_json(silent=True) or {}
    name   = data.get('name', '').strip()
    slug   = data.get('slug', '').strip()
    region = data.get('region')
    config = data.get('config', {})

    if not name:
        return error_response('name is required.', 400, 'VALIDATION_ERROR')
    if not slug:
        return error_response('slug is required.', 400, 'VALIDATION_ERROR')

    try:
        district = district_service.create_district(
            name=name,
            slug=slug,
            region=region,
            config=config,
            actor_id=g.current_user.id,
        )
        return success_response(data=district.to_dict(), status_code=201, message='District created.')
    except ValueError as exc:
        return error_response(str(exc), 400, 'VALIDATION_ERROR')


@districts_bp.route('/<district_id>', methods=['GET'])
@require_permission('district', 'read')
def get_district(district_id):
    """Get district details by ID."""
    try:
        district = district_service.get_district_by_id(district_id)
        return success_response(data=district.to_dict())
    except ValueError as exc:
        return error_response(str(exc), 404, 'NOT_FOUND')


@districts_bp.route('/<district_id>', methods=['PATCH'])
@require_permission('district', 'update')
def update_district(district_id):
    """Update district fields (name, region, config, status).

    Request body (JSON): supply only the fields you want to change.
    """
    data = request.get_json(silent=True) or {}
    allowed_keys = {'name', 'region', 'config', 'status'}
    updates = {k: v for k, v in data.items() if k in allowed_keys}

    if not updates:
        return error_response('No updatable fields provided.', 400, 'VALIDATION_ERROR')

    try:
        district = district_service.update_district(
            district_id, actor_id=g.current_user.id, **updates
        )
        return success_response(data=district.to_dict(), message='District updated.')
    except ValueError as exc:
        return error_response(str(exc), 400, 'VALIDATION_ERROR')


@districts_bp.route('/<district_id>', methods=['DELETE'])
@require_permission('district', 'delete')
def deactivate_district(district_id):
    """Deactivate a district (soft delete — sets status to inactive)."""
    try:
        district = district_service.deactivate_district(district_id, actor_id=g.current_user.id)
        return success_response(data=district.to_dict(), message='District deactivated.')
    except ValueError as exc:
        return error_response(str(exc), 404, 'NOT_FOUND')
