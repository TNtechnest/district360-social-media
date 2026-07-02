"""Department management service.

Handles CRUD operations for departments within a district tenant.
"""
import logging

from app.extensions import db
from app.models.department import Department
from app.services.audit_service import write_audit_log
from app.utils.db import paginate_query

logger = logging.getLogger(__name__)


def get_departments(district_id: str, page: int = 1, per_page: int = 20,
                    status: str | None = None, search: str | None = None):
    """Return a paginated list of departments in the given district.

    Args:
        district_id: Tenant scope.
        page:        Page number (1-based).
        per_page:    Page size (max 100).
        status:      Optional status filter.
        search:      Optional substring match against name / code.

    Returns:
        SQLAlchemy Pagination object.
    """
    query = Department.query.filter_by(district_id=district_id)

    if status:
        query = query.filter(Department.status == status)

    if search:
        like = f'%{search}%'
        query = query.filter(
            db.or_(
                Department.name.ilike(like),
                Department.code.ilike(like),
            )
        )

    query = query.order_by(Department.name.asc())
    return paginate_query(query, page=page, per_page=per_page)


def get_department_by_id(district_id: str, department_id: str) -> Department:
    """Fetch a single department, enforcing tenant scope.

    Args:
        district_id:   Tenant scope.
        department_id: Department UUID.

    Returns:
        Department model instance.

    Raises:
        ValueError: If not found.
    """
    dept = Department.query.filter_by(id=department_id, district_id=district_id).first()
    if not dept:
        raise ValueError('Department not found.')
    return dept


def create_department(
    district_id: str,
    name: str,
    code: str,
    description: str | None = None,
    wards: list | None = None,
    head_id: str | None = None,
    actor_id: str | None = None,
) -> Department:
    """Create a new department within a district.

    Args:
        district_id: Tenant scope.
        name:        Full department name.
        code:        Short unique code within the district (e.g. ``'WATER'``).
        description: Optional description.
        wards:       Optional list of ward names/IDs this dept serves.
        head_id:     Optional UUID of the department head (User).
        actor_id:    UUID of the admin performing the action.

    Returns:
        Newly created Department model instance.

    Raises:
        ValueError: If code is already taken in this district.
    """
    code = code.upper().strip()

    existing = Department.query.filter_by(district_id=district_id, code=code).first()
    if existing:
        raise ValueError(f"A department with code '{code}' already exists in this district.")

    dept = Department(
        district_id=district_id,
        name=name.strip(),
        code=code,
        description=description,
        wards=wards or [],
        head_id=head_id,
        status='active',
    )
    db.session.add(dept)
    db.session.flush()

    write_audit_log(
        district_id=district_id,
        actor_id=actor_id,
        action='department.created',
        resource_type='department',
        resource_id=dept.id,
        after_state=dept.to_dict(),
    )
    db.session.commit()
    logger.info('Department created: %s (%s) in district %s', dept.id, dept.code, district_id)
    return dept


def update_department(
    district_id: str,
    department_id: str,
    actor_id: str | None = None,
    **fields,
) -> Department:
    """Update allowed fields on a department.

    Allowed fields: ``name``, ``description``, ``wards``, ``head_id``, ``status``.

    Args:
        district_id:   Tenant scope.
        department_id: Department UUID.
        actor_id:      UUID of the admin making the change.
        **fields:      Key/value pairs of fields to update.

    Returns:
        Updated Department model instance.

    Raises:
        ValueError: If not found or invalid field provided.
    """
    dept = get_department_by_id(district_id, department_id)
    before = dept.to_dict()

    allowed = {'name', 'description', 'wards', 'head_id', 'status'}
    for key, value in fields.items():
        if key not in allowed:
            raise ValueError(f"Field '{key}' cannot be updated via this method.")
        setattr(dept, key, value)

    write_audit_log(
        district_id=district_id,
        actor_id=actor_id,
        action='department.updated',
        resource_type='department',
        resource_id=department_id,
        before_state=before,
        after_state=dept.to_dict(),
    )
    db.session.commit()
    return dept


def deactivate_department(
    district_id: str,
    department_id: str,
    actor_id: str | None = None,
) -> Department:
    """Set department status to ``'inactive'``.

    Args:
        district_id:   Tenant scope.
        department_id: Department UUID.
        actor_id:      UUID of the admin performing the action.

    Returns:
        Updated Department model instance.
    """
    return update_department(
        district_id, department_id, actor_id=actor_id, status='inactive'
    )
