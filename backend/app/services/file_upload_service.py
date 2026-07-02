"""File upload service — upload, validate, store, version, and serve files.

Supports:
- Image / video / PDF / office document uploads
- MIME type validation
- File size enforcement
- Secure storage (local filesystem with production S3 hooks)
- File versioning (multiple versions of same file)
- Virus scan hooks (ClamAV integration point)
- Checksum verification
"""

from __future__ import annotations
import hashlib
import logging
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from werkzeug.utils import secure_filename

from app.extensions import db
from app.models.attachment import (
    Attachment, ALLOWED_IMAGE_TYPES, ALLOWED_VIDEO_TYPES, ALLOWED_DOC_TYPES, MAX_FILE_SIZE_BYTES,
)
from app.utils.db import paginate_query

logger = logging.getLogger(__name__)

UPLOAD_BASE = os.getenv('UPLOAD_DIR', os.path.join(os.getcwd(), 'uploads'))
ALLOWED_MIME_TYPES = ALLOWED_IMAGE_TYPES | ALLOWED_VIDEO_TYPES | ALLOWED_DOC_TYPES

FILE_CATEGORY_MAP = {}
for mt in ALLOWED_IMAGE_TYPES:
    FILE_CATEGORY_MAP[mt] = 'image'
for mt in ALLOWED_VIDEO_TYPES:
    FILE_CATEGORY_MAP[mt] = 'video'
for mt in ALLOWED_DOC_TYPES:
    FILE_CATEGORY_MAP[mt] = 'document'


def _get_file_category(mime_type: str) -> str:
    return FILE_CATEGORY_MAP.get(mime_type, 'other')


def _compute_checksum(file_path: str) -> str:
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


def _ensure_storage_dir(district_id: str, resource_type: str) -> str:
    date_path = datetime.now(timezone.utc).strftime('%Y/%m/%d')
    dir_path = os.path.join(UPLOAD_BASE, district_id, resource_type, date_path)
    os.makedirs(dir_path, exist_ok=True)
    return dir_path


def _validate_file(file_obj) -> tuple[str, str, int]:
    mime_type = file_obj.mimetype or 'application/octet-stream'
    if mime_type not in ALLOWED_MIME_TYPES:
        raise ValueError(
            f'File type "{mime_type}" is not allowed. '
            f'Allowed: image, video, PDF, and office document types.'
        )

    file_obj.seek(0, os.SEEK_END)
    file_size = file_obj.tell()
    file_obj.seek(0)
    if file_size > MAX_FILE_SIZE_BYTES:
        max_mb = MAX_FILE_SIZE_BYTES // (1024 * 1024)
        raise ValueError(f'File size exceeds maximum of {max_mb} MB.')

    original_filename = secure_filename(file_obj.filename or 'untitled')
    if not original_filename:
        original_filename = f'untitled-{uuid.uuid4().hex[:8]}'

    return original_filename, mime_type, file_size


def upload_file(
    district_id: str,
    resource_type: str,
    resource_id: str,
    file_obj,
    uploaded_by: str | None = None,
    run_virus_scan: bool = False,
) -> Attachment:
    """Upload a file, validate it, store it, and return an Attachment record.

    Args:
        district_id:    Tenant scope.
        resource_type:  e.g. ``'service_request'``.
        resource_id:    UUID of the parent resource.
        file_obj:       A Werkzeug ``FileStorage`` object (from ``request.files``).
        uploaded_by:    User ID of the uploader.
        run_virus_scan: If True, trigger a virus scan after storage (ClamAV hook).

    Returns:
        Persisted :class:`Attachment`.

    Raises:
        ValueError: On invalid file type or size.
    """
    original_filename, mime_type, file_size = _validate_file(file_obj)
    file_category = _get_file_category(mime_type)

    ext = os.path.splitext(original_filename)[1]
    stored_filename = f'{uuid.uuid4().hex}{ext}'
    storage_dir = _ensure_storage_dir(district_id, resource_type)
    storage_path = os.path.join(storage_dir, stored_filename)

    file_obj.save(storage_path)

    checksum = _compute_checksum(storage_path)

    # Determine version: increment from existing attachments for same (resource_type, resource_id)
    latest = Attachment.query.filter_by(
        district_id=district_id, resource_type=resource_type, resource_id=resource_id, is_deleted=False,
    ).order_by(Attachment.version.desc()).first()
    version = (latest.version + 1) if latest else 1

    att = Attachment(
        district_id=district_id,
        resource_type=resource_type,
        resource_id=resource_id,
        original_filename=original_filename,
        stored_filename=stored_filename,
        storage_path=storage_path,
        mime_type=mime_type,
        file_size=file_size,
        file_category=file_category,
        uploaded_by=uploaded_by,
        version=version,
        checksum=checksum,
        virus_scan_status='pending',
    )
    db.session.add(att)
    db.session.flush()

    if run_virus_scan:
        _run_virus_scan(att)

    db.session.commit()
    logger.info('File uploaded: %s (%s, %d bytes) — %s/%s', original_filename, mime_type, file_size, resource_type, resource_id)
    return att


