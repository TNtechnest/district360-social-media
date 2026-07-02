"""Tests for Notification API — send, list, templates (CRUD).

Covers:
  - Email / SMS / WhatsApp / Push channel dispatch (log mode — no real delivery)
  - Template create / list
  - Notification list / filter
  - Auth enforcement
  - Validation errors
"""
import pytest
from app.models import Permission, Notification, NotificationTemplate
from app.services.notifications.notification_service import (
    send_notification, upsert_template, get_notifications,
)


def _grant(db_session, role, resource, action):
    p = Permission.query.filter_by(resource=resource, action=action).first()
    if not p:
        p = Permission(resource=resource, action=action)
        db_session.add(p)
        db_session.flush()
    if p not in role.permissions:
        role.permissions.append(p)
        db_session.flush()


@pytest.fixture
def email_template(db_session, district):
    """A seeded email notification template."""
    t = NotificationTemplate(
        district_id=district.id,
        event_key='test.event',
        channel='email',
        subject='Test subject for {{ref_id}}',
        body='Hello {{name}}, your ref is {{ref_id}}.',
        is_active=True,
    )
    db_session.add(t)
    db_session.flush()
    return t


@pytest.fixture
def sent_notification(db_session, district, admin_user):
    """A pre-existing notification record."""
    n = Notification(
        district_id=district.id,
        user_id=admin_user.id,
        channel='email',
        recipient='admin@test.example',
        subject='Test subject',
        body='Test body',
        event_key='test.event',
        status='sent',
        payload={},
    )
    db_session.add(n)
    db_session.flush()
    return n


# ===========================================================================
# API — List Notifications
# ===========================================================================

