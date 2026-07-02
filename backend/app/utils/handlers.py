"""Global error handlers for the District360 Flask application.

All unhandled exceptions and HTTP errors are caught here and returned
as consistent JSON envelopes using the shared response helpers.
"""
import logging
from flask import jsonify, request
from werkzeug.exceptions import HTTPException
from sqlalchemy.exc import IntegrityError, OperationalError

logger = logging.getLogger(__name__)


def register_error_handlers(app):
    """Attach all error handlers to the Flask application."""

    # ------------------------------------------------------------------ 400
    @app.errorhandler(400)
    def bad_request(err):
        return _json_error('Bad request.', 400, 'BAD_REQUEST')

    # ------------------------------------------------------------------ 401
    @app.errorhandler(401)
    def unauthorized(err):
        return _json_error('Authentication required.', 401, 'UNAUTHORIZED')

    # ------------------------------------------------------------------ 403
    @app.errorhandler(403)
    def forbidden(err):
        return _json_error('You do not have permission to perform this action.', 403, 'FORBIDDEN')

    # ------------------------------------------------------------------ 404
    @app.errorhandler(404)
    def not_found(err):
        return _json_error(f"The requested resource was not found: {request.path}", 404, 'NOT_FOUND')

    # ------------------------------------------------------------------ 405
    @app.errorhandler(405)
    def method_not_allowed(err):
        return _json_error(
            f"Method {request.method} is not allowed on this endpoint.", 405, 'METHOD_NOT_ALLOWED'
        )

    # ------------------------------------------------------------------ 409
    @app.errorhandler(409)
    def conflict(err):
        return _json_error('Resource conflict.', 409, 'CONFLICT')

    # ------------------------------------------------------------------ 422
    @app.errorhandler(422)
    def unprocessable(err):
        return _json_error('Unprocessable entity.', 422, 'UNPROCESSABLE_ENTITY')

    # ------------------------------------------------------------------ 429
    @app.errorhandler(429)
    def too_many_requests(err):
        return _json_error('Rate limit exceeded. Please slow down.', 429, 'RATE_LIMIT_EXCEEDED')

    # ------------------------------------------------------------------ 500
    @app.errorhandler(500)
    def internal_server_error(err):
        logger.exception('Unhandled internal server error: %s', err)
        return _json_error('An unexpected error occurred. Please try again later.', 500, 'INTERNAL_SERVER_ERROR')

    # ------------------------------------------------------------------ Generic HTTP
    @app.errorhandler(HTTPException)
    def handle_http_exception(err):
        return _json_error(err.description, err.code, err.name.upper().replace(' ', '_'))

    # ------------------------------------------------------------------ SQLAlchemy
    @app.errorhandler(IntegrityError)
    def handle_integrity_error(err):
        logger.warning('Database integrity error: %s', err.orig)
        return _json_error(
            'A resource with this data already exists or a required reference is missing.',
            409,
            'INTEGRITY_ERROR',
        )

    @app.errorhandler(OperationalError)
    def handle_operational_error(err):
        logger.error('Database operational error: %s', err)
        return _json_error('Database is temporarily unavailable.', 503, 'DB_UNAVAILABLE')


def _json_error(message, status_code, code=None):
    """Build a JSON error response dict."""
    body = {
        'success': False,
        'error': {
            'message': message,
            'code': code or str(status_code),
            'path': request.path,
            'method': request.method,
        },
    }
    response = jsonify(body)
    response.status_code = status_code
    return response