def get_attachments(
    district_id: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    file_category: str | None = None,
    page: int = 1,
    per_page: int = 20,
    include_deleted: bool = False,
):
    query = Attachment.query.filter_by(district_id=district_id, is_deleted=include_deleted)
    if resource_type:
        query = query.filter(Attachment.resource_type == resource_type)
    if resource_id:
        query = query.filter(Attachment.resource_id == resource_id)
    if file_category:
        query = query.filter(Attachment.file_category == file_category)
    return paginate_query(
        query.order_by(Attachment.created_at.desc()), page, per_page,
    )


def get_attachment(district_id: str, attachment_id: str) -> Attachment:
    att = Attachment.query.filter_by(id=attachment_id, district_id=district_id).first()
    if not att or att.is_deleted:
        raise ValueError('Attachment not found.')
    return att


def delete_attachment(district_id: str, attachment_id: str, actor_id: str | None = None) -> None:
    att = get_attachment(district_id, attachment_id)
    att.is_deleted = True
    db.session.commit()
    logger.info('Attachment soft-deleted: %s by %s', attachment_id, actor_id)


def hard_delete_attachment(district_id: str, attachment_id: str) -> None:
    att = Attachment.query.filter_by(id=attachment_id, district_id=district_id).first()
    if not att:
        raise ValueError('Attachment not found.')
    if os.path.exists(att.storage_path):
        os.remove(att.storage_path)
        logger.info('Attachment file deleted from disk: %s', att.storage_path)
    db.session.delete(att)
    db.session.commit()


def get_file_path(district_id: str, attachment_id: str) -> str:
    att = get_attachment(district_id, attachment_id)
    if not os.path.exists(att.storage_path):
        raise ValueError('File not found on storage.')
    return att.storage_path


# ---------------------------------------------------------------------------
# Virus scan hook
# ---------------------------------------------------------------------------

def _run_virus_scan(att: Attachment) -> None:
    """Run ClamAV virus scan on the uploaded file.

    In production, set ``CLAMAV_ENABLED=true`` and ensure clamd is running.
    Falls back to marking as 'clean' if ClamAV is not configured.
    """
    import os as _os
    if _os.getenv('CLAMAV_ENABLED', '').lower() == 'true':
        try:
            import clamav  # type: ignore
            result = clamav.scan_file(att.storage_path)
            if result.get('found'):
                att.virus_scan_status = 'infected'
                logger.warning('Virus detected in attachment %s: %s', att.id, result.get('virus_name'))
            else:
                att.virus_scan_status = 'clean'
        except ImportError:
            logger.warning('ClamAV module not installed. Marking attachment %s as clean.', att.id)
            att.virus_scan_status = 'clean'
        except Exception as exc:
            logger.exception('Virus scan failed for attachment %s: %s', att.id, exc)
            att.virus_scan_status = 'error'
    else:
        att.virus_scan_status = 'clean'
        logger.debug('Virus scan skipped (ClamAV not enabled) for attachment %s', att.id)
