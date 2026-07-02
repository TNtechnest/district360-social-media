"""Notification dispatcher — email, SMS, WhatsApp, and push.

Architecture:
  1. ``send_notification()`` — main entry point; resolves template, renders body,
     persists a Notification record, then calls the appropriate channel sender.
  2. Channel senders are thin wrappers around provider SDKs / REST APIs.
     They are designed to be swapped for real providers (SendGrid, Twilio, etc.)
     by setting environment variables.

Default (development) behaviour:
  - Email / SMS / WhatsApp / Push: logs the notification; no real delivery.
  - Set ``NOTIFICATION_PROVIDER=real`` + provider keys to enable real delivery.
"""
from __future__ import annotations
import logging
import re
from datetime import datetime, timezone

from app.extensions import db
from app.models.notification import Notification, NotificationTemplate
from app.utils.db import paginate_query

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Template rendering (simple {{variable}} substitution)
# ---------------------------------------------------------------------------

def _render(template: str, variables: dict) -> str:
    """Replace ``{{key}}`` placeholders in template with values."""
    def replacer(m):
        return str(variables.get(m.group(1), m.group(0)))
    return re.sub(r'\{\{(\w+)\}\}', replacer, template)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def send_notification(
    district_id: str,
    channel: str,
    recipient: str,
    event_key: str,
    variables: dict | None = None,
    user_id: str | None = None,
    subject: str | None = None,
    body: str | None = None,
) -> Notification:
    """Create a Notification record and dispatch it through the channel.

    If a NotificationTemplate exists for (district_id, event_key, channel),
    its body/subject is used (with variable substitution).  Otherwise the
    caller must supply ``body`` directly.

    Args:
        district_id: Tenant scope.
        channel:     ``'email'`` | ``'sms'`` | ``'whatsapp'`` | ``'push'``.
        recipient:   Email address / phone / device token.
        event_key:   e.g. ``'approval.submitted'``.
        variables:   Template substitution dict.
        user_id:     Associated user UUID.
        subject:     Email subject (override template).
        body:        Message body (override template).

    Returns:
        Persisted :class:`Notification` record.
    """
    variables = variables or {}

    template = NotificationTemplate.query.filter_by(
        district_id=district_id, event_key=event_key, channel=channel, is_active=True,
    ).first()

    rendered_body    = _render(template.body,    variables) if template else (body or '')
    rendered_subject = _render(template.subject, variables) if (template and template.subject) else (subject or '')

    if not rendered_body:
        logger.warning('send_notification: empty body for %s/%s — skipping', event_key, channel)
        raise ValueError('Notification body cannot be empty.')

    notif = Notification(
        district_id=district_id,
        user_id=user_id,
        template_id=template.id if template else None,
        channel=channel,
        recipient=recipient,
        subject=rendered_subject,
        body=rendered_body,
        event_key=event_key,
        status='pending',
        payload=variables,
    )
    db.session.add(notif)
    db.session.flush()

    try:
        _dispatch(notif)
        notif.status  = 'sent'
        notif.sent_at = datetime.now(timezone.utc).isoformat()
    except Exception as exc:
        logger.exception('Notification dispatch failed: channel=%s recipient=%s', channel, recipient)
        notif.status        = 'failed'
        notif.error_message = str(exc)

    db.session.commit()
    return notif


def get_notifications(
    district_id: str,
    page: int = 1,
    per_page: int = 20,
    channel: str | None = None,
    status: str | None = None,
    user_id: str | None = None,
) -> object:
    query = Notification.query.filter_by(district_id=district_id)
    if channel:
        query = query.filter(Notification.channel == channel)
    if status:
        query = query.filter(Notification.status == status)
    if user_id:
        query = query.filter(Notification.user_id == user_id)
    return paginate_query(query.order_by(Notification.created_at.desc()), page, per_page)


# ---------------------------------------------------------------------------
# Template CRUD
# ---------------------------------------------------------------------------

def get_templates(district_id: str, page: int = 1, per_page: int = 20) -> object:
    return paginate_query(
        NotificationTemplate.query.filter_by(district_id=district_id)
        .order_by(NotificationTemplate.event_key.asc()),
        page, per_page,
    )


def upsert_template(
    district_id: str,
    event_key: str,
    channel: str,
    body: str,
    subject: str | None = None,
) -> NotificationTemplate:
    t = NotificationTemplate.query.filter_by(
        district_id=district_id, event_key=event_key, channel=channel,
    ).first()
    if t:
        t.body    = body
        t.subject = subject
    else:
        t = NotificationTemplate(
            district_id=district_id, event_key=event_key, channel=channel,
            body=body, subject=subject, is_active=True,
        )
        db.session.add(t)
    db.session.commit()
    return t


