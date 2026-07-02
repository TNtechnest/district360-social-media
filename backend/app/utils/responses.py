"""Standard JSON response helpers for District360 API.

Every endpoint should go through these helpers to ensure a consistent
envelope structure across the entire API surface:

    Success:  { "success": true,  "data": ...,  "meta": ... }
    Error:    { "success": false, "error": { "code": ..., "message": ... } }
"""
from flask import jsonify


def success_response(data=None, message=None, status_code=200, meta=None):
    """Return a standardised success JSON response.

    Args:
        data:        Serialisable payload (dict, list, or None).
        message:     Optional human-readable message.
        status_code: HTTP status code (default 200).
        meta:        Optional pagination / metadata dict.

    Returns:
        Flask Response with JSON body and the given status code.
    """
    body = {'success': True}
    if message:
        body['message'] = message
    if data is not None:
        body['data'] = data
    if meta:
        body['meta'] = meta
    return jsonify(body), status_code


def error_response(message, status_code=400, code=None, details=None):
    """Return a standardised error JSON response.

    Args:
        message:     Human-readable error description.
        status_code: HTTP status code (default 400).
        code:        Machine-readable error code string.
        details:     Optional dict with extra context (field errors, etc.).

    Returns:
        Flask Response with JSON body and the given status code.
    """
    error_body = {'message': message}
    if code:
        error_body['code'] = code
    if details:
        error_body['details'] = details

    body = {'success': False, 'error': error_body}
    return jsonify(body), status_code


def paginated_response(items, pagination, message=None):
    """Return a paginated success response.

    Args:
        items:      List of serialised items.
        pagination: SQLAlchemy Pagination object.
        message:    Optional human-readable message.

    Returns:
        Flask Response with data + pagination meta.
    """
    meta = {
        'page': pagination.page,
        'per_page': pagination.per_page,
        'total': pagination.total,
        'pages': pagination.pages,
        'has_next': pagination.has_next,
        'has_prev': pagination.has_prev,
    }
    return success_response(data=items, message=message, meta=meta)
