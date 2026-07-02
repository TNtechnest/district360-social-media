"""Migration 008: Add social_comment and comment_analysis tables.
Also adds social_comment_count to social_post.

Revision ID: 008_social_comments
Revises: 007_auth_ext
Create Date: 2026-06-27
"""
from alembic import op
import sqlalchemy as sa

revision      = '008_social_comments'
down_revision = '007_auth_ext'
branch_labels = None
depends_on    = None


def upgrade():
    # ---------------------------------------------------------------- social_comment
    op.create_table(
        'social_comment',
        sa.Column('id',                  sa.String(36),  primary_key=True),
        sa.Column('district_id',         sa.String(36),
                  sa.ForeignKey('district.id',       ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('post_id',             sa.String(36),
                  sa.ForeignKey('social_post.id',    ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('parent_comment_id',   sa.String(36),
                  sa.ForeignKey('social_comment.id', ondelete='CASCADE'),
                  nullable=True, index=True),
        # Platform identity
        sa.Column('platform',            sa.String(30),  nullable=False, index=True),
        sa.Column('platform_comment_id', sa.String(255), nullable=False),
        sa.Column('author_platform_id',  sa.String(255), nullable=True),
        sa.Column('author_name',         sa.String(255), nullable=True),
        sa.Column('author_username',     sa.String(255), nullable=True),
        sa.Column('author_profile_url',  sa.Text(),      nullable=True),
        # Content
        sa.Column('text',                sa.Text(),      nullable=False),
        sa.Column('platform_created_at', sa.String(50),  nullable=True),
        sa.Column('likes',               sa.Integer(),   nullable=False, server_default='0'),
        sa.Column('reply_count',         sa.Integer(),   nullable=False, server_default='0'),
        # Moderation
        sa.Column('moderation_status',   sa.String(20),  nullable=False,
                  server_default='visible', index=True),
        sa.Column('is_replied',          sa.Boolean(),   nullable=False, server_default='false'),
        sa.Column('reply_text',          sa.Text(),      nullable=True),
        sa.Column('reply_platform_id',   sa.String(255), nullable=True),
        sa.Column('replied_at',          sa.String(50),  nullable=True),
        sa.Column('replied_by_id',       sa.String(36),
                  sa.ForeignKey('user.id', ondelete='SET NULL'), nullable=True),
        # AI summary columns (mirrors CommentAnalysis for fast querying)
        sa.Column('language',            sa.String(20),  nullable=False,
                  server_default='unknown', index=True),
        sa.Column('sentiment',           sa.String(20),  nullable=True, index=True),
        sa.Column('sentiment_score',     sa.Float(),     nullable=True),
        sa.Column('is_complaint',        sa.Boolean(),   nullable=False,
                  server_default='false', index=True),
        sa.Column('is_emergency',        sa.Boolean(),   nullable=False,
                  server_default='false', index=True),
        sa.Column('is_spam',             sa.Boolean(),   nullable=False,
                  server_default='false', index=True),
        sa.Column('suggested_reply',     sa.Text(),      nullable=True),
        sa.Column('ai_status',           sa.String(20),  nullable=False,
                  server_default='pending', index=True),
        # Timestamps
        sa.Column('created_at',          sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at',          sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            'post_id', 'platform_comment_id',
            name='uix_social_comment_post_platform_comment',
        ),
    )

    # ---------------------------------------------------------------- comment_analysis
    op.create_table(
        'comment_analysis',
        sa.Column('id',                   sa.String(36), primary_key=True),
        sa.Column('district_id',          sa.String(36),
                  sa.ForeignKey('district.id',        ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('comment_id',           sa.String(36),
                  sa.ForeignKey('social_comment.id',  ondelete='CASCADE'),
                  nullable=False, unique=True, index=True),
        # Language
        sa.Column('language',             sa.String(20),  nullable=False, server_default='unknown'),
        # Sentiment
        sa.Column('sentiment_label',      sa.String(20),  nullable=True, index=True),
        sa.Column('sentiment_score',      sa.Float(),     nullable=True),
        # Complaint
        sa.Column('is_complaint',         sa.Boolean(),   nullable=False,
                  server_default='false', index=True),
        sa.Column('complaint_confidence', sa.Float(),     nullable=False, server_default='0'),
        sa.Column('complaint_keywords',   sa.JSON(),      nullable=False, server_default='[]'),
        # Emergency
        sa.Column('is_emergency',         sa.Boolean(),   nullable=False,
                  server_default='false', index=True),
        sa.Column('emergency_confidence', sa.Float(),     nullable=False, server_default='0'),
        sa.Column('emergency_keywords',   sa.JSON(),      nullable=False, server_default='[]'),
        # Spam
        sa.Column('is_spam',              sa.Boolean(),   nullable=False,
                  server_default='false', index=True),
        sa.Column('spam_confidence',      sa.Float(),     nullable=False, server_default='0'),
        sa.Column('spam_reasons',         sa.JSON(),      nullable=False, server_default='[]'),
        # Trends
        sa.Column('trend_tags',           sa.JSON(),      nullable=False, server_default='[]'),
        sa.Column('top_topic',            sa.String(100), nullable=True),
        # Reply suggestion
        sa.Column('suggested_reply',      sa.Text(),      nullable=True),
        sa.Column('reply_category',       sa.String(30),  nullable=True),
        # Processing metadata
        sa.Column('status',               sa.String(20),  nullable=False,
                  server_default='pending', index=True),
        sa.Column('error_message',        sa.Text(),      nullable=True),
        sa.Column('raw_result',           sa.JSON(),      nullable=False, server_default='{}'),
        sa.Column('processing_ms',        sa.Integer(),   nullable=False, server_default='0'),
        # Timestamps
        sa.Column('created_at',           sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at',           sa.DateTime(timezone=True), nullable=False),
    )

    # ---------------------------------------------------------------- add column to social_post
    op.add_column(
        'social_post',
        sa.Column('social_comment_count', sa.Integer(), nullable=False, server_default='0'),
    )


def downgrade():
    op.drop_column('social_post', 'social_comment_count')
    op.drop_table('comment_analysis')
    op.drop_table('social_comment')
