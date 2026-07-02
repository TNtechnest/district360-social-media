"""Tests for Workflow, Approval, Escalation, and SLA APIs."""
import pytest
from datetime import datetime, timezone, timedelta

from app.models import Permission, ApprovalRequest, WorkflowRule, EscalationLog
from app.services.workflow.approval_service import create_approval_request
from app.services.workflow.escalation_service import (
    check_sla_breaches, get_sla_summary, create_workflow_rule,
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
def approval(db_session, district, admin_user):
    """An open approval request for a social_post."""
    req = ApprovalRequest(
        district_id=district.id,
        resource_type='social_post',
        resource_id='fake-post-uuid-001',
        submitter_id=admin_user.id,
        status='pending',
        submitted_at=datetime.now(timezone.utc).isoformat(),
        sla_due_at=(datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
    )
    db_session.add(req)
    db_session.flush()
    return req


@pytest.fixture
def breached_approval(db_session, district, admin_user):
    """An approval request whose SLA is already past due."""
    req = ApprovalRequest(
        district_id=district.id,
        resource_type='social_post',
        resource_id='fake-post-uuid-002',
        submitter_id=admin_user.id,
        status='pending',
        submitted_at=(datetime.now(timezone.utc) - timedelta(hours=3)).isoformat(),
        sla_due_at=(datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat(),
    )
    db_session.add(req)
    db_session.flush()
    return req


# ===========================================================================
# Approval Requests — API
# ===========================================================================

class TestApprovalRequests:
    def test_requires_auth(self, client):
        resp = client.get('/api/v1/workflow/approvals')
        assert resp.status_code == 401

    def test_list_approvals(self, client, auth_headers, admin_role, db_session, approval):
        _grant(db_session, admin_role, 'approval', 'read')
        resp = client.get('/api/v1/workflow/approvals', headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()['meta']['total'] >= 1

    def test_create_approval(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'approval', 'create')
        _grant(db_session, admin_role, 'approval', 'read')
        resp = client.post('/api/v1/workflow/approvals', headers=auth_headers, json={
            'resource_type': 'social_post',
            'resource_id': 'unique-new-post-uuid',
            'notes': 'Please review this post.',
            'sla_minutes': 120,
        })
        assert resp.status_code == 201
        body = resp.get_json()['data']
        assert body['status'] == 'pending'
        assert body['resource_type'] == 'social_post'

    def test_create_duplicate_fails(self, client, auth_headers, admin_role, db_session, approval):
        _grant(db_session, admin_role, 'approval', 'create')
        resp = client.post('/api/v1/workflow/approvals', headers=auth_headers, json={
            'resource_type': approval.resource_type,
            'resource_id': approval.resource_id,
        })
        assert resp.status_code == 400

    def test_create_missing_resource_type(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'approval', 'create')
        resp = client.post('/api/v1/workflow/approvals', headers=auth_headers, json={
            'resource_id': 'some-id',
        })
        assert resp.status_code == 400

    def test_get_approval(self, client, auth_headers, admin_role, db_session, approval):
        _grant(db_session, admin_role, 'approval', 'read')
        resp = client.get(f'/api/v1/workflow/approvals/{approval.id}', headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()['data']['id'] == approval.id

    def test_get_approval_not_found(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'approval', 'read')
        resp = client.get('/api/v1/workflow/approvals/nonexistent', headers=auth_headers)
        assert resp.status_code == 404

    def test_approve_request(self, client, auth_headers, admin_role, db_session, approval):
        _grant(db_session, admin_role, 'approval', 'update')
        resp = client.post(
            f'/api/v1/workflow/approvals/{approval.id}/review',
            headers=auth_headers,
            json={'decision': 'approved', 'comment': 'Looks good!'},
        )
        assert resp.status_code == 200
        assert resp.get_json()['data']['status'] == 'approved'

    def test_reject_request(self, client, auth_headers, admin_role, db_session, district, admin_user):
        _grant(db_session, admin_role, 'approval', 'update')
        req = ApprovalRequest(
            district_id=district.id,
            resource_type='social_post',
            resource_id='reject-test-uuid',
            submitter_id=admin_user.id,
            status='pending',
            submitted_at=datetime.now(timezone.utc).isoformat(),
            sla_due_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        )
        db_session.add(req)
        db_session.flush()
        resp = client.post(
            f'/api/v1/workflow/approvals/{req.id}/review',
            headers=auth_headers,
            json={'decision': 'rejected', 'comment': 'Needs revision.'},
        )
        assert resp.status_code == 200
        assert resp.get_json()['data']['status'] == 'rejected'

    def test_invalid_decision(self, client, auth_headers, admin_role, db_session, approval):
        _grant(db_session, admin_role, 'approval', 'update')
        resp = client.post(
            f'/api/v1/workflow/approvals/{approval.id}/review',
            headers=auth_headers,
            json={'decision': 'maybe'},
        )
        assert resp.status_code == 400

    def test_review_already_reviewed(self, client, auth_headers, admin_role, db_session, district, admin_user):
        _grant(db_session, admin_role, 'approval', 'update')
        req = ApprovalRequest(
            district_id=district.id,
            resource_type='social_post',
            resource_id='already-done-uuid',
            submitter_id=admin_user.id,
            status='approved',
            submitted_at=datetime.now(timezone.utc).isoformat(),
            sla_due_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        )
        db_session.add(req)
        db_session.flush()
        resp = client.post(
            f'/api/v1/workflow/approvals/{req.id}/review',
            headers=auth_headers,
            json={'decision': 'approved'},
        )
        assert resp.status_code == 400


# ===========================================================================
# Workflow Rules — API
# ===========================================================================

class TestWorkflowRules:
    def test_list_rules(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'workflow_rule', 'read')
        resp = client.get('/api/v1/workflow/rules', headers=auth_headers)
        assert resp.status_code == 200

    def test_create_rule(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'workflow_rule', 'create')
        _grant(db_session, admin_role, 'workflow_rule', 'read')
        resp = client.post('/api/v1/workflow/rules', headers=auth_headers, json={
            'resource_type': 'social_post',
            'name': 'Approval required for Facebook',
            'rule_type': 'approval',
            'conditions': {'platform': 'facebook'},
            'actions': [{'action': 'require_approval', 'target_role': 'district_admin'}],
            'sla_minutes': 60,
        })
        assert resp.status_code == 201
        assert resp.get_json()['data']['rule_type'] == 'approval'

    def test_create_rule_invalid_type(self, client, auth_headers, admin_role, db_session):
        _grant(db_session, admin_role, 'workflow_rule', 'create')
        resp = client.post('/api/v1/workflow/rules', headers=auth_headers, json={
            'resource_type': 'social_post',
            'name': 'Bad rule',
            'rule_type': 'invalid_type',
            'conditions': {},
            'actions': [],
        })
        assert resp.status_code == 400


# ===========================================================================
# Escalation — API
# ===========================================================================

class TestEscalation:
    def test_run_escalation_check(self, client, auth_headers, admin_role, db_session, breached_approval):
        _grant(db_session, admin_role, 'approval', 'update')
        resp = client.post('/api/v1/workflow/escalations/check', headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()['data']
        assert 'escalated' in data
        assert data['escalated'] >= 1  # breached_approval should be escalated

    def test_list_escalations(self, client, auth_headers, admin_role, db_session, breached_approval):
        _grant(db_session, admin_role, 'approval', 'update')
        client.post('/api/v1/workflow/escalations/check', headers=auth_headers)
        _grant(db_session, admin_role, 'approval', 'read')
        resp = client.get('/api/v1/workflow/escalations', headers=auth_headers)
        assert resp.status_code == 200


# ===========================================================================
# SLA Summary
# ===========================================================================

class TestSLASummary:
    def test_sla_summary(self, client, auth_headers, admin_role, db_session, approval):
        _grant(db_session, admin_role, 'approval', 'read')
        resp = client.get('/api/v1/workflow/sla/summary', headers=auth_headers)
        assert resp.status_code == 200
        body = resp.get_json()['data']
        assert 'open_requests' in body
        assert 'sla_breached' in body
        assert 'compliance_pct' in body
        assert body['open_requests'] >= 1


# ===========================================================================
# Service layer unit tests
# ===========================================================================

class TestApprovalService:
    def test_create_and_get(self, db_session, district, admin_user):
        req = create_approval_request(
            district_id=district.id,
            resource_type='social_post',
            resource_id='svc-test-uuid',
            submitter_id=admin_user.id,
            sla_minutes=30,
        )
        assert req.status == 'pending'
        assert req.sla_due_at is not None

    def test_check_sla_breaches(self, db_session, district, admin_user, breached_approval):
        count = check_sla_breaches()
        assert count >= 1

    def test_sla_summary_service(self, db_session, district, admin_user, approval):
        summary = get_sla_summary(district.id)
        assert summary['open_requests'] >= 1
        assert 'compliance_pct' in summary
