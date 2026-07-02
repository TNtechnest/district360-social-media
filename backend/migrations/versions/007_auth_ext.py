"""Migration 007: Add OTP, session, and OAuth connection tables.

Revision ID: 007_auth_ext
Revises: 006_payments
Create Date: 2026-06-24
"""
from alembic import op
import sqlalchemy as sa

revision     = '007_auth_ext'
down_revision = '006_payments'
branch_labels = None
depends_on    = None


def upgrade():
    # ------------------------------------------------------------------ otp_code
    op.create_table(
        'otp_code',
        sa.Column('id',          sa.String(36), primary_key=True),
        sa.Column('district_id', sa.String(36),
                  sa.ForeignKey('district.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('user_id',     sa.String(36),
                  sa.ForeignKey('user.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('email',       sa.String(255), nullable=True, index=True),
        sa.Column('phone',       sa.String(20),  nullable=True, index=True),
        sa.Column('code',        sa.String(6),   nullable=False),
        sa.Column('purpose',     sa.String(30),  nullable=False, index=True),
        sa.Column('is_used',     sa.Boolean(),   nullable=False, server_default='false'),
        sa.Column('expires_at',  sa.String(50),  nullable=False),
        sa.Column('attempts',    sa.Integer(),   nullable=False, server_default='0'),
        sa.Column('verified_at', sa.String(50),  nullable=True),
        sa.Column('sent_to',     sa.String(255), nullable=True),
        sa.Column('created_at',  sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at',  sa.DateTime(timezone=True), nullable=False),
    )

    # ------------------------------------------------------------------ user_session
    op.create_table(
        'user_session',
        sa.Column('id',              sa.String(36), primary_key=True),
        sa.Column('district_id',     sa.String(36),
                  sa.ForeignKey('district.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('user_id',         sa.String(36),
                  sa.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('token_jti',       sa.String(255), nullable=False, index=True),
        sa.Column('device_name',     sa.String(255), nullable=True),
        sa.Column('device_type',     sa.String(50),  nullable=True),
        sa.Column('browser',         sa.String(255), nullable=True),
        sa.Column('os_info',         sa.String(255), nullable=True),
        sa.Column('ip_address',      sa.String(45),  nullable=True),
        sa.Column('location',        sa.String(255), nullable=True),
        sa.Column('is_active',       sa.Boolean(),   nullable=False, server_default='true'),
        sa.Column('last_activity_at', sa.String(50), nullable=True),
        sa.Column('logged_out_at',   sa.String(50),  nullable=True),
        sa.Column('created_at',      sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at',      sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_user_session_user_active', 'user_session', ['user_id', 'is_active'])

    # ------------------------------------------------------------------ oauth_connection
    op.create_table(
        'oauth_connection',
        sa.Column('id',               sa.String(36), primary_key=True),
        sa.Column('district_id',      sa.String(36),
                  sa.ForeignKey('district.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('user_id',          sa.String(36),
                  sa.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('provider',         sa.String(30),  nullable=False),
        sa.Column('provider_user_id', sa.String(255), nullable=False),
        sa.Column('provider_email',   sa.String(255), nullable=True),
        sa.Column('access_token',     sa.Text(),      nullable=True),
        sa.Column('refresh_token',    sa.Text(),      nullable=True),
        sa.Column('token_expires_at', sa.String(50),  nullable=True),
        sa.Column('raw_profile',      sa.JSON(),      nullable=False, server_default='{}'),
        sa.Column('created_at',       sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at',       sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('user_id', 'provider', name='uix_oauth_user_provider'),
        sa.UniqueConstraint('provider', 'provider_user_id', name='uix_oauth_provider_user'),
    )


def downgrade():
    op.drop_table('oauth_connection')
    op.drop_table('user_session')
    op.drop_table('otp_code')
