"""Service Request business logic — CRUD, assignment, status workflow, auto-routing."""

from __future__ import annotations
import logging
from datetime import datetime, timezone, timedelta

from app.extensions import db
from app.models.service_request import (
    ServiceRequest, ServiceRequestCategory, ServiceRequestComment,
    REQUEST_STATUSES, REQUEST_PRIORITIES,
)
from app.models.department import Department
from app.models.user import User
from app.services.audit_service import write_audit_log
from app.utils.db import paginate_query

logger = logging.getLogger(__name__)

PHASE7_ISSUE_ROUTES = {
    'water': {
        'department_code': 'WATER',
        'department_name': 'Water Supply Department',
        'category_code': 'WATER_ISSUE',
        'category_name': 'Water Issue',
        'priority': 'high',
        'sla_hours': 24,
    },
    'roads': {
        'department_code': 'ROADS',
        'department_name': 'Roads and Infrastructure Department',
        'category_code': 'ROAD_ISSUE',
        'category_name': 'Road Issue',
        'priority': 'medium',
        'sla_hours': 72,
    },
    'electricity': {
        'department_code': 'ELECTRICITY',
        'department_name': 'Electricity Department',
        'category_code': 'ELECTRICITY_ISSUE',
        'category_name': 'Electricity Issue',
        'priority': 'high',
        'sla_hours': 24,
    },
    'garbage': {
        'department_code': 'SANITATION',
        'department_name': 'Sanitation Department',
        'category_code': 'GARBAGE_ISSUE',
        'category_name': 'Garbage Issue',
        'priority': 'medium',
        'sla_hours': 48,
    },
    'drainage': {
        'department_code': 'DRAINAGE',
        'department_name': 'Drainage Department',
        'category_code': 'DRAINAGE_ISSUE',
        'category_name': 'Drainage Issue',
        'priority': 'high',
        'sla_hours': 24,
    },
}

VALID_TRANSITIONS = {
    'submitted':      {'acknowledged', 'rejected'},
    'acknowledged':   {'in_progress', 'escalated', 'rejected'},
    'in_progress':    {'resolved', 'escalated'},
    'escalated':      {'in_progress', 'resolved', 'closed'},
    'resolved':       {'closed', 'in_progress'},
    'closed':         set(),
    'rejected':       set(),
}


def _transition_allowed(current: str, next_status: str) -> bool:
    allowed = VALID_TRANSITIONS.get(current, set())
    return next_status in allowed


