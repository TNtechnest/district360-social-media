"""Migration 010: Add Phase 6 comment analysis outputs.

Revision ID: 010_phase6_comment_analysis
Revises: 009_meta_oauth_state
Create Date: 2026-07-01
"""
from alembic import op
import sqlalchemy as sa

revision      = '010_phase6_comment_analysis'
down_revision = '009_meta_oauth_state'
branch_labels = None
depends_on    = None


def upgrade():
    op.add_column(
        'comment_analysis',
        sa.Column('category', sa.String(30), nullable=False, server_default='neutral'),
    )
    op.add_column(
        'comment_analysis',
        sa.Column('keywords', sa.JSON(), nullable=False, server_default='[]'),
    )
    op.add_column(
        'comment_analysis',
        sa.Column('summary', sa.Text(), nullable=True),
    )
    op.create_index('ix_comment_analysis_category', 'comment_analysis', ['category'])


def downgrade():
    op.drop_index('ix_comment_analysis_category', table_name='comment_analysis')
    op.drop_column('comment_analysis', 'summary')
    op.drop_column('comment_analysis', 'keywords')
    op.drop_column('comment_analysis', 'category')
