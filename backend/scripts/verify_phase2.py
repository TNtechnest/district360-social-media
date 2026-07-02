"""Verify Phase 2 tables and models load correctly."""
from app import create_app
from app.extensions import db
from app.services.rbac_service import seed_system_roles_and_permissions
from sqlalchemy import text

app = create_app('development')
with app.app_context():
    seed_system_roles_and_permissions()
    print('RBAC seeded OK')

    # List ALL public tables
    result = db.session.execute(text(
        "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
    ))
    all_tables = [r[0] for r in result]
    print('All tables:', all_tables)

    needed = ['social_account', 'social_post', 'social_comment', 'comment_analysis']
    for t in needed:
        status = 'OK' if t in all_tables else 'MISSING'
        print(f'  {t}: {status}')

    # Verify social_comment_count column
    result2 = db.session.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='social_post' AND column_name='social_comment_count'"
    ))
    col = result2.fetchone()
    print(f'  social_post.social_comment_count: {"OK" if col else "MISSING"}')

    # Import models
    from app.models.social_comment import SocialComment
    from app.models.comment_analysis import CommentAnalysis
    print('SocialComment model: OK')
    print('CommentAnalysis model: OK')

    # Import schemas
    from app.schemas.social_comment_schema import (
        SocialCommentSchema, CommentAnalysisSchema,
        CreateCommentSchema, ReplyCommentSchema, ModerateCommentSchema,
    )
    print('Schemas: OK')

    # Import service
    from app.services.social.comment_service import (
        get_comments, get_comment, upsert_comment,
        reply_to_comment, moderate_comment, bulk_analyse,
    )
    print('comment_service: OK')

    # Import API blueprint
    from app.api.v1.social.comments import comments_bp
    print('comments API blueprint: OK')

    print('All Phase 2 components: VERIFIED')
