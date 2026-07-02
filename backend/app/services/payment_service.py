"""Payment service — Razorpay & Stripe integration, webhooks, invoices, refunds.

Supports:
- Razorpay order creation, payment verification, webhooks
- Stripe payment intent, webhooks
- Subscription plan management
- Invoice generation
- Full refund handling
"""

from __future__ import annotations
import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timezone

from app.extensions import db
from app.models.payment import SubscriptionPlan, PaymentTransaction
from app.services.audit_service import write_audit_log
from app.utils.db import paginate_query

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Subscription Plan CRUD
# ---------------------------------------------------------------------------

def create_plan(
    district_id: str, name: str, code: str, amount: float,
    currency: str = 'INR', interval: str = 'monthly',
    description: str | None = None, features: list | None = None,
    max_users: int | None = None, max_storage_gb: int | None = None,
) -> SubscriptionPlan:
    existing = SubscriptionPlan.query.filter_by(district_id=district_id, code=code).first()
    if existing:
        raise ValueError(f'Plan with code "{code}" already exists.')
    plan = SubscriptionPlan(
        district_id=district_id, name=name, code=code, amount=amount,
        currency=currency, interval=interval, description=description,
        features=features or [], max_users=max_users, max_storage_gb=max_storage_gb,
        is_active=True,
    )
    db.session.add(plan)
    db.session.commit()
    return plan


def get_plans(district_id: str, page: int = 1, per_page: int = 20):
    return paginate_query(
        SubscriptionPlan.query.filter_by(district_id=district_id)
        .order_by(SubscriptionPlan.amount.asc()),
        page, per_page,
    )


def get_plan(district_id: str, plan_id: str) -> SubscriptionPlan:
    plan = SubscriptionPlan.query.filter_by(id=plan_id, district_id=district_id).first()
    if not plan:
        raise ValueError('Plan not found.')
    return plan


# ---------------------------------------------------------------------------
# Razorpay Integration
# ---------------------------------------------------------------------------

def _razorpay_client():
    import razorpay  # type: ignore
    key_id = os.getenv('RAZORPAY_KEY_ID', 'rzp_test_xxxx')
    key_secret = os.getenv('RAZORPAY_KEY_SECRET', '')
    return razorpay.Client(auth=(key_id, key_secret))


def create_razorpay_order(
    district_id: str, plan_id: str, user_id: str | None = None,
) -> dict:
    """Create a Razorpay order for a subscription plan."""
    plan = get_plan(district_id, plan_id)
    if not plan.is_active:
        raise ValueError('Plan is not active.')

    amount_paise = int(plan.amount * 100)
    client = _razorpay_client()
    order_data = {
        'amount': amount_paise,
        'currency': plan.currency,
        'receipt': f'district360_{district_id[:8]}_{datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")}',
        'notes': {'district_id': district_id, 'plan_id': plan_id},
    }
    order = client.order.create(order_data)

    txn = PaymentTransaction(
        district_id=district_id,
        plan_id=plan_id,
        user_id=user_id,
        provider='razorpay',
        transaction_id=order['id'],
        amount=plan.amount,
        currency=plan.currency,
        status='created',
        description=f'Order for {plan.name}',
    )
    db.session.add(txn)
    db.session.commit()
    logger.info('Razorpay order created: %s for plan %s', order['id'], plan_id)
    return {'order_id': order['id'], 'amount': amount_paise, 'currency': plan.currency, 'transaction_id': txn.id}


def verify_razorpay_payment(
    order_id: str, payment_id: str, signature: str,
) -> PaymentTransaction:
    """Verify Razorpay payment signature and mark transaction as paid."""
    txn = PaymentTransaction.query.filter_by(transaction_id=order_id, provider='razorpay').first()
    if not txn:
        raise ValueError('Transaction not found.')

    expected_signature = hmac.new(
        os.getenv('RAZORPAY_KEY_SECRET', '').encode(),
        f'{order_id}|{payment_id}'.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, signature):
        raise ValueError('Payment signature verification failed.')

    txn.transaction_id = payment_id
    txn.provider_order_id = order_id
    txn.status = 'paid'
    txn.paid_at = datetime.now(timezone.utc).isoformat()

    write_audit_log(
        district_id=txn.district_id, actor_id=txn.user_id,
        action='payment.completed',
        resource_type='payment_transaction', resource_id=txn.id,
        after_state=txn.to_dict(),
    )
    db.session.commit()
    logger.info('Razorpay payment verified: %s for order %s', payment_id, order_id)
    return txn


