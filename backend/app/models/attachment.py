"""Attachment model — uploaded files for service requests and general use."""

from sqlalchemy import String, Text, Integer, BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.base import TenantScopedModel


ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml'}
ALLOWED_VIDEO_TYPES = {'video/mp4', 'video/mpeg', 'video/quicktime', 'video/x-msvideo', 'video/webm'}
ALLOWED_DOC_TYPES = {
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'text/plain', 'text/csv',
}
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB


class Attachment(TenantScopedModel):
    """An uploaded file attached to a resource (service request, etc.)."""
    __tablename__ = 'attachment'

    resource_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    resource_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_category: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    uploaded_by: Mapped[str] = mapped_column(
        String(36), ForeignKey('user.id', ondelete='SET NULL'), nullable=True,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(default=False, nullable=False, index=True)
    checksum: Mapped[str] = mapped_column(String(64), nullable=True)
    virus_scan_status: Mapped[str] = mapped_column(String(20), default='pending', nullable=False)

    uploader = relationship('User', foreign_keys=[uploaded_by])

    def to_dict(self):
        return {
            'id': self.id,
            'district_id': self.district_id,
            'resource_type': self.resource_type,
            'resource_id': self.resource_id,
            'original_filename': self.original_filename,
            'stored_filename': self.stored_filename,
            'storage_path': self.storage_path,
            'mime_type': self.mime_type,
            'file_size': self.file_size,
            'file_category': self.file_category,
            'uploaded_by': self.uploaded_by,
            'version': self.version,
            'is_deleted': self.is_deleted,
            'checksum': self.checksum,
            'virus_scan_status': self.virus_scan_status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
