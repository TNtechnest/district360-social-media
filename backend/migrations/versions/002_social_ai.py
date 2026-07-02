"""Migration 002: Add social media and AI tables.

Revision ID: 002_social_ai
Revises: 001_initial
Create Date: 2026-06-23
"""
from alembic import op
import sqlalchemy as sa

revision = '002_social_ai'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade():
    # ------------------------------------------------------------------ social_account
    op.create_table(
        'social_account',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('district_id', sa.String(36), sa.ForeignKey('district.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('platform', sa.String(30), nullable=False, index=True),
        sa.Column('label', sa.String(255), nullable=False),
        sa.Column('platform_account_id', sa.String(255), nullable=False),
        sa.Column('username', sa.String(255), nullable=True),
        sa.Column('credentials', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('webhook_secret', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('config', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('district_id', 'platform', 'platform_account_id',
                            name='uix_social_account_district_platform_id'),
    )

    # ------------------------------------------------------------------ social_post
    op.create_table(
        'social_post',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('district_id', sa.String(36), sa.ForeignKey('district.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('account_id', sa.String(36), sa.ForeignKey('social_account.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('author_id', sa.String(36), sa.ForeignKey('user.id', ondelete='SET NULL'), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft', index=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('platform', sa.String(30), nullable=False, index=True),
        sa.Column('platform_post_id', sa.String(255), nullable=True),
        sa.Column('scheduled_at', sa.String(50), nullable=True),
        sa.Column('published_at', sa.String(50), nullable=True),
        sa.Column('likes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('comments', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('shares', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('views', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('meta', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('ai_analysis', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # ------------------------------------------------------------------ media_item
    op.create_table(
        'media_item',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('district_id', sa.String(36), sa.ForeignKey('district.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('post_id', sa.String(36), sa.ForeignKey('social_post.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('uploaded_by', sa.String(36), sa.ForeignKey('user.id', ondelete='SET NULL'), nullable=True),
        sa.Column('media_type', sa.String(20), nullable=False, index=True),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('mime_type', sa.String(100), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('thumbnail_url', sa.Text(), nullable=True),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('alt_text', sa.String(500), nullable=True),
        sa.Column('folder', sa.String(255), nullable=False, server_default='/', index=True),
        sa.Column('tags', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # ------------------------------------------------------------------ post_schedule
    op.create_table(
        'post_schedule',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('district_id', sa.String(36), sa.ForeignKey('district.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('account_id', sa.String(36), sa.ForeignKey('social_account.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('author_id', sa.String(36), sa.ForeignKey('user.id', ondelete='SET NULL'), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('platform', sa.String(30), nullable=False),
        sa.Column('content_template', sa.Text(), nullable=False),
        sa.Column('recurrence', sa.String(20), nullable=False, server_default='one_off'),
        sa.Column('next_run_at', sa.String(50), nullable=False, index=True),
        sa.Column('cron_expression', sa.String(100), nullable=True),
        sa.Column('timezone', sa.String(60), nullable=False, server_default='UTC'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('meta', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('status', sa.String(20), nullable=False, server_default='active', index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # ------------------------------------------------------------------ collected_post
    op.create_table(
        'collected_post',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('district_id', sa.String(36), sa.ForeignKey('district.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('account_id', sa.String(36), sa.ForeignKey('social_account.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('platform', sa.String(30), nullable=False, index=True),
        sa.Column('content_type', sa.String(30), nullable=False, index=True),
        sa.Column('platform_content_id', sa.String(255), nullable=False),
        sa.Column('author_platform_id', sa.String(255), nullable=True),
        sa.Column('author_username', sa.String(255), nullable=True),
        sa.Column('raw_text', sa.Text(), nullable=False),
        sa.Column('language', sa.String(20), nullable=False, server_default='unknown', index=True),
        sa.Column('platform_created_at', sa.String(50), nullable=True),
        sa.Column('likes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('comments', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('shares', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('sentiment', sa.String(20), nullable=True, index=True),
        sa.Column('sentiment_score', sa.Float(), nullable=True),
        sa.Column('is_complaint', sa.Boolean(), nullable=False, server_default='false', index=True),
        sa.Column('is_emergency', sa.Boolean(), nullable=False, server_default='false', index=True),
        sa.Column('is_spam', sa.Boolean(), nullable=False, server_default='false', index=True),
        sa.Column('trend_tags', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('suggested_reply', sa.Text(), nullable=True),
        sa.Column('ai_result', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('ai_status', sa.String(20), nullable=False, server_default='pending', index=True),
        sa.Column('review_status', sa.String(20), nullable=False, server_default='unreviewed', index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('account_id', 'platform_content_id', name='uix_collected_post_account_content'),
    )


def downgrade():
    op.drop_table('collected_post')
    op.drop_table('post_schedule')
    op.drop_table('media_item')
    op.drop_table('social_post')
    op.drop_table('social_account')