# ---------------------------------------------------------------------------
# Channel dispatchers
# ---------------------------------------------------------------------------

def _dispatch(notif: Notification) -> None:
    dispatchers = {
        'email':    _send_email,
        'sms':      _send_sms,
        'whatsapp': _send_whatsapp,
        'push':     _send_push,
    }
    fn = dispatchers.get(notif.channel)
    if not fn:
        raise ValueError(f"Unknown notification channel: '{notif.channel}'")
    fn(notif)


def _send_email(notif: Notification) -> None:
    """Send email via SendGrid / AWS SES / SMTP.

    Set ``EMAIL_PROVIDER=sendgrid`` and ``SENDGRID_API_KEY=...`` for real delivery.
    """
    import os
    provider = os.getenv('EMAIL_PROVIDER', 'log')

    if provider == 'sendgrid':
        import sendgrid  # type: ignore
        from sendgrid.helpers.mail import Mail  # type: ignore
        sg   = sendgrid.SendGridAPIClient(api_key=os.getenv('SENDGRID_API_KEY'))
        mail = Mail(
            from_email=os.getenv('EMAIL_FROM', 'noreply@district360.app'),
            to_emails=notif.recipient,
            subject=notif.subject,
            html_content=notif.body,
        )
        resp = sg.send(mail)
        notif.provider_message_id = resp.headers.get('X-Message-Id')
    elif provider == 'smtp':
        import smtplib
        from email.mime.text import MIMEText
        msg = MIMEText(notif.body, 'html')
        msg['Subject'] = notif.subject or ''
        msg['From']    = os.getenv('EMAIL_FROM', 'noreply@district360.app')
        msg['To']      = notif.recipient
        with smtplib.SMTP(os.getenv('SMTP_HOST', 'localhost'), int(os.getenv('SMTP_PORT', 587))) as s:
            s.starttls()
            s.login(os.getenv('SMTP_USER', ''), os.getenv('SMTP_PASS', ''))
            s.send_message(msg)
    else:
        logger.info('[EMAIL] to=%s subject=%s | %s', notif.recipient, notif.subject, notif.body[:80])


def _send_sms(notif: Notification) -> None:
    """Send SMS via Twilio / MSG91.

    Set ``SMS_PROVIDER=twilio`` and Twilio credentials for real delivery.
    """
    import os
    provider = os.getenv('SMS_PROVIDER', 'log')

    if provider == 'twilio':
        from twilio.rest import Client  # type: ignore
        client = Client(os.getenv('TWILIO_ACCOUNT_SID'), os.getenv('TWILIO_AUTH_TOKEN'))
        msg = client.messages.create(
            body=notif.body,
            from_=os.getenv('TWILIO_FROM_NUMBER'),
            to=notif.recipient,
        )
        notif.provider_message_id = msg.sid
    else:
        logger.info('[SMS] to=%s | %s', notif.recipient, notif.body[:80])


def _send_whatsapp(notif: Notification) -> None:
    """Send WhatsApp message via Twilio WhatsApp or Meta Cloud API.

    Set ``WHATSAPP_PROVIDER=twilio`` for Twilio sandbox delivery.
    """
    import os
    provider = os.getenv('WHATSAPP_PROVIDER', 'log')

    if provider == 'twilio':
        from twilio.rest import Client  # type: ignore
        client = Client(os.getenv('TWILIO_ACCOUNT_SID'), os.getenv('TWILIO_AUTH_TOKEN'))
        msg = client.messages.create(
            body=notif.body,
            from_=f"whatsapp:{os.getenv('TWILIO_WHATSAPP_NUMBER')}",
            to=f'whatsapp:{notif.recipient}',
        )
        notif.provider_message_id = msg.sid
    else:
        logger.info('[WHATSAPP] to=%s | %s', notif.recipient, notif.body[:80])


def _send_push(notif: Notification) -> None:
    """Send push notification via Firebase Cloud Messaging.

    Set ``PUSH_PROVIDER=fcm`` and ``FCM_SERVER_KEY=...`` for real delivery.
    ``notif.recipient`` should be a valid FCM device token.
    """
    import os
    provider = os.getenv('PUSH_PROVIDER', 'log')

    if provider == 'fcm':
        import requests
        headers = {
            'Authorization': f"key={os.getenv('FCM_SERVER_KEY')}",
            'Content-Type': 'application/json',
        }
        payload = {
            'to': notif.recipient,
            'notification': {
                'title': notif.subject or 'District360',
                'body': notif.body,
            },
            'data': notif.payload,
        }
        resp = requests.post('https://fcm.googleapis.com/fcm/send',
                             headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        notif.provider_message_id = resp.json().get('message_id')
    else:
        logger.info('[PUSH] to=%s title=%s | %s', notif.recipient, notif.subject, notif.body[:80])
