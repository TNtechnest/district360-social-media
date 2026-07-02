"""District360 Flask application factory."""
from flask import Flask, jsonify

from app.config import CONFIG_MAP
from app.extensions import db, migrate, jwt, bcrypt, limiter, cors
from app.utils.handlers import register_error_handlers
from app.utils.logger import configure_logging


def create_app(config_name=None):
    """Create and configure the Flask application.

    Args:
        config_name: One of ``'development'``, ``'testing'``, ``'production'``,
                     or ``'default'``.  Reads ``FLASK_ENV`` from the environment
                     if not supplied.

    Returns:
        Configured Flask application instance.
    """
    app = Flask(__name__)
    config_name = config_name or 'default'
    app.config.from_object(CONFIG_MAP.get(config_name, CONFIG_MAP['default']))

    configure_logging(app)
    _register_extensions(app)
    _register_jwt_callbacks(app)
    _register_blueprints(app)
    register_error_handlers(app)

    @app.route('/health')
    def health_check():
        """Platform health probe — used by load balancers / k8s."""
        from app.utils.db import check_database_connection
        db_ok = check_database_connection()
        status = 'ok' if db_ok else 'degraded'
        code   = 200 if db_ok else 503
        return jsonify({
            'status': status,
            'service': 'district360-api',
            'db': 'connected' if db_ok else 'unreachable',
        }), code

    return app


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _register_extensions(app):
    """Initialise all Flask extensions."""
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    bcrypt.init_app(app)
    limiter.init_app(app)
    cors.init_app(app, resources={r'/api/*': {'origins': '*'}})


def _register_jwt_callbacks(app):
    """Register JWT Manager callbacks (token blocklist, error handlers)."""
    from app.services.auth_service import is_token_revoked
    from app.utils.responses import error_response

    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        return is_token_revoked(jwt_header, jwt_payload)

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return error_response('Token has been revoked. Please log in again.', 401, 'TOKEN_REVOKED')

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return error_response('Token has expired. Please refresh or log in again.', 401, 'TOKEN_EXPIRED')

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        if 'Only refresh tokens are allowed' in error or 'Only non-refresh tokens are allowed' in error:
            return error_response(error, 422, 'INVALID_TOKEN_TYPE')
        return error_response('Invalid token.', 401, 'INVALID_TOKEN')

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return error_response('Authorization token is required.', 401, 'MISSING_TOKEN')


def _register_blueprints(app):
    """Register API blueprints."""
    from app.api.v1 import api_v1, register_v1_blueprints
    register_v1_blueprints(app)
    app.register_blueprint(api_v1, url_prefix='/api/v1')
