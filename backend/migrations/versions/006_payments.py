"""Migration 006: Add payment tables (plans, transactions).

Revision ID: 006_payments
Revises: 005_attachments
Create Date: 2026-06-24
"""
from alembic import op
import sqlalchemy as sa

revision     = '006_payments'
down_revision = '005_attachments'
branch_labels = None
depends_on    = None


def upgrade():
    # ------------------------------------------------------------------ subscription_plan
    op.create_table(
        'subscription_plan',
        sa.Column('id',               sa.String(36), primary_key=True),
        sa.Column('district_id',      sa.String(36),
                  sa.ForeignKey('district.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name',             sa.String(255), nullable=False),
        sa.Column('code',             sa.String(50),  nullable=False),
        sa.Column('description',      sa.Text(),      nullable=True),
        sa.Column('amount',           sa.Float(),     nullable=False),
        sa.Column('currency',         sa.String(10),  nullable=False, server_default='INR'),
        sa.Column('interval',         sa.String(20),  nullable=False, server_default='monthly'),
        sa.Column('is_active',        sa.Boolean(),   nullable=False, server_default='true'),
        sa.Column('features',         sa.JSON(),      nullable=False, server_default='[]'),
        sa.Column('max_users',        sa.Integer(),   nullable=True),
        sa.Column('max_storage_gb',   sa.Integer(),   nullable=True),
        sa.Column('provider_plan_id', sa.String(255), nullable=True),
        sa.Column('created_at',       sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at',       sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('district_id', 'code', name='uix_plan_district_code'),
    )

    # ------------------------------------------------------------------ payment_transaction
    op.create_table(
        'payment_transaction',
        sa.Column('id',                sa.String(36), primary_key=True),
        sa.Column('district_id',       sa.String(36),
                  sa.ForeignKey('district.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('plan_id',           sa.String(36),
                  sa.ForeignKey('subscription_plan.id', ondelete='SET NULL'), nullable=True),
        sa.Column('user_id',           sa.String(36),
                  sa.ForeignKey('user.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('provider',          sa.String(20),  nullable=False),
        sa.Column('transaction_id',    sa.String(255), nullable=False, index=True),
        sa.Column('provider_order_id', sa.String(255), nullable=True),
        sa.Column('amount',            sa.Float(),     nullable=False),
        sa.Column('currency',          sa.String(10),  nullable=False, server_default='INR'),
        sa.Column('status',            sa.String(20),  nullable=False,
                  server_default='pending', index=True),
        sa.Column('payment_method',    sa.String(50),  nullable=True),
        sa.Column('description',       sa.Text(),      nullable=True),
        sa.Column('invoice_url',       sa.Text(),      nullable=True),
        sa.Column('refund_status',     sa.String(20),  nullable=True),
        sa.Column('refund_amount',     sa.Float(),     nullable=True),
        sa.Column('refund_reason',     sa.Text(),      nullable=True),
        sa.Column('refunded_at',       sa.String(50),  nullable=True),
        sa.Column('paid_at',           sa.String(50),  nullable=True),
        sa.Column('webhook_data',      sa.JSON(),      nullable=False, server_default='{}'),
        sa.Column('error_message',     sa.Text(),      nullable=True),
        sa.Column('created_at',        sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at',        sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table('payment_transaction')
    op.drop_table('subscription_plan')
