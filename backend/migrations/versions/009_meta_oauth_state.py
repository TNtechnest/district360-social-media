"""Migration 009: Add meta_oauth_state table.

Revision ID: 009_meta_oauth_state
Revises: 008_social_comments
Create Date: 2026-07-01
"""
from alembic import op
import sqlalchemy as sa

revision      = '009_meta_oauth_state'
down_revision = '008_social_comments'
branch_labels = None
depends_on    = None


def upgrade():
    op.create_table(
        'meta_oauth_state',
        sa.Column('id',               sa.String(36),  primary_key=True),
        sa.Column('district_id',      sa.String(36),
                  sa.ForeignKey('district.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('state',            sa.String(128), nullable=False,  unique=True, index=True),
        sa.Column('initiated_by',     sa.String(36),
                  sa.ForeignKey('user.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('platform_scope',   sa.String(30),  nullable=False),
        sa.Column('expires_at',       sa.String(50),  nullable=False),
        sa.Column('is_used',          sa.Boolean(),   nullable=False, server_default='false'),
        sa.Column('connection_label', sa.String(255), nullable=True),
        sa.Column('created_at',       sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at',       sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table('meta_oauth_state')
