"""API v1 blueprint package.

Registers all sub-blueprints under the /api/v1 namespace.

Phase 1: auth, districts, users, departments, audit
Phase 2: ai, social (accounts, content, media, schedules, collector, comments, meta_oauth)
Phase 3: analytics, reports, workflow, notifications, monitoring
"""
from flask import Blueprint, jsonify

api_v1 = Blueprint('api_v1', __name__)


@api_v1.route('/ping')
def ping():
    """Liveness probe for the API v1 namespace."""
    return jsonify({'message': 'pong', 'version': 'v1'})


def register_v1_blueprints(app):
    """Attach all v1 sub-blueprints to the given Flask app."""

    # ---- Phase 1 — Core ----
    from app.api.v1.auth        import auth_bp
    import app.api.v1.auth_ext  # registers OTP/OAuth/session routes on auth_bp  # noqa: F401
    from app.api.v1.districts   import districts_bp
    from app.api.v1.users       import users_bp
    from app.api.v1.departments import departments_bp
    from app.api.v1.audit       import audit_bp

    # ---- Phase 2 — Social + AI ----
    from app.api.v1.ai                        import ai_bp
    from app.api.v1.social.accounts           import accounts_bp
    from app.api.v1.social.content            import content_bp
    from app.api.v1.social.media              import media_bp
    from app.api.v1.social.schedules          import schedules_bp
    from app.api.v1.social.collector          import collector_bp
    from app.api.v1.social.collector_dashboard import collector_dashboard_bp
    from app.api.v1.social.comments           import comments_bp
    from app.api.v1.social.meta_oauth         import meta_oauth_bp

    # ---- Phase 3 — Analytics, Reports, Workflow, Notifications, Monitoring ----
    from app.api.v1.analytics         import analytics_bp
    from app.api.v1.reports           import reports_bp
    from app.api.v1.workflow          import workflow_bp
    from app.api.v1.notifications     import notifications_bp
    from app.api.v1.monitoring        import monitoring_bp
    from app.api.v1.service_requests  import sr_bp
    from app.api.v1.uploads           import uploads_bp
    from app.api.v1.payments          import payments_bp

    # Social sub-blueprints nested under /social  (registered ONCE each)
    from flask import Blueprint as _BP
    social_bp = _BP('social', __name__, url_prefix='/social')
    for bp in (
        accounts_bp, content_bp, media_bp, schedules_bp,
        collector_bp, collector_dashboard_bp, comments_bp, meta_oauth_bp,
    ):
        social_bp.register_blueprint(bp)

    # Register all top-level blueprints
    for bp in (
        auth_bp, districts_bp, users_bp, departments_bp, audit_bp,
        ai_bp, social_bp,
        analytics_bp, reports_bp, workflow_bp, notifications_bp, monitoring_bp,
        sr_bp, uploads_bp, payments_bp,
    ):
        api_v1.register_blueprint(bp)


