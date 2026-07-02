"""Media library service — upload metadata, list, tag, and delete assets.

Actual binary storage is handled by the calling layer (e.g. Flask route
saves the file to object storage and passes the URL here).
"""
import logging
from app.extensions import db
from app.models.media_item import MediaItem
from app.utils.db import paginate_query

logger = logging.getLogger(__name__)


def get_media(district_id: str, page: int = 1, per_page: int = 20,
              media_type: str | None = None, folder: str | None = None,
              search: str | None = None) -> object:
    query = MediaItem.query.filter_by(district_id=district_id, is_deleted=False)
    if media_type:
        query = query.filter(MediaItem.media_type == media_type)
    if folder:
        query = query.filter(MediaItem.folder == folder)
    if search:
        like = f'%{search}%'
        query = query.filter(
            db.or_(MediaItem.filename.ilike(like), MediaItem.alt_text.ilike(like))
        )
    return paginate_query(query.order_by(MediaItem.created_at.desc()), page, per_page)


def get_media_item(district_id: str, item_id: str) -> MediaItem:
    item = MediaItem.query.filter_by(id=item_id, district_id=district_id, is_deleted=False).first()
    if not item:
        raise ValueError('Media item not found.')
    return item


def add_media_item(
    district_id: str,
    filename: str,
    url: str,
    media_type: str,
    uploaded_by: str | None = None,
    mime_type: str | None = None,
    file_size: int = 0,
    alt_text: str | None = None,
    folder: str = '/',
    tags: list | None = None,
    width: int | None = None,
    height: int | None = None,
    thumbnail_url: str | None = None,
) -> MediaItem:
    item = MediaItem(
        district_id=district_id,
        filename=filename,
        url=url,
        media_type=media_type,
        uploaded_by=uploaded_by,
        mime_type=mime_type,
        file_size=file_size,
        alt_text=alt_text,
        folder=folder,
        tags=tags or [],
        width=width,
        height=height,
        thumbnail_url=thumbnail_url,
    )
    db.session.add(item)
    db.session.commit()
    return item


def update_media_item(district_id: str, item_id: str, **fields) -> MediaItem:
    item = get_media_item(district_id, item_id)
    allowed = {'alt_text', 'folder', 'tags', 'thumbnail_url'}
    for k, v in fields.items():
        if k not in allowed:
            raise ValueError(f"Field '{k}' cannot be updated.")
        setattr(item, k, v)
    db.session.commit()
    return item


def soft_delete_media(district_id: str, item_id: str) -> None:
    item = get_media_item(district_id, item_id)
    item.is_deleted = True
    db.session.commit()
