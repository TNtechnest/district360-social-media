"""Notification API endpoints.

Routes
------
GET  /api/v1/notifications               — list sent notifications
POST /api/v1/notifications/send          — send a notification manually
GET  /api/v1/notifications/templates     — list notification templates
POST /api/v1/notifications/templates     — create/update a template
"""
import logging

from flask import Blueprint, request, g
from flask_jwt_extended import get_jwt

from app.services.notifications.notification_service import (
    send_notification, get_notifications, get_templates, upsert_template,
)
from app.services.rbac_service import require_permission
from app.utils.responses import success_response, error_response, paginated_response
from app.utils.validators import validate_pagination_params

logger = logging.getLogger(__name__)
notifications_bp = Blueprint('notifications', __name__, url_prefix='/notifications')

VALID_CHANNELS = {'email', 'sms', 'whatsapp', 'push'}


def _district():
    return get_jwt().get('district_id', '')


@notifications_bp.route('', methods=['GET'])
@require_permission('notification', 'read')
def list_notifications():
    """List notification delivery records.

    Query params: ``page``, ``per_page``, ``channel``, ``status``, ``user_id``.
    """
    page, per_page = validate_pagination_params(
        request.args.get('page', 1), request.args.get('per_page', 20)
    )
    pagination = get_notifications(
        _district(), page=page, per_page=per_page,
        channel=request.args.get('channel'),
        status=request.args.get('status'),
        user_id=request.args.get('user_id'),
    )
    return paginated_response([n.to_dict() for n in pagination.items], pagination)


@notifications_bp.route('/send', methods=['POST'])
@require_permission('notification', 'create')
def send():
    """Send a notification manually.

    Request body (JSON)::

        {
          "channel": "email",
          "recipient": "user@example.com",
          "event_key": "approval.submitted",
          "variables": {"ref_id": "APP-001", "resource": "social post"},
          "user_id": "<optional-user-uuid>",
          "subject": "Override subject (optional)",
          "body": "Override body (optional — used if no template exists)"
        }
    """
    data = request.get_json(silent=True) or {}

    channel   = data.get('channel', '').strip()
    recipient = data.get('recipient', '').strip()
    event_key = data.get('event_key', '').strip()

    if not channel:
        return error_response('channel is required.', 400, 'VALIDATION_ERROR')
    if channel not in VALID_CHANNELS:
        return error_response(
            f"channel must be one of: {', '.join(VALID_CHANNELS)}",
            400, 'VALIDATION_ERROR',
        )
    if not recipient:
        return error_response('recipient is required.', 400, 'VALIDATION_ERROR')
    if not event_key:
        return error_response('event_key is required.', 400, 'VALIDATION_ERROR')

    try:
        notif = send_notification(
            district_id=_district(),
            channel=channel,
            recipient=recipient,
            event_key=event_key,
            variables=data.get('variables', {}),
            user_id=data.get('user_id'),
            subject=data.get('subject'),
            body=data.get('body'),
        )
        return success_response(
            data=notif.to_dict(),
            status_code=201,
            message=f'Notification {notif.status}.',
        )
    except ValueError as exc:
        return error_response(str(exc), 400, 'VALIDATION_ERROR')
    except Exception as exc:
        logger.exception('Notification send failed')
        return error_response(str(exc), 500, 'NOTIFICATION_FAILED')


@notifications_bp.route('/templates', methods=['GET'])
@require_permission('notification', 'read')
def list_templates():
    """List all notification templates for the district."""
    page, per_page = validate_pagination_params(
        request.args.get('page', 1), request.args.get('per_page', 20)
    )
    pagination = get_templates(_district(), page=page, per_page=per_page)
    return paginated_response([t.to_dict() for t in pagination.items], pagination)


@notifications_bp.route('/templates', methods=['POST'])
@require_permission('notification', 'create')
def create_template():
    """Create or update a notification template.

    Request body (JSON)::

        {
          "event_key": "approval.submitted",
          "channel": "email",
          "subject": "New approval request: {{ref_id}}",
          "body": "Hello {{name}}, a new approval request has been submitted. Ref: {{ref_id}}"
        }
    """
    data = request.get_json(silent=True) or {}

    event_key = data.get('event_key', '').strip()
    channel   = data.get('channel', '').strip()
    body      = data.get('body', '').strip()

    if not event_key:
        return error_response('event_key is required.', 400, 'VALIDATION_ERROR')
    if not channel:
        return error_response('channel is required.', 400, 'VALIDATION_ERROR')
    if channel not in VALID_CHANNELS:
        return error_response(f"channel must be one of: {', '.join(VALID_CHANNELS)}", 400, 'VALIDATION_ERROR')
    if not body:
        return error_response('body is required.', 400, 'VALIDATION_ERROR')

    template = upsert_template(
        district_id=_district(),
        event_key=event_key,
        channel=channel,
        body=body,
        subject=data.get('subject'),
    )
    return success_response(data=template.to_dict(), status_code=201, message='Template saved.')