def handle_razorpay_webhook(payload: dict, signature: str) -> str:
    """Process incoming Razorpay webhook event."""
    expected_sig = hmac.new(
        os.getenv('RAZORPAY_WEBHOOK_SECRET', '').encode(),
        json.dumps(payload).encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected_sig, signature):
        raise ValueError('Webhook signature verification failed.')

    event = payload.get('event', '')
    payment_entity = payload.get('payload', {}).get('payment', {}).get('entity', {})

    if event == 'payment.captured' and payment_entity:
        order_id = payment_entity.get('order_id', '')
        payment_id = payment_entity.get('id', '')
        txn = PaymentTransaction.query.filter_by(
            provider_order_id=order_id, provider='razorpay',
        ).first()
        if txn and txn.status != 'paid':
            txn.transaction_id = payment_id
            txn.status = 'paid'
            txn.paid_at = datetime.now(timezone.utc).isoformat()
            txn.webhook_data = payload
            db.session.commit()
            logger.info('Razorpay webhook: payment %s captured for order %s', payment_id, order_id)
            return 'payment.captured'

    elif event == 'payment.failed' and payment_entity:
        order_id = payment_entity.get('order_id', '')
        txn = PaymentTransaction.query.filter_by(
            provider_order_id=order_id, provider='razorpay',
        ).first()
        if txn:
            txn.status = 'failed'
            txn.error_message = payment_entity.get('error_description', 'Payment failed')
            txn.webhook_data = payload
            db.session.commit()
            logger.warning('Razorpay webhook: payment failed for order %s', order_id)
            return 'payment.failed'

    return 'unhandled'


# ---------------------------------------------------------------------------
# Stripe Integration
# ---------------------------------------------------------------------------

def _stripe_client():
    import stripe  # type: ignore
    stripe.api_key = os.getenv('STRIPE_SECRET_KEY', 'sk_test_xxxx')
    return stripe


def create_stripe_payment_intent(
    district_id: str, plan_id: str, user_id: str | None = None,
) -> dict:
    """Create a Stripe PaymentIntent for a subscription plan."""
    plan = get_plan(district_id, plan_id)
    if not plan.is_active:
        raise ValueError('Plan is not active.')

    stripe_client = _stripe_client()
    intent = stripe_client.PaymentIntent.create(
        amount=int(plan.amount * 100),
        currency=plan.currency.lower(),
        description=f'{plan.name} — {district_id[:8]}',
        metadata={'district_id': district_id, 'plan_id': plan_id},
    )

    txn = PaymentTransaction(
        district_id=district_id,
        plan_id=plan_id,
        user_id=user_id,
        provider='stripe',
        transaction_id=intent['id'],
        amount=plan.amount,
        currency=plan.currency,
        status='created',
        description=f'PaymentIntent for {plan.name}',
    )
    db.session.add(txn)
    db.session.commit()
    logger.info('Stripe PaymentIntent created: %s for plan %s', intent['id'], plan_id)
    return {
        'client_secret': intent['client_secret'],
        'intent_id': intent['id'],
        'amount': intent['amount'],
        'currency': intent['currency'],
        'transaction_id': txn.id,
    }