def _compute_sla(category: ServiceRequestCategory | None, priority: str) -> str | None:
    hours = category.sla_hours if category else 48
    if priority in ('urgent', 'emergency'):
        hours = max(1, hours // 4)
    elif priority == 'high':
        hours = max(2, hours // 2)
    deadline = datetime.now(timezone.utc) + timedelta(hours=hours)
    return deadline.isoformat()


def _auto_route(category: ServiceRequestCategory | None) -> str | None:
    if category and category.department_id:
        return category.department_id
    return None


def _get_or_create_phase7_department(district_id: str, route: dict) -> Department:
    dept = Department.query.filter_by(
        district_id=district_id,
        code=route['department_code'],
    ).first()
    if dept:
        if dept.status != 'active':
            dept.status = 'active'
        return dept

    dept = Department(
        district_id=district_id,
        name=route['department_name'],
        code=route['department_code'],
        description='Auto-created for Phase 7 social comment service request routing.',
        wards=[],
        status='active',
    )
    db.session.add(dept)
    db.session.flush()
    return dept


def _get_or_create_phase7_category(
    district_id: str,
    route: dict,
    department: Department,
) -> ServiceRequestCategory:
    category = ServiceRequestCategory.query.filter_by(
        district_id=district_id,
        code=route['category_code'],
    ).first()
    if category:
        category.department_id = department.id
        category.default_priority = route['priority']
        category.sla_hours = route['sla_hours']
        category.is_active = True
        return category

    category = ServiceRequestCategory(
        district_id=district_id,
        name=route['category_name'],
        code=route['category_code'],
        description='Auto-created for Phase 7 social comment service request routing.',
        department_id=department.id,
        default_priority=route['priority'],
        sla_hours=route['sla_hours'],
        is_active=True,
    )
    db.session.add(category)
    db.session.flush()
    return category


# ---------------------------------------------------------------------------
# Category CRUD
# ---------------------------------------------------------------------------

def create_category(
    district_id: str, name: str, code: str, description: str | None = None,
    parent_id: str | None = None, department_id: str | None = None,
    default_priority: str = 'medium', sla_hours: int = 48,
) -> ServiceRequestCategory:
    existing = ServiceRequestCategory.query.filter_by(district_id=district_id, code=code).first()
    if existing:
        raise ValueError(f'Category with code "{code}" already exists.')
    cat = ServiceRequestCategory(
        district_id=district_id, name=name, code=code, description=description,
        parent_id=parent_id, department_id=department_id,
        default_priority=default_priority, sla_hours=sla_hours, is_active=True,
    )
    db.session.add(cat)
    db.session.commit()
    logger.info('Service request category created: %s (%s)', cat.id, code)
    return cat


def get_categories(district_id: str, page: int = 1, per_page: int = 20):
    return paginate_query(
        ServiceRequestCategory.query.filter_by(district_id=district_id)
        .order_by(ServiceRequestCategory.name.asc()),
        page, per_page,
    )


def update_category(district_id: str, category_id: str, **kwargs) -> ServiceRequestCategory:
    cat = ServiceRequestCategory.query.filter_by(id=category_id, district_id=district_id).first()
    if not cat:
        raise ValueError('Category not found.')
    for key in ('name', 'description', 'parent_id', 'department_id', 'default_priority', 'sla_hours', 'is_active'):
        if key in kwargs:
            setattr(cat, key, kwargs[key])
    db.session.commit()
    return cat


# ---------------------------------------------------------------------------
# Service Request CRUD
# ---------------------------------------------------------------------------

def create_service_request(
    district_id: str, category_id: str | None, title: str, description: str,
    citizen_id: str | None = None, citizen_phone: str | None = None,
    citizen_email: str | None = None, priority: str | None = None,
    location: str | None = None, ward: str | None = None,
    landmark: str | None = None, tags: list | None = None,
    department_id: str | None = None,
) -> ServiceRequest:
    if not title:
        raise ValueError('title is required.')
    if not description:
        raise ValueError('description is required.')

    if priority and priority not in REQUEST_PRIORITIES:
        raise ValueError(f'priority must be one of: {", ".join(REQUEST_PRIORITIES)}')

    category = None
    if category_id:
        category = ServiceRequestCategory.query.filter_by(
            id=category_id, district_id=district_id, is_active=True,
        ).first()
        if not category:
            raise ValueError('Category not found or inactive.')

    resolved_priority = priority or (category.default_priority if category else 'medium')
    resolved_dept = department_id or _auto_route(category)

    req = ServiceRequest(
        district_id=district_id,
        category_id=category_id,
        department_id=resolved_dept,
        citizen_id=citizen_id,
        title=title,
        description=description,
        priority=resolved_priority,
        status='submitted',
        location=location,
        ward=ward,
        landmark=landmark,
        citizen_phone=citizen_phone,
        citizen_email=citizen_email,
        sla_deadline=_compute_sla(category, resolved_priority),
        tags=tags or [],
    )
    db.session.add(req)
    db.session.flush()

    write_audit_log(
        district_id=district_id, actor_id=citizen_id,
        action='service_request.created',
        resource_type='service_request', resource_id=req.id,
        after_state=req.to_dict(),
    )
    db.session.commit()
    logger.info('Service request created: %s — %s', req.id, title[:60])
    return req


def create_service_request_from_social_comment(
    comment,
    analysis,
    issue_type: str | None = None,
) -> ServiceRequest | None:
    """Create one routed service request for an actionable social comment.

    Phase 7 supports water, road, electricity, garbage, and drainage issues.
    The ``analysis.service_request_id`` link makes the operation idempotent
    when analysis is re-run for the same comment.
    """
    issue = issue_type or getattr(analysis, 'issue_type', None)
    route = PHASE7_ISSUE_ROUTES.get(issue or '')
    if not route:
        return None

    if analysis.service_request_id:
        return ServiceRequest.query.filter_by(
            id=analysis.service_request_id,
            district_id=comment.district_id,
        ).first()

    if analysis.category not in ('complaint', 'negative'):
        return None

    department = _get_or_create_phase7_department(comment.district_id, route)
    category = _get_or_create_phase7_category(comment.district_id, route, department)
    priority = 'emergency' if comment.is_emergency else category.default_priority

    title = f"{route['category_name']} from social comment"
    description = (
        f"Auto-created from {comment.platform} comment {comment.platform_comment_id}.\n\n"
        f"Author: {comment.author_name or comment.author_username or 'Unknown'}\n"
        f"Comment: {comment.text}\n\n"
        f"AI summary: {analysis.summary or 'No summary available.'}"
    )
    tags = [
        'auto_created',
        'phase7',
        'social_comment',
        f'comment:{comment.id}',
        f'issue:{issue}',
    ]
    for keyword in analysis.keywords or []:
        value = str(keyword).strip().lower()
        if value and value not in tags:
            tags.append(value)

    req = ServiceRequest(
        district_id=comment.district_id,
        category_id=category.id,
        department_id=department.id,
        citizen_id=None,
        title=title,
        description=description,
        priority=priority,
        status='submitted',
        sla_deadline=_compute_sla(category, priority),
        tags=tags[:20],
    )
    db.session.add(req)
    db.session.flush()

    analysis.service_request_id = req.id

    write_audit_log(
        district_id=comment.district_id,
        actor_id=None,
        action='service_request.auto_created_from_social_comment',
        resource_type='service_request',
        resource_id=req.id,
        after_state={
            'request': req.to_dict(),
            'comment_id': comment.id,
            'issue_type': issue,
        },
    )
    logger.info(
        'Phase 7 service request created: %s from comment %s (%s)',
        req.id,
        comment.id,
        issue,
    )
    return req


def get_service_requests(
    district_id: str, page: int = 1, per_page: int = 20,
    status: str | None = None, priority: str | None = None,
    category_id: str | None = None, department_id: str | None = None,
    assigned_to: str | None = None, citizen_id: str | None = None,
    ward: str | None = None,
):
    query = ServiceRequest.query.filter_by(district_id=district_id)
    if status:
        query = query.filter(ServiceRequest.status == status)
    if priority:
        query = query.filter(ServiceRequest.priority == priority)
    if category_id:
        query = query.filter(ServiceRequest.category_id == category_id)
    if department_id:
        query = query.filter(ServiceRequest.department_id == department_id)
    if assigned_to:
        query = query.filter(ServiceRequest.assigned_to == assigned_to)
    if citizen_id:
        query = query.filter(ServiceRequest.citizen_id == citizen_id)
    if ward:
        query = query.filter(ServiceRequest.ward == ward)
    return paginate_query(
        query.order_by(ServiceRequest.created_at.desc()), page, per_page,
    )


def get_service_request(district_id: str, request_id: str) -> ServiceRequest:
    req = ServiceRequest.query.filter_by(id=request_id, district_id=district_id).first()
    if not req:
        raise ValueError('Service request not found.')
    return req


def update_service_request(
    district_id: str, request_id: str, actor_id: str | None = None, **kwargs,
) -> ServiceRequest:
    req = get_service_request(district_id, request_id)
    before = req.to_dict()

    allowed_fields = {'title', 'description', 'priority', 'location', 'ward',
                      'landmark', 'citizen_phone', 'citizen_email', 'tags', 'category_id'}
    for key, value in kwargs.items():
        if key in allowed_fields:
            if key == 'priority' and value not in REQUEST_PRIORITIES:
                raise ValueError(f'priority must be one of: {", ".join(REQUEST_PRIORITIES)}')
            setattr(req, key, value)

    req.tags = kwargs.get('tags', req.tags)

    write_audit_log(
        district_id=district_id, actor_id=actor_id,
        action='service_request.updated',
        resource_type='service_request', resource_id=request_id,
        before_state=before, after_state=req.to_dict(),
    )
    db.session.commit()
    return req


def delete_service_request(district_id: str, request_id: str, actor_id: str | None = None) -> None:
    req = get_service_request(district_id, request_id)
    db.session.delete(req)
    write_audit_log(
        district_id=district_id, actor_id=actor_id,
        action='service_request.deleted',
        resource_type='service_request', resource_id=request_id,
        before_state=req.to_dict(),
    )
    db.session.commit()
    logger.info('Service request deleted: %s', request_id)


# ---------------------------------------------------------------------------
# Assignment
# ---------------------------------------------------------------------------

def assign_service_request(
    district_id: str, request_id: str, assignee_id: str, actor_id: str | None = None,
) -> ServiceRequest:
    req = get_service_request(district_id, request_id)
    assignee = User.query.filter_by(id=assignee_id, district_id=district_id, status='active').first()
    if not assignee:
        raise ValueError('Assignee not found or inactive.')
    before = req.to_dict()
    req.assigned_to = assignee_id
    if req.status == 'submitted':
        req.status = 'acknowledged'
        req.acknowledged_at = datetime.now(timezone.utc).isoformat()

    _add_comment(req.id, district_id, actor_id,
                 f'Assigned to {assignee.full_name} ({assignee.email})', is_internal=True,
                 old_status=before['status'], new_status=req.status)

    write_audit_log(
        district_id=district_id, actor_id=actor_id,
        action='service_request.assigned',
        resource_type='service_request', resource_id=request_id,
        before_state=before, after_state=req.to_dict(),
    )
    db.session.commit()
    logger.info('Service request %s assigned to %s', request_id, assignee_id)
    return req


# ---------------------------------------------------------------------------
# Status Transition
# ---------------------------------------------------------------------------

def transition_status(
    district_id: str, request_id: str, new_status: str,
    comment: str | None = None, actor_id: str | None = None,
) -> ServiceRequest:
    req = get_service_request(district_id, request_id)
    if not _transition_allowed(req.status, new_status):
        raise ValueError(f'Cannot transition from "{req.status}" to "{new_status}".')

    before = req.to_dict()
    req.status = new_status

    now = datetime.now(timezone.utc).isoformat()
    if new_status == 'acknowledged':
        req.acknowledged_at = now
    elif new_status == 'resolved':
        req.resolved_at = now
    elif new_status == 'closed':
        req.closed_at = now
    elif new_status == 'escalated':
        req.is_escalated = True

    _add_comment(req.id, district_id, actor_id, comment or f'Status changed to {new_status}',
                 is_internal=False, old_status=before['status'], new_status=new_status)

    write_audit_log(
        district_id=district_id, actor_id=actor_id,
        action=f'service_request.{new_status}',
        resource_type='service_request', resource_id=request_id,
        before_state=before, after_state=req.to_dict(),
    )
    db.session.commit()
    logger.info('Service request %s: %s → %s', request_id, before['status'], new_status)
    return req


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

def add_comment(
    district_id: str, request_id: str, author_id: str | None,
    comment: str, is_internal: bool = False,
) -> ServiceRequestComment:
    req = get_service_request(district_id, request_id)
    return _add_comment(request_id, district_id, author_id, comment, is_internal)


def _add_comment(
    request_id: str, district_id: str, author_id: str | None,
    comment: str, is_internal: bool = False,
    old_status: str | None = None, new_status: str | None = None,
) -> ServiceRequestComment:
    c = ServiceRequestComment(
        district_id=district_id,
        request_id=request_id,
        author_id=author_id,
        comment=comment,
        is_internal=is_internal,
        old_status=old_status,
        new_status=new_status,
    )
    db.session.add(c)
    db.session.flush()
    return c


def get_comments(district_id: str, request_id: str, page: int = 1, per_page: int = 50):
    req = get_service_request(district_id, request_id)
    return paginate_query(
        ServiceRequestComment.query
        .filter_by(district_id=district_id, request_id=request_id)
        .order_by(ServiceRequestComment.created_at.asc()),
        page, per_page,
    )
