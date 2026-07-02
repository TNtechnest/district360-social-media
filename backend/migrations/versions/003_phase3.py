"""Migration 003: Add Phase 3 tables — notifications, workflow, reports.

Revision ID: 003_phase3
Revises: 002_social_ai
Create Date: 2026-06-23
"""
from alembic import op
import sqlalchemy as sa

revision     = '003_phase3'
down_revision = '002_social_ai'
branch_labels = None
depends_on    = None


def upgrade():
    # ------------------------------------------------------------------ notification_template
    op.create_table(
        'notification_template',
        sa.Column('id',          sa.String(36), primary_key=True),
        sa.Column('district_id', sa.String(36),
                  sa.ForeignKey('district.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('event_key',   sa.String(100), nullable=False, index=True),
        sa.Column('channel',     sa.String(20),  nullable=False, index=True),
        sa.Column('subject',     sa.String(255), nullable=True),
        sa.Column('body',        sa.Text(),      nullable=False),
        sa.Column('is_active',   sa.Boolean(),   nullable=False, server_default='true'),
        sa.Column('created_at',  sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at',  sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('district_id', 'event_key', 'channel',
                            name='uix_notif_template_district_event_channel'),
    )

    # ------------------------------------------------------------------ notification
    op.create_table(
        'notification',
        sa.Column('id',                  sa.String(36), primary_key=True),
        sa.Column('district_id',         sa.String(36),
                  sa.ForeignKey('district.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('user_id',             sa.String(36),
                  sa.ForeignKey('user.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('template_id',         sa.String(36),
                  sa.ForeignKey('notification_template.id', ondelete='SET NULL'), nullable=True),
        sa.Column('channel',             sa.String(20),  nullable=False, index=True),
        sa.Column('recipient',           sa.String(255), nullable=False),
        sa.Column('subject',             sa.String(255), nullable=True),
        sa.Column('body',                sa.Text(),      nullable=False),
        sa.Column('status',              sa.String(20),  nullable=False,
                  server_default='pending', index=True),
        sa.Column('event_key',           sa.String(100), nullable=True),
        sa.Column('provider_message_id', sa.String(255), nullable=True),
        sa.Column('error_message',       sa.Text(),      nullable=True),
        sa.Column('sent_at',             sa.String(50),  nullable=True),
        sa.Column('payload',             sa.JSON(),      nullable=False, server_default='{}'),
        sa.Column('created_at',          sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at',          sa.DateTime(timezone=True), nullable=False),
    )

    # ------------------------------------------------------------------ workflow_rule
    op.create_table(
        'workflow_rule',
        sa.Column('id',                        sa.String(36), primary_key=True),
        sa.Column('district_id',               sa.String(36),
                  sa.ForeignKey('district.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('resource_type',             sa.String(50),  nullable=False, index=True),
        sa.Column('name',                      sa.String(255), nullable=False),
        sa.Column('description',               sa.Text(),      nullable=True),
        sa.Column('rule_type',                 sa.String(30),  nullable=False, index=True),
        sa.Column('conditions',                sa.JSON(),      nullable=False, server_default='{}'),
        sa.Column('actions',                   sa.JSON(),      nullable=False, server_default='{}'),
        sa.Column('sla_minutes',               sa.Integer(),   nullable=True),
        sa.Column('escalation_after_minutes',  sa.Integer(),   nullable=True),
        sa.Column('priority',                  sa.Integer(),   nullable=False, server_default='10'),
        sa.Column('is_active',                 sa.Boolean(),   nullable=False, server_default='true'),
        sa.Column('created_at',                sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at',                sa.DateTime(timezone=True), nullable=False),
    )

    # ------------------------------------------------------------------ approval_request
    op.create_table(
        'approval_request',
        sa.Column('id',               sa.String(36), primary_key=True),
        sa.Column('district_id',      sa.String(36),
                  sa.ForeignKey('district.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('submitter_id',     sa.String(36),
                  sa.ForeignKey('user.id', ondelete='SET NULL'), nullable=True),
        sa.Column('approver_id',      sa.String(36),
                  sa.ForeignKey('user.id', ondelete='SET NULL'), nullable=True),
        sa.Column('resource_type',    sa.String(50),  nullable=False, index=True),
        sa.Column('resource_id',      sa.String(36),  nullable=False, index=True),
        sa.Column('status',           sa.String(20),  nullable=False,
                  server_default='pending', index=True),
        sa.Column('notes',            sa.Text(),      nullable=True),
        sa.Column('approver_comment', sa.Text(),      nullable=True),
        sa.Column('submitted_at',     sa.String(50),  nullable=True),
        sa.Column('reviewed_at',      sa.String(50),  nullable=True),
        sa.Column('sla_due_at',       sa.String(50),  nullable=True, index=True),
        sa.Column('workflow_rule_id', sa.String(36),
                  sa.ForeignKey('workflow_rule.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at',       sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at',       sa.DateTime(timezone=True), nullable=False),
    )

    # ------------------------------------------------------------------ escalation_log
    op.create_table(
        'escalation_log',
        sa.Column('id',               sa.String(36), primary_key=True),
        sa.Column('district_id',      sa.String(36),
                  sa.ForeignKey('district.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('resource_type',    sa.String(50),  nullable=False),
        sa.Column('resource_id',      sa.String(36),  nullable=False, index=True),
        sa.Column('rule_id',          sa.String(36),
                  sa.ForeignKey('workflow_rule.id', ondelete='SET NULL'), nullable=True),
        sa.Column('escalated_to_id',  sa.String(36),
                  sa.ForeignKey('user.id', ondelete='SET NULL'), nullable=True),
        sa.Column('reason',           sa.Text(),      nullable=True),
        sa.Column('escalated_at',     sa.String(50),  nullable=True),
        sa.Column('created_at',       sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at',       sa.DateTime(timezone=True), nullable=False),
    )

    # ------------------------------------------------------------------ report
    op.create_table(
        'report',
        sa.Column('id',             sa.String(36), primary_key=True),
        sa.Column('district_id',    sa.String(36),
                  sa.ForeignKey('district.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('report_type',    sa.String(30),  nullable=False, index=True),
        sa.Column('title',          sa.String(255), nullable=False),
        sa.Column('period_start',   sa.String(30),  nullable=False),
        sa.Column('period_end',     sa.String(30),  nullable=False),
        sa.Column('status',         sa.String(20),  nullable=False,
                  server_default='pending', index=True),
        sa.Column('data',           sa.JSON(),      nullable=False, server_default='{}'),
        sa.Column('pdf_url',        sa.Text(),      nullable=True),
        sa.Column('excel_url',      sa.Text(),      nullable=True),
        sa.Column('generated_by',   sa.String(36),
                  sa.ForeignKey('user.id', ondelete='SET NULL'), nullable=True),
        sa.Column('generated_at',   sa.String(50),  nullable=True),
        sa.Column('error_message',  sa.Text(),      nullable=True),
        sa.Column('created_at',     sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at',     sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table('report')
    op.drop_table('escalation_log')
    op.drop_table('approval_request')
    op.drop_table('workflow_rule')
    op.drop_table('notification')
    op.drop_table('notification_template')
