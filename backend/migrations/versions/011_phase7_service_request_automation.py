"""Migration 011: Add Phase 7 service request automation links.

Revision ID: 011_phase7_service_request_automation
Revises: 010_phase6_comment_analysis
Create Date: 2026-07-01
"""
from alembic import op
import sqlalchemy as sa

revision      = '011_phase7_service_request_automation'
down_revision = '010_phase6_comment_analysis'
branch_labels = None
depends_on    = None


def upgrade():
    op.add_column(
        'comment_analysis',
        sa.Column('issue_type', sa.String(30), nullable=True),
    )
    op.add_column(
        'comment_analysis',
        sa.Column(
            'service_request_id',
            sa.String(36),
            sa.ForeignKey('service_request.id', ondelete='SET NULL'),
            nullable=True,
        ),
    )
    op.create_index('ix_comment_analysis_issue_type', 'comment_analysis', ['issue_type'])
    op.create_index('ix_comment_analysis_service_request_id', 'comment_analysis', ['service_request_id'])


def downgrade():
    op.drop_index('ix_comment_analysis_service_request_id', table_name='comment_analysis')
    op.drop_index('ix_comment_analysis_issue_type', table_name='comment_analysis')
    op.drop_column('comment_analysis', 'service_request_id')
    op.drop_column('comment_analysis', 'issue_type')
