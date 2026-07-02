"""Database utilities for PostgreSQL connectivity and tenant scoping."""
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db


def check_database_connection():
    """Verify PostgreSQL connectivity."""
    try:
        db.session.execute(text('SELECT 1'))
        return True
    except SQLAlchemyError:
        return False


def get_tenant_query_filter(model_class, district_id):
    """Return a tenant-scoped query filter.

    Enforces multi-tenant isolation by ensuring every query
    includes the district_id predicate.
    """
    return model_class.query.filter(model_class.district_id == district_id)


def paginate_query(query, page=1, per_page=20):
    """Apply standard pagination to a SQLAlchemy query."""
    per_page = min(max(per_page, 1), 100)
    return query.paginate(page=page, per_page=per_page, error_out=False)
