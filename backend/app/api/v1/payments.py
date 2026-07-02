"""Payment API endpoints.

Routes
------
GET    /api/v1/payments/plans              — list subscription plans
POST   /api/v1/payments/plans              — create a plan
GET    /api/v1/payments/plans/<id>         — get plan details
POST   /api/v1/payments/razorpay/order     — create Razorpay order
POST   /api/v1/payments/razorpay/verify    — verify Razorpay payment
POST   /api/v1/payments/stripe/intent      — create Stripe PaymentIntent
POST   /api/v1/payments/webhook/razorpay   — Razorpay webhook
POST   /api/v1/payments/webhook/stripe     — Stripe webhook
POST   /api/v1/payments/<id>/refund        — refund a transaction
GET    /api/v1/payments/transactions       — list transactions
GET    /api/v1/payments/transactions/<id>  — get transaction detail
"""

import logging

from flask import Blueprint, request, g
from flask_jwt_extended import get_jwt

from app.services.payment_service import (
    create_plan, get_plans, get_plan,
    create_razorpay_order, verify_razorpay_payment,
    create_stripe_payment_intent,
    handle_razorpay_webhook, handle_stripe_webhook,
    process_refund,
    get_transactions, get_transaction,
)
from app.services.rbac_service import require_permission
from app.utils.responses import success_response, error_response, paginated_response
from app.utils.validators import validate_pagination_params

logger = logging.getLogger(__name__)
payments_bp = Blueprint('payments', __name__, url_prefix='/payments')


def _district():
    return get_jwt().get('district_id', '')


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------

@payments_bp.route('/plans', methods=['GET'])
@require_permission('payment', 'read')
def list_plans():
    page, per_page = validate_pagination_params(
        request.args.get('page', 1), request.args.get('per_page', 20)
    )
    pagination = get_plans(_district(), page=page, per_page=per_page)
    return paginated_response([p.to_dict() for p in pagination.items], pagination)


@payments_bp.route('/plans', methods=['POST'])
@require_permission('payment', 'create')
def create_plan_endpoint():
    data = request.get_json(silent=True) or {}
    for field in ('name', 'code', 'amount'):
        if not data.get(field):
            return error_response(f"'{field}' is required.", 400, 'VALIDATION_ERROR')
    try:
        plan = create_plan(
            district_id=_district(),
            name=data['name'],
            code=data['code'],
            amount=float(data['amount']),
            currency=data.get('currency', 'INR'),
            interval=data.get('interval', 'monthly'),
            description=data.get('description'),
            features=data.get('features'),
            max_users=data.get('max_users'),
            max_storage_gb=data.get('max_storage_gb'),
        )
        return success_response(data=plan.to_dict(), status_code=201, message='Plan created.')
    except ValueError as exc:
        return error_response(str(exc), 400, 'VALIDATION_ERROR')


@payments_bp.route('/plans/<plan_id>', methods=['GET'])
@require_permission('payment', 'read')
def get_plan_endpoint(plan_id):
    try:
        plan = get_plan(_district(), plan_id)
        return success_response(data=plan.to_dict())
    except ValueError as exc:
        return error_response(str(exc), 404, 'NOT_FOUND')


# ---------------------------------------------------------------------------
# Razorpay
# ---------------------------------------------------------------------------

@payments_bp.route('/razorpay/order', methods=['POST'])
@require_permission('payment', 'create')
def create_razorpay_order_endpoint():
    data = request.get_json(silent=True) or {}
    plan_id = data.get('plan_id', '').strip()
    if not plan_id:
        return error_response('plan_id is required.', 400, 'VALIDATION_ERROR')
    try:
        result = create_razorpay_order(
            _district(), plan_id,
            user_id=getattr(g.current_user, 'id', None),
        )
        return success_response(data=result, message='Razorpay order created.')
    except ValueError as exc:
        return error_response(str(exc), 400, 'VALIDATION_ERROR')


@payments_bp.route('/razorpay/verify', methods=['POST'])
@require_permission('payment', 'create')
def verify_razorpay_payment_endpoint():
    data = request.get_json(silent=True) or {}
    for field in ('order_id', 'payment_id', 'signature'):
        if not data.get(field):
            return error_response(f"'{field}' is required.", 400, 'VALIDATION_ERROR')
    try:
        txn = verify_razorpay_payment(
            order_id=data['order_id'],
            payment_id=data['payment_id'],
            signature=data['signature'],
        )
        return success_response(data=txn.to_dict(), message='Payment verified.')
    except ValueError as exc:
        return error_response(str(exc), 400, 'PAYMENT_VERIFICATION_FAILED')


# ---------------------------------------------------------------------------
# Stripe
# ---------------------------------------------------------------------------

@payments_bp.route('/stripe/intent', methods=['POST'])
@require_permission('payment', 'create')
def create_stripe_intent_endpoint():
    data = request.get_json(silent=True) or {}
    plan_id = data.get('plan_id', '').strip()
    if not plan_id:
        return error_response('plan_id is required.', 400, 'VALIDATION_ERROR')
    try:
        result = create_stripe_payment_intent(
            _district(), plan_id,
            user_id=getattr(g.current_user, 'id', None),
        )
        return success_response(data=result, message='Stripe PaymentIntent created.')
    except ValueError as exc:
        return error_response(str(exc), 400, 'VALIDATION_ERROR')


# ---------------------------------------------------------------------------
# Webhooks (no auth — called by payment providers)
# ---------------------------------------------------------------------------

@payments_bp.route('/webhook/razorpay', methods=['POST'])
def razorpay_webhook():
    payload = request.get_json(silent=True) or {}
    signature = request.headers.get('X-Razorpay-Signature', '')
    try:
        event = handle_razorpay_webhook(payload, signature)
        return success_response(data={'event': event}, message='Webhook processed.')
    except ValueError as exc:
        return error_response(str(exc), 400, 'WEBHOOK_ERROR')


@payments_bp.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature', '')
    try:
        event = handle_stripe_webhook(payload, sig_header)
        return success_response(data={'event': event}, message='Webhook processed.')
    except ValueError as exc:
        return error_response(str(exc), 400, 'WEBHOOK_ERROR')


# ---------------------------------------------------------------------------
# Transactions & Refunds
# ---------------------------------------------------------------------------

@payments_bp.route('/transactions', methods=['GET'])
@require_permission('payment', 'read')
def list_transactions():
    page, per_page = validate_pagination_params(
        request.args.get('page', 1), request.args.get('per_page', 20)
    )
    pagination = get_transactions(
        _district(), page=page, per_page=per_page,
        status=request.args.get('status'),
        provider=request.args.get('provider'),
    )
    return paginated_response([t.to_dict() for t in pagination.items], pagination)


@payments_bp.route('/transactions/<transaction_id>', methods=['GET'])
@require_permission('payment', 'read')
def get_transaction_endpoint(transaction_id):
    try:
        txn = get_transaction(_district(), transaction_id)
        return success_response(data=txn.to_dict())
    except ValueError as exc:
        return error_response(str(exc), 404, 'NOT_FOUND')


@payments_bp.route('/<transaction_id>/refund', methods=['POST'])
@require_permission('payment', 'create')
def refund_transaction(transaction_id):
    data = request.get_json(silent=True) or {}
    try:
        txn = process_refund(
            _district(), transaction_id,
            amount=float(data['amount']) if data.get('amount') else None,
            reason=data.get('reason'),
        )
        return success_response(data=txn.to_dict(), message='Refund processed.')
    except ValueError as exc:
        return error_response(str(exc), 400, 'REFUND_FAILED')
