"""Migration 004: Add service request tables.

Revision ID: 004_service_requests
Revises: 003_phase3
Create Date: 2026-06-24
"""
from alembic import op
import sqlalchemy as sa

revision     = '004_service_requests'
down_revision = '003_phase3'
branch_labels = None
depends_on    = None


def upgrade():
    # ------------------------------------------------------------------ service_request_category
    op.create_table(
        'service_request_category',
        sa.Column('id',               sa.String(36), primary_key=True),
        sa.Column('district_id',      sa.String(36),
                  sa.ForeignKey('district.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name',             sa.String(255), nullable=False),
        sa.Column('code',             sa.String(50),  nullable=False),
        sa.Column('description',      sa.Text(),      nullable=True),
        sa.Column('parent_id',        sa.String(36),
                  sa.ForeignKey('service_request_category.id', ondelete='SET NULL'), nullable=True),
        sa.Column('department_id',    sa.String(36),
                  sa.ForeignKey('department.id', ondelete='SET NULL'), nullable=True),
        sa.Column('default_priority', sa.String(20),  nullable=False, server_default='medium'),
        sa.Column('sla_hours',        sa.Integer(),   nullable=False, server_default='48'),
        sa.Column('is_active',        sa.Boolean(),   nullable=False, server_default='true'),
        sa.Column('created_at',       sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at',       sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('district_id', 'code', name='uix_sr_category_district_code'),
    )

    # ------------------------------------------------------------------ service_request
    op.create_table(
        'service_request',
        sa.Column('id',                sa.String(36), primary_key=True),
        sa.Column('district_id',       sa.String(36),
                  sa.ForeignKey('district.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('category_id',       sa.String(36),
                  sa.ForeignKey('service_request_category.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('department_id',     sa.String(36),
                  sa.ForeignKey('department.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('citizen_id',        sa.String(36),
                  sa.ForeignKey('user.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('assigned_to',       sa.String(36),
                  sa.ForeignKey('user.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('title',             sa.String(500), nullable=False),
        sa.Column('description',       sa.Text(),      nullable=False),
        sa.Column('status',            sa.String(20),  nullable=False,
                  server_default='submitted', index=True),
        sa.Column('priority',          sa.String(20),  nullable=False,
                  server_default='medium', index=True),
        sa.Column('location',          sa.Text(),      nullable=True),
        sa.Column('ward',              sa.String(100), nullable=True),
        sa.Column('landmark',          sa.String(255), nullable=True),
        sa.Column('citizen_phone',     sa.String(20),  nullable=True),
        sa.Column('citizen_email',     sa.String(255), nullable=True),
        sa.Column('acknowledged_at',   sa.String(50),  nullable=True),
        sa.Column('resolved_at',       sa.String(50),  nullable=True),
        sa.Column('closed_at',         sa.String(50),  nullable=True),
        sa.Column('sla_deadline',      sa.String(50),  nullable=True),
        sa.Column('resolution_notes',  sa.Text(),      nullable=True),
        sa.Column('citizen_feedback',  sa.Text(),      nullable=True),
        sa.Column('satisfaction_score', sa.Integer(),  nullable=True),
        sa.Column('is_escalated',      sa.Boolean(),   nullable=False, server_default='false'),
        sa.Column('escalation_reason', sa.Text(),      nullable=True),
        sa.Column('tags',              sa.JSON(),      nullable=False, server_default='[]'),
        sa.Column('created_at',        sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at',        sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_sr_assigned_to', 'service_request', ['assigned_to'])
    op.create_index('ix_sr_citizen_id', 'service_request', ['citizen_id'])

    # ------------------------------------------------------------------ service_request_comment
    op.create_table(
        'service_request_comment',
        sa.Column('id',          sa.String(36), primary_key=True),
        sa.Column('district_id', sa.String(36),
                  sa.ForeignKey('district.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('request_id',  sa.String(36),
                  sa.ForeignKey('service_request.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('author_id',   sa.String(36),
                  sa.ForeignKey('user.id', ondelete='SET NULL'), nullable=True),
        sa.Column('comment',     sa.Text(),      nullable=False),
        sa.Column('is_internal', sa.Boolean(),   nullable=False, server_default='false'),
        sa.Column('old_status',  sa.String(20),  nullable=True),
        sa.Column('new_status',  sa.String(20),  nullable=True),
        sa.Column('created_at',  sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table('service_request_comment')
    op.drop_table('service_request')
    op.drop_table('service_request_category')
