"""Scheduling engine endpoints.

Routes
------
GET    /api/v1/social/schedules
POST   /api/v1/social/schedules
GET    /api/v1/social/schedules/<id>
PATCH  /api/v1/social/schedules/<id>
DELETE /api/v1/social/schedules/<id>
POST   /api/v1/social/schedules/run     — manually trigger due schedules
"""
from flask import Blueprint, request, g
from flask_jwt_extended import get_jwt
from app.services.social import schedule_service
from app.services.rbac_service import require_permission
from app.utils.responses import success_response, error_response, paginated_response
from app.utils.validators import validate_pagination_params

schedules_bp = Blueprint('social_schedules', __name__, url_prefix='/schedules')


def _district():
    return get_jwt().get('district_id', '')


@schedules_bp.route('', methods=['GET'])
@require_permission('schedule', 'read')
def list_schedules():
    page, per_page = validate_pagination_params(request.args.get('page', 1), request.args.get('per_page', 20))
    pagination = schedule_service.get_schedules(_district(), page, per_page, request.args.get('status'))
    return paginated_response([s.to_dict() for s in pagination.items], pagination)


@schedules_bp.route('', methods=['POST'])
@require_permission('schedule', 'create')
def create_schedule():
    data = request.get_json(silent=True) or {}
    for field in ('account_id', 'name', 'content_template', 'next_run_at'):
        if not data.get(field):
            return error_response(f"'{field}' is required.", 400, 'VALIDATION_ERROR')
    try:
        schedule = schedule_service.create_schedule(
            district_id=_district(),
            account_id=data['account_id'],
            name=data['name'],
            content_template=data['content_template'],
            next_run_at=data['next_run_at'],
            recurrence=data.get('recurrence', 'one_off'),
            cron_expression=data.get('cron_expression'),
            timezone_str=data.get('timezone', 'Asia/Kolkata'),
            meta=data.get('meta', {}),
            author_id=g.current_user.id,
        )
        return success_response(data=schedule.to_dict(), status_code=201, message='Schedule created.')
    except ValueError as exc:
        return error_response(str(exc), 400, 'VALIDATION_ERROR')


@schedules_bp.route('/<schedule_id>', methods=['GET'])
@require_permission('schedule', 'read')
def get_schedule(schedule_id):
    try:
        return success_response(data=schedule_service.get_schedule(_district(), schedule_id).to_dict())
    except ValueError as exc:
        return error_response(str(exc), 404, 'NOT_FOUND')


@schedules_bp.route('/<schedule_id>', methods=['PATCH'])
@require_permission('schedule', 'update')
def update_schedule(schedule_id):
    data = request.get_json(silent=True) or {}
    allowed = {'name', 'content_template', 'next_run_at', 'cron_expression', 'timezone', 'is_active', 'meta', 'status'}
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return error_response('No updatable fields.', 400, 'VALIDATION_ERROR')
    try:
        schedule = schedule_service.update_schedule(_district(), schedule_id, **updates)
        return success_response(data=schedule.to_dict(), message='Schedule updated.')
    except ValueError as exc:
        return error_response(str(exc), 400, 'VALIDATION_ERROR')


@schedules_bp.route('/<schedule_id>', methods=['DELETE'])
@require_permission('schedule', 'delete')
def delete_schedule(schedule_id):
    try:
        schedule_service.delete_schedule(_district(), schedule_id)
        return success_response(message='Schedule deleted.')
    except ValueError as exc:
        return error_response(str(exc), 404, 'NOT_FOUND')


@schedules_bp.route('/run', methods=['POST'])
@require_permission('schedule', 'update')
def run_schedules():
    """Manually trigger all due schedules (for testing / admin use)."""
    count = schedule_service.run_due_schedules()
    return success_response(data={'triggered': count}, message=f'{count} schedule(s) triggered.')
