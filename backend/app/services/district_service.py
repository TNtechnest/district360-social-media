"""District (tenant) management service.

Handles creation, retrieval, update, and status management for district tenants.
Super-admin-only operations are enforced at the API layer via RBAC decorators.
"""
import logging

from app.extensions import db
from app.models.district import District
from app.services.audit_service import write_audit_log
from app.utils.db import paginate_query
from app.utils.validators import is_valid_slug

logger = logging.getLogger(__name__)


def get_districts(page: int = 1, per_page: int = 20,
                  status: str | None = None, search: str | None = None):
    """Return a paginated list of all districts.

    Args:
        page:     Page number (1-based).
        per_page: Page size (max 100).
        status:   Optional status filter.
        search:   Optional substring match against name / slug.

    Returns:
        SQLAlchemy Pagination object.
    """
    query = District.query

    if status:
        query = query.filter(District.status == status)

    if search:
        like = f'%{search}%'
        query = query.filter(
            db.or_(
                District.name.ilike(like),
                District.slug.ilike(like),
            )
        )

    query = query.order_by(District.created_at.desc())
    return paginate_query(query, page=page, per_page=per_page)


def get_district_by_id(district_id: str) -> District:
    """Fetch a district by its UUID.

    Args:
        district_id: District UUID.

    Returns:
        District model instance.

    Raises:
        ValueError: If not found.
    """
    district = District.query.get(district_id)
    if not district:
        raise ValueError('District not found.')
    return district


def get_district_by_slug(slug: str) -> District:
    """Fetch a district by its URL-safe slug.

    Args:
        slug: Lowercase slug string.

    Returns:
        District model instance.

    Raises:
        ValueError: If not found.
    """
    district = District.query.filter_by(slug=slug).first()
    if not district:
        raise ValueError(f"District with slug '{slug}' not found.")
    return district


def create_district(
    name: str,
    slug: str,
    region: str | None = None,
    config: dict | None = None,
    actor_id: str | None = None,
) -> District:
    """Provision a new district tenant.

    Args:
        name:     Human-readable district name.
        slug:     URL-safe unique identifier (lowercase, hyphens).
        region:   Optional geographic region string.
        config:   Optional tenant configuration dict.
        actor_id: UUID of the Super Admin creating the district.

    Returns:
        Newly created District model instance.

    Raises:
        ValueError: If the slug is invalid or already taken.
    """
    slug = slug.lower().strip()

    if not is_valid_slug(slug):
        raise ValueError(
            "Slug must contain only lowercase letters, digits, and hyphens (e.g. 'metro-north')."
        )

    existing = District.query.filter_by(slug=slug).first()
    if existing:
        raise ValueError(f"A district with slug '{slug}' already exists.")

    district = District(
        name=name.strip(),
        slug=slug,
        region=region,
        config=config or {},
        status='active',
    )
    db.session.add(district)
    db.session.flush()

    write_audit_log(
        district_id=district.id,
        actor_id=actor_id,
        action='district.created',
        resource_type='district',
        resource_id=district.id,
        after_state=district.to_dict(),
    )
    db.session.commit()
    logger.info('District created: %s (%s)', district.id, district.slug)
    return district


def update_district(
    district_id: str,
    actor_id: str | None = None,
    **fields,
) -> District:
    """Update allowed fields on a district.

    Allowed fields: ``name``, ``region``, ``config``, ``status``.

    Args:
        district_id: District UUID.
        actor_id:    UUID of the admin making the change.
        **fields:    Key/value pairs of fields to update.

    Returns:
        Updated District model instance.

    Raises:
        ValueError: If district not found or invalid field provided.
    """
    district = get_district_by_id(district_id)
    before = district.to_dict()

    allowed = {'name', 'region', 'config', 'status'}
    for key, value in fields.items():
        if key not in allowed:
            raise ValueError(f"Field '{key}' cannot be updated via this method.")
        setattr(district, key, value)

    write_audit_log(
        district_id=district_id,
        actor_id=actor_id,
        action='district.updated',
        resource_type='district',
        resource_id=district_id,
        before_state=before,
        after_state=district.to_dict(),
    )
    db.session.commit()
    return district


def deactivate_district(district_id: str, actor_id: str | None = None) -> District:
    """Set a district status to ``'inactive'``.

    Args:
        district_id: District UUID.
        actor_id:    UUID of the Super Admin performing the action.

    Returns:
        Updated District model instance.
    """
    return update_district(district_id, actor_id=actor_id, status='inactive')
