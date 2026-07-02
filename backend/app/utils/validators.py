"""Input validation utilities used across request/service layers."""
import re

EMAIL_RE = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')
PHONE_RE = re.compile(r'^\+?[1-9]\d{6,14}$')
SLUG_RE  = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')


def is_valid_email(value: str) -> bool:
    """Return True if *value* looks like a valid e-mail address."""
    return bool(EMAIL_RE.match(value)) if value else False


def is_valid_phone(value: str) -> bool:
    """Return True if *value* looks like an E.164 phone number."""
    return bool(PHONE_RE.match(value)) if value else False


def is_valid_slug(value: str) -> bool:
    """Return True if *value* is a valid URL-safe slug (lowercase, hyphens)."""
    return bool(SLUG_RE.match(value)) if value else False


def validate_pagination_params(page, per_page, max_per_page=100):
    """Normalise and clamp pagination parameters.

    Args:
        page:         Requested page number (1-based).
        per_page:     Requested page size.
        max_per_page: Maximum allowed page size.

    Returns:
        Tuple (page: int, per_page: int).
    """
    try:
        page = max(1, int(page))
    except (TypeError, ValueError):
        page = 1

    try:
        per_page = max(1, min(int(per_page), max_per_page))
    except (TypeError, ValueError):
        per_page = 20

    return page, per_page
