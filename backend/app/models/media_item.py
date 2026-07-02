"""MediaItem model — files in the district's media library.

Tracks images, videos, and documents that can be attached to social posts.
File binaries are stored in object storage; this table stores metadata only.
"""
from sqlalchemy import String, Text, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.base import TenantScopedModel


class MediaItem(TenantScopedModel):
    """A media asset in the district media library."""
    __tablename__ = 'media_item'

    # FK to social post (nullable — media can exist without being attached to a post)
    post_id: Mapped[str] = mapped_column(
        String(36), db.ForeignKey('social_post.id', ondelete='SET NULL'),
        nullable=True, index=True,
    )

    # User who uploaded the asset
    uploaded_by: Mapped[str] = mapped_column(
        String(36), db.ForeignKey('user.id', ondelete='SET NULL'),
        nullable=True,
    )

    # image | video | document | audio
    media_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # Original filename
    filename: Mapped[str] = mapped_column(String(255), nullable=False)

    # MIME type (image/jpeg, video/mp4, etc.)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=True)

    # File size in bytes
    file_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Object storage URL / key
    url: Mapped[str] = mapped_column(Text, nullable=False)

    # CDN / thumbnail URL (generated async)
    thumbnail_url: Mapped[str] = mapped_column(Text, nullable=True)

    # Width × height for images/videos
    width: Mapped[int] = mapped_column(Integer, nullable=True)
    height: Mapped[int] = mapped_column(Integer, nullable=True)

    # Duration in seconds for video/audio
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=True)

    # Alt text / caption for accessibility
    alt_text: Mapped[str] = mapped_column(String(500), nullable=True)

    # Folder / tag for library organisation
    folder: Mapped[str] = mapped_column(String(255), default='/', nullable=False, index=True)
    tags: Mapped[list] = mapped_column(db.JSON, default=list, nullable=False)

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    post = relationship('SocialPost', back_populates='media_items')

    def to_dict(self):
        return {
            'id': self.id,
            'district_id': self.district_id,
            'post_id': self.post_id,
            'uploaded_by': self.uploaded_by,
            'media_type': self.media_type,
            'filename': self.filename,
            'mime_type': self.mime_type,
            'file_size': self.file_size,
            'url': self.url,
            'thumbnail_url': self.thumbnail_url,
            'width': self.width,
            'height': self.height,
            'duration_seconds': self.duration_seconds,
            'alt_text': self.alt_text,
            'folder': self.folder,
            'tags': self.tags,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
