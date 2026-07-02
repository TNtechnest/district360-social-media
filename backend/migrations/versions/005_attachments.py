"""Migration 005: Add attachment table for file uploads.

Revision ID: 005_attachments
Revises: 004_service_requests
Create Date: 2026-06-24
"""
from alembic import op
import sqlalchemy as sa

revision     = '005_attachments'
down_revision = '004_service_requests'
branch_labels = None
depends_on    = None


def upgrade():
    op.create_table(
        'attachment',
        sa.Column('id',                sa.String(36), primary_key=True),
        sa.Column('district_id',       sa.String(36),
                  sa.ForeignKey('district.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('resource_type',     sa.String(50),  nullable=False, index=True),
        sa.Column('resource_id',       sa.String(36),  nullable=False, index=True),
        sa.Column('original_filename', sa.String(500), nullable=False),
        sa.Column('stored_filename',   sa.String(500), nullable=False),
        sa.Column('storage_path',      sa.Text(),      nullable=False),
        sa.Column('mime_type',         sa.String(100), nullable=False),
        sa.Column('file_size',         sa.BigInteger(), nullable=False),
        sa.Column('file_category',     sa.String(20),  nullable=False, index=True),
        sa.Column('uploaded_by',       sa.String(36),
                  sa.ForeignKey('user.id', ondelete='SET NULL'), nullable=True),
        sa.Column('version',           sa.Integer(),   nullable=False, server_default='1'),
        sa.Column('is_deleted',        sa.Boolean(),   nullable=False, server_default='false', index=True),
        sa.Column('checksum',          sa.String(64),  nullable=True),
        sa.Column('virus_scan_status', sa.String(20),  nullable=False, server_default='pending'),
        sa.Column('created_at',        sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at',        sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_attachment_resource', 'attachment', ['resource_type', 'resource_id'])


def downgrade():
    op.drop_table('attachment')
