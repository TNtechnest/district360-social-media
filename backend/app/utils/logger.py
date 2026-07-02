"""Structured logging configuration for District360.

Sets up a JSON-friendly formatter in production and a human-readable one
in development.  Call ``configure_logging(app)`` from the app factory.
"""
import logging
import sys
from flask import request, g


class RequestContextFilter(logging.Filter):
    """Inject request context into every log record when inside a request."""

    def filter(self, record):
        try:
            record.request_id = getattr(g, 'request_id', '-')
            record.remote_addr = request.remote_addr if request else '-'
            record.method     = request.method if request else '-'
            record.path       = request.path if request else '-'
        except RuntimeError:
            # Outside application / request context
            record.request_id = '-'
            record.remote_addr = '-'
            record.method = '-'
            record.path = '-'
        return True


DEVELOPMENT_FORMAT = (
    '%(asctime)s  %(levelname)-8s  [%(name)s]  '
    '%(remote_addr)s %(method)s %(path)s  —  %(message)s'
)

PRODUCTION_FORMAT = (
    '{'
    '"time":"%(asctime)s",'
    '"level":"%(levelname)s",'
    '"logger":"%(name)s",'
    '"request_id":"%(request_id)s",'
    '"addr":"%(remote_addr)s",'
    '"method":"%(method)s",'
    '"path":"%(path)s",'
    '"message":"%(message)s"'
    '}'
)


def configure_logging(app):
    """Configure application-level logging based on the active environment.

    Args:
        app: The Flask application instance.
    """
    log_level_name = app.config.get('LOG_LEVEL', 'INFO').upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    is_production = not app.debug and not app.testing
    fmt = PRODUCTION_FORMAT if is_production else DEVELOPMENT_FORMAT

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    handler.setFormatter(logging.Formatter(fmt))
    handler.addFilter(RequestContextFilter())

    # Replace default Flask / root logger handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(log_level)
    root_logger.addHandler(handler)

    # Quiet noisy third-party loggers in production
    if is_production:
        logging.getLogger('werkzeug').setLevel(logging.WARNING)
        logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    else:
        logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

    app.logger.info(
        'Logging configured — level=%s  env=%s',
        log_level_name,
        app.config.get('FLASK_ENV', 'development'),
    )