class TestListNotifications:
    def test_requires_auth(self, client):
        resp = client.get('/api/v1/notifications')
        assert resp.status_code == 401

    def test_list_returns_results(self, client, auth_headers, admin_role, db_session, sent_notification):
        _grant(db_session, admin_role, 'notification', 'read')
        resp = client.get('/api/v1/notifications', headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()['meta']['total'] >= 1

    def test_filter_by_channel(self, client, auth_headers, admin_role, db_session, sent_notification):
        _grant(db_session, admin_role, 'notification', 'read')
        resp = client.get('/api/v1/notifications?channel=email', headers=auth_headers)
        assert resp.status_code == 200
        for n in resp.get_json()['data']:
            assert n['channel'] == 'email'

    def test_filter_by_status(self, client, auth_headers, admin_role, db_session, sent_notification):
        _grant(db_session, admin_role, 'notification', 'read')
        resp = client.get('/api/v1/notifications?status=sent', headers=auth_headers)
        assert resp.status_code == 200
        for n in resp.get_json()['data']:
            assert n['status'] == 'sent'

    def test_pagination(self, client, auth_headers, admin_role, db_session, sent_notification):
        _grant(db_session, admin_role, 'notification', 'read')
        resp = client.get('/api/v1/notifications?page=1&per_page=5', headers=auth_headers)
        assert resp.status_code == 200
        meta = resp.get_json()['meta']
        assert 'page' in meta
        assert 'per_page' in meta


# ===========================================================================
# API — Send Notification
# ===========================================================================

class TestSendNotification:
    def test_send_email(self, client, auth_headers, admin_role, db_session, email_template):
        _grant(db_session, admin_role, 'notification', 'create')
        resp = client.post('/api/v1/notifications/send', headers=auth_headers, json={
            'channel': 'email',
            'recipient': 'user@example.com',
            'event_key': 'test.event',
            'variables': {'name': 'Alice', 'ref_id': 'REF-001'},
        })
        assert resp.status_code == 201
        body = resp.get_json()['data']
        assert body['channel'] == 'email'
        assert body['status'] in ('sent', 'failed')

    def test_send_sms(self, client, auth_headers, admin_role, db_session, district):
        _grant(db_session, admin_role, 'notification', 'create')
        # Create SMS template
        upsert_template(
            district_id=district.id,
            event_key='sms.test',
            channel='sms',
            body='Your OTP is {{otp}}',
        )
        resp = client.post('/api/v1/notifications/send', headers=auth_headers, json={
            'channel': 'sms',
            'recipient': '+919876543210',
            'event_key': 'sms.test',
            'variables': {'otp': '123456'},
        })
        assert resp.status_code == 201
        assert resp.get_json()['data']['channel'] == 'sms'

    def test_send_whatsapp(self, client, auth_headers, admin_role, db_session, district):
        _grant(db_session, admin_role, 'notification', 'create')
        upsert_template(
            district_id=district.id,
            event_key='wa.test',
            channel='whatsapp',
            body='Hello {{name}}! Your complaint ref is {{ref_id}}.',
        )
        resp = client.post('/api/v1/notifications/send', headers=auth_headers, json={
            'channel': 'whatsapp',
            'recipient': '+919876543210',
            'event_key': 'wa.test',
            'variables': {'name': 'Bob', 'ref_id': 'COMP-001'},
        })
        assert resp.status_code == 201
        assert resp.get_json()['data']['channel'] == 'whatsapp'

    def test_send_push(self, client, auth_headers, admin_role, db_session, district):
        _grant(db_session, admin_role, 'notification', 'create')
        upsert_template(
            district_id=district.id,
            event_key='push.test',
            channel='push',
            body='New update: {{message}}',
            subject='District360 Alert',
        )
        resp = client.post('/api/v1/notifications/send', headers=auth_headers, json={
            'channel': 'push',
            'recipient': 'device-token-xyz123',
            'event_key': 'push.test',
            'variables': {'message': 'Road work scheduled tomorrow.'},
        })
        assert resp.status_code == 201
        assert resp.get_json()['data']['channel'] == 'push'

    def test_send_missing_channel(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'notification', 'create')
        resp = client.post('/api/v1/notifications/send', headers=auth_headers, json={
            'recipient': 'x@y.com',
            'event_key': 'test.event',
        })
        assert resp.status_code == 400

    def test_send_invalid_channel(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'notification', 'create')
        resp = client.post('/api/v1/notifications/send', headers=auth_headers, json={
            'channel': 'telegram',
            'recipient': 'x@y.com',
            'event_key': 'test.event',
        })
        assert resp.status_code == 400

    def test_send_missing_recipient(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'notification', 'create')
        resp = client.post('/api/v1/notifications/send', headers=auth_headers, json={
            'channel': 'email',
            'event_key': 'test.event',
        })
        assert resp.status_code == 400

    def test_send_no_template_no_body(self, client, auth_headers, admin_role, db_session):
        """No template + no body fallback → 400."""
        _grant(db_session, admin_role, 'notification', 'create')
        resp = client.post('/api/v1/notifications/send', headers=auth_headers, json={
            'channel': 'email',
            'recipient': 'x@y.com',
            'event_key': 'nonexistent.event.key.xyz',
        })
        assert resp.status_code == 400

    def test_send_with_inline_body(self, client, auth_headers, admin_role, db_session):
        """Inline body (no template) should succeed."""
        _grant(db_session, admin_role, 'notification', 'create')
        resp = client.post('/api/v1/notifications/send', headers=auth_headers, json={
            'channel': 'email',
            'recipient': 'inline@example.com',
            'event_key': 'inline.body.test',
            'subject': 'Inline subject',
            'body': 'This is a direct body without a template.',
        })
        assert resp.status_code == 201


# ===========================================================================
# API — Templates
# ===========================================================================

class TestNotificationTemplates:
    def test_list_templates(self, client, auth_headers, admin_role, db_session, email_template):
        _grant(db_session, admin_role, 'notification', 'read')
        resp = client.get('/api/v1/notifications/templates', headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()['meta']['total'] >= 1

    def test_create_template(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'notification', 'create')
        _grant(db_session, admin_role, 'notification', 'read')
        resp = client.post('/api/v1/notifications/templates', headers=auth_headers, json={
            'event_key': 'approval.approved',
            'channel': 'email',
            'subject': 'Your post has been approved',
            'body': 'Hello {{name}}, your post {{resource}} was approved.',
        })
        assert resp.status_code == 201
        body = resp.get_json()['data']
        assert body['event_key'] == 'approval.approved'
        assert body['channel'] == 'email'

    def test_upsert_template_updates_existing(self, client, auth_headers, admin_role, db_session, email_template):
        _grant(db_session, admin_role, 'notification', 'create')
        resp = client.post('/api/v1/notifications/templates', headers=auth_headers, json={
            'event_key': email_template.event_key,
            'channel': email_template.channel,
            'subject': 'Updated subject',
            'body': 'Updated body {{ref_id}}',
        })
        assert resp.status_code == 201
        assert resp.get_json()['data']['subject'] == 'Updated subject'

    def test_create_template_missing_body(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'notification', 'create')
        resp = client.post('/api/v1/notifications/templates', headers=auth_headers, json={
            'event_key': 'no.body.event',
            'channel': 'sms',
        })
        assert resp.status_code == 400

    def test_create_template_invalid_channel(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'notification', 'create')
        resp = client.post('/api/v1/notifications/templates', headers=auth_headers, json={
            'event_key': 'test.event',
            'channel': 'fax',
            'body': 'Hello',
        })
        assert resp.status_code == 400


# ===========================================================================
# Service Layer Unit Tests
# ===========================================================================

class TestNotificationService:
    def test_send_with_template_renders_variables(self, db_session, district, admin_user, email_template):
        notif = send_notification(
            district_id=district.id,
            channel='email',
            recipient='svc@example.com',
            event_key='test.event',
            variables={'name': 'Charlie', 'ref_id': 'SVC-001'},
            user_id=admin_user.id,
        )
        assert 'Charlie' in notif.body
        assert 'SVC-001' in notif.body
        assert notif.status in ('sent', 'failed')

    def test_upsert_creates_new_template(self, db_session, district):
        t = upsert_template(
            district_id=district.id,
            event_key='new.unique.event',
            channel='push',
            body='Push body {{msg}}',
            subject='Push title',
        )
        assert t.id is not None
        assert t.channel == 'push'

    def test_upsert_updates_existing(self, db_session, district, email_template):
        t2 = upsert_template(
            district_id=district.id,
            event_key=email_template.event_key,
            channel=email_template.channel,
            body='New body content',
        )
        assert t2.id == email_template.id
        assert t2.body == 'New body content'

    def test_get_notifications_filter(self, db_session, district, admin_user, sent_notification):
        pagination = get_notifications(
            district_id=district.id,
            channel='email',
            status='sent',
        )
        assert pagination.total >= 1
