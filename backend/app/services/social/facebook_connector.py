"""Facebook / Meta Graph API connector.

Uses the Meta Graph API v19.0.
Required credentials keys:
  - ``page_access_token``: Page-level access token (long-lived preferred).
  - ``page_id``:           Facebook Page ID.

API docs: https://developers.facebook.com/docs/graph-api
"""
import logging
import requests

from app.services.social.base_connector import BaseSocialConnector, PublishResult, CollectedItem

logger = logging.getLogger(__name__)

GRAPH_API_BASE = 'https://graph.facebook.com/v19.0'
DEFAULT_COLLECT_FIELDS = 'id,message,created_time,from,likes.summary(true),comments.summary(true),shares'


class FacebookConnector(BaseSocialConnector):
    """Facebook Page connector via Meta Graph API."""

    platform_name = 'facebook'

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    def publish_post(self, content: str, media_urls: list[str] | None = None,
                     meta: dict | None = None) -> PublishResult:
        """Publish a text (+ optional photo) post to the Facebook Page.

        For video posts, use the resumable upload endpoint (not implemented
        in this baseline; extend as needed).
        """
        page_id    = self.credentials.get('page_id') or self.config.get('page_id')
        page_token = self.credentials.get('page_access_token') or self.credentials.get('access_token')

        if not page_id or not page_token:
            return PublishResult(success=False, error_message='page_id and page_access_token are required.')

        try:
            if media_urls:
                # Photo post — use the /photos endpoint with the first image
                url = f'{GRAPH_API_BASE}/{page_id}/photos'
                payload = {
                    'caption': content,
                    'url': media_urls[0],
                    'access_token': page_token,
                }
            else:
                url = f'{GRAPH_API_BASE}/{page_id}/feed'
                payload = {
                    'message': content,
                    'access_token': page_token,
                }

            if meta:
                payload.update(meta)

            resp = requests.post(url, data=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            return PublishResult(
                success=True,
                platform_post_id=data.get('id') or data.get('post_id'),
                raw_response=data,
            )
        except requests.RequestException as exc:
            self._log_error('publish_post', exc)
            return PublishResult(success=False, error_message=str(exc))

    # ------------------------------------------------------------------
    # Collection
    # ------------------------------------------------------------------

    def collect_recent(self, since_id: str | None = None, limit: int = 50) -> list[CollectedItem]:
        """Collect recent posts from the Facebook Page feed."""
        page_id    = self.credentials.get('page_id') or self.config.get('page_id')
        page_token = self.credentials.get('page_access_token') or self.credentials.get('access_token')

        if not page_id or not page_token:
            logger.error('Facebook: missing page_id or page_access_token')
            return []

        try:
            params = {
                'fields': DEFAULT_COLLECT_FIELDS,
                'limit': min(limit, 100),
                'access_token': page_token,
            }
            if since_id:
                params['after'] = since_id

            resp = requests.get(f'{GRAPH_API_BASE}/{page_id}/feed', params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            items = []
            for post in data.get('data', []):
                item = CollectedItem(
                    platform_content_id=post.get('id', ''),
                    content_type='post',
                    raw_text=post.get('message', ''),
                    author_platform_id=post.get('from', {}).get('id'),
                    author_username=post.get('from', {}).get('name'),
                    platform_created_at=post.get('created_time'),
                    likes=post.get('likes', {}).get('summary', {}).get('total_count', 0),
                    comments=post.get('comments', {}).get('summary', {}).get('total_count', 0),
                    shares=post.get('shares', {}).get('count', 0) if post.get('shares') else 0,
                    extra=post,
                )
                items.append(item)
            return items

        except requests.RequestException as exc:
            self._log_error('collect_recent', exc)
            return []

    def collect_comments(self, post_id: str, limit: int = 100) -> list[CollectedItem]:
        """Collect comments on a specific post."""
        page_token = self.credentials.get('page_access_token') or self.credentials.get('access_token')
        try:
            params = {
                'fields': 'id,message,created_time,from,like_count,comment_count,parent',
                'limit': min(limit, 100),
                'access_token': page_token,
                'filter': 'stream',   # include all comments (not just top-level)
            }
            resp = requests.get(f'{GRAPH_API_BASE}/{post_id}/comments', params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            return [
                CollectedItem(
                    platform_content_id=c.get('id', ''),
                    content_type='comment',
                    raw_text=c.get('message', ''),
                    author_platform_id=c.get('from', {}).get('id'),
                    author_username=c.get('from', {}).get('name'),
                    platform_created_at=c.get('created_time'),
                    likes=c.get('like_count', 0),
                    extra={
                        **c,
                        '_parent_id': c.get('parent', {}).get('id'),
                        '_reply_count': c.get('comment_count', 0),
                    },
                )
                for c in data.get('data', [])
            ]
        except requests.RequestException as exc:
            self._log_error('collect_comments', exc)
            return []

    def sync_post_comments(
        self,
        post_id: str,
        platform_post_id: str,
        district_id: str,
        limit: int = 100,
    ) -> int:
        """Collect and persist comments for a published post via comment_service.

        Args:
            post_id:          Internal SocialPost UUID.
            platform_post_id: Facebook post ID (e.g. page_id_post_id).
            district_id:      Tenant scope.
            limit:            Max comments to fetch.

        Returns:
            Number of new comments stored.
        """
        from app.services.social.comment_service import upsert_comment

        items = self.collect_comments(platform_post_id, limit=limit)
        new_count = 0

        for item in items:
            if not item.raw_text.strip():
                continue
            parent_platform_id = item.extra.get('_parent_id')
            parent_db_id       = None

            if parent_platform_id:
                from app.models.social_comment import SocialComment
                parent = SocialComment.query.filter_by(
                    post_id=post_id,
                    platform_comment_id=parent_platform_id,
                ).first()
                if parent:
                    parent_db_id = parent.id

            _, created = upsert_comment(
                district_id=district_id,
                post_id=post_id,
                platform='facebook',
                platform_comment_id=item.platform_content_id,
                text=item.raw_text,
                parent_comment_id=parent_db_id,
                author_platform_id=item.author_platform_id,
                author_name=item.author_username,
                author_username=item.author_username,
                platform_created_at=item.platform_created_at,
                likes=item.likes,
                reply_count=item.extra.get('_reply_count', 0),
                run_ai=False,   # batch AI is run separately
            )
            if created:
                new_count += 1

        logger.info('Facebook sync: %d new comments for post %s', new_count, post_id)
        return new_count

    # ------------------------------------------------------------------
    # Account info
    # ------------------------------------------------------------------

    def get_account_info(self) -> dict:
        page_id    = self.credentials.get('page_id') or self.config.get('page_id')
        page_token = self.credentials.get('page_access_token') or self.credentials.get('access_token')
        try:
            resp = requests.get(
                f'{GRAPH_API_BASE}/{page_id}',
                params={'fields': 'id,name,category,followers_count', 'access_token': page_token},
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            self._log_error('get_account_info', exc)
            return {}
