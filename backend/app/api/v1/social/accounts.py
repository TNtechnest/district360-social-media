"""Social account management endpoints.

Routes
------
GET    /api/v1/social/accounts
POST   /api/v1/social/accounts
GET    /api/v1/social/accounts/<id>
PATCH  /api/v1/social/accounts/<id>
DELETE /api/v1/social/accounts/<id>
GET    /api/v1/social/accounts/<id>/info    — fetch live account info from platform
"""
from flask import Blueprint, request, g
from flask_jwt_extended import get_jwt
from app.services.social import account_service
from app.services.social.connector_factory import ConnectorFactory
from app.services.rbac_service import require_permission
from app.utils.responses import success_response, error_response, paginated_response
from app.utils.validators import validate_pagination_params

accounts_bp = Blueprint('social_accounts', __name__, url_prefix='/accounts')


def _district():
    return get_jwt().get('district_id', '')


@accounts_bp.route('', methods=['GET'])
@require_permission('social_account', 'read')
def list_accounts():
    page, per_page = validate_pagination_params(request.args.get('page', 1), request.args.get('per_page', 20))
    pagination = account_service.get_accounts(
        _district(), page=page, per_page=per_page, platform=request.args.get('platform')
    )
    return paginated_response([a.to_dict() for a in pagination.items], pagination)


@accounts_bp.route('', methods=['POST'])
@require_permission('social_account', 'create')
def connect_account():
    data = request.get_json(silent=True) or {}
    required = ['platform', 'label', 'platform_account_id', 'credentials']
    for field in required:
        if not data.get(field):
            return error_response(f"'{field}' is required.", 400, 'VALIDATION_ERROR')
    try:
        account = account_service.connect_account(
            district_id=_district(),
            platform=data['platform'],
            label=data['label'],
            platform_account_id=data['platform_account_id'],
            credentials=data['credentials'],
            username=data.get('username'),
            config=data.get('config', {}),
            actor_id=g.current_user.id,
        )
        return success_response(data=account.to_dict(), status_code=201, message='Account connected.')
    except ValueError as exc:
        return error_response(str(exc), 400, 'VALIDATION_ERROR')


@accounts_bp.route('/<account_id>', methods=['GET'])
@require_permission('social_account', 'read')
def get_account(account_id):
    try:
        return success_response(data=account_service.get_account(_district(), account_id).to_dict())
    except ValueError as exc:
        return error_response(str(exc), 404, 'NOT_FOUND')


@accounts_bp.route('/<account_id>', methods=['PATCH'])
@require_permission('social_account', 'update')
def update_account(account_id):
    data = request.get_json(silent=True) or {}
    allowed = {'label', 'credentials', 'config', 'is_active', 'username', 'webhook_secret'}
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return error_response('No updatable fields.', 400, 'VALIDATION_ERROR')
    try:
        account = account_service.update_account(_district(), account_id, actor_id=g.current_user.id, **updates)
        return success_response(data=account.to_dict(), message='Account updated.')
    except ValueError as exc:
        return error_response(str(exc), 400, 'VALIDATION_ERROR')


@accounts_bp.route('/<account_id>', methods=['DELETE'])
@require_permission('social_account', 'delete')
def disconnect_account(account_id):
    try:
        account_service.disconnect_account(_district(), account_id, actor_id=g.current_user.id)
        return success_response(message='Account disconnected.')
    except ValueError as exc:
        return error_response(str(exc), 404, 'NOT_FOUND')


@accounts_bp.route('/<account_id>/info', methods=['GET'])
@require_permission('social_account', 'read')
def get_live_info(account_id):
    """Fetch live account info from the platform API."""
    try:
        account = account_service.get_account(_district(), account_id)
        connector = ConnectorFactory.get(account)
        info = connector.get_account_info()
        return success_response(data=info)
    except (ValueError, Exception) as exc:
        return error_response(str(exc), 400, 'PLATFORM_ERROR')