def handle_stripe_webhook(payload: bytes, sig_header: str) -> str:
    """Process incoming Stripe webhook event."""
    stripe_client = _stripe_client()
    endpoint_secret = os.getenv('STRIPE_WEBHOOK_SECRET', '')

    try:
        event = stripe_client.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError:
        raise ValueError('Invalid Stripe webhook payload.')
    except stripe_client.error.SignatureVerificationError:
        raise ValueError('Stripe webhook signature verification failed.')

    event_type = event['type']
    data = event['data']['object']

    if event_type == 'payment_intent.succeeded':
        intent_id = data['id']
        txn = PaymentTransaction.query.filter_by(
            transaction_id=intent_id, provider='stripe',
        ).first()
        if txn and txn.status != 'paid':
            txn.status = 'paid'
            txn.paid_at = datetime.now(timezone.utc).isoformat()
            txn.webhook_data = event
            db.session.commit()
            logger.info('Stripe webhook: PaymentIntent %s succeeded', intent_id)
        return 'payment_intent.succeeded'

    elif event_type == 'payment_intent.payment_failed':
        intent_id = data['id']
        txn = PaymentTransaction.query.filter_by(
            transaction_id=intent_id, provider='stripe',
        ).first()
        if txn:
            txn.status = 'failed'
            txn.error_message = data.get('last_payment_error', {}).get('message', 'Payment failed')
            txn.webhook_data = event
            db.session.commit()
            logger.warning('Stripe webhook: PaymentIntent %s failed', intent_id)
        return 'payment_intent.payment_failed'

    return 'unhandled'


# ---------------------------------------------------------------------------
# Refund Handling
# ---------------------------------------------------------------------------

def process_refund(
    district_id: str, transaction_id: str,
    amount: float | None = None, reason: str | None = None,
) -> PaymentTransaction:
    """Process a full or partial refund for a paid transaction."""
    txn = PaymentTransaction.query.filter_by(
        id=transaction_id, district_id=district_id, status='paid',
    ).first()
    if not txn:
        raise ValueError('Paid transaction not found.')

    if txn.refund_status == 'refunded':
        raise ValueError('Transaction already refunded.')

    if txn.provider == 'razorpay':
        _razorpay_refund(txn, amount)
    elif txn.provider == 'stripe':
        _stripe_refund(txn, amount)
    else:
        raise ValueError(f'Refund not supported for provider: {txn.provider}')

    txn.refund_status = 'refunded'
    txn.refund_amount = amount or txn.amount
    txn.refund_reason = reason
    txn.refunded_at = datetime.now(timezone.utc).isoformat()
    txn.status = 'refunded'

    write_audit_log(
        district_id=district_id, actor_id=None,
        action='payment.refunded',
        resource_type='payment_transaction', resource_id=txn.id,
        after_state=txn.to_dict(),
    )
    db.session.commit()
    logger.info('Refund processed: %s for transaction %s', amount or txn.amount, transaction_id)
    return txn


def _razorpay_refund(txn: PaymentTransaction, amount: float | None) -> None:
    import razorpay  # type: ignore
    client = _razorpay_client()
    refund_data = {'payment_id': txn.transaction_id}
    if amount:
        refund_data['amount'] = int(amount * 100)
    client.payment.refund(txn.transaction_id, refund_data)


def _stripe_refund(txn: PaymentTransaction, amount: float | None) -> None:
    stripe_client = _stripe_client()
    refund_data = {'payment_intent': txn.transaction_id}
    if amount:
        refund_data['amount'] = int(amount * 100)
    stripe_client.Refund.create(**refund_data)


# ---------------------------------------------------------------------------
# Transaction Queries
# ---------------------------------------------------------------------------

def get_transactions(
    district_id: str, page: int = 1, per_page: int = 20,
    status: str | None = None, provider: str | None = None,
):
    query = PaymentTransaction.query.filter_by(district_id=district_id)
    if status:
        query = query.filter(PaymentTransaction.status == status)
    if provider:
        query = query.filter(PaymentTransaction.provider == provider)
    return paginate_query(
        query.order_by(PaymentTransaction.created_at.desc()), page, per_page,
    )


def get_transaction(district_id: str, transaction_id: str) -> PaymentTransaction:
    txn = PaymentTransaction.query.filter_by(id=transaction_id, district_id=district_id).first()
    if not txn:
        raise ValueError('Transaction not found.')
    return txn
