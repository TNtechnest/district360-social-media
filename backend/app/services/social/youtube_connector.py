"""YouTube Data API v3 connector.

Required credentials:
  - ``api_key``:       YouTube Data API v3 key (for read-only public data).
  - ``access_token``:  OAuth 2.0 token for write operations (video upload,
                       community posts, comment replies).
  - ``channel_id``:    YouTube Channel ID.

Publishing note:
  Video upload uses the resumable upload protocol and is intentionally
  left as a stub (requires multipart streaming) — community post publishing
  via the ``activities`` endpoint is used for text-based updates.

API docs: https://developers.google.com/youtube/v3
"""
import logging
import requests

from app.services.social.base_connector import BaseSocialConnector, PublishResult, CollectedItem

logger = logging.getLogger(__name__)
YT_API_BASE = 'https://www.googleapis.com/youtube/v3'


class YouTubeConnector(BaseSocialConnector):
    """YouTube channel connector via Data API v3."""

    platform_name = 'youtube'

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    def publish_post(self, content: str, media_urls: list[str] | None = None,
                     meta: dict | None = None) -> PublishResult:
        """Post a Community post (text update) to the YouTube channel.

        Video uploads require resumable streaming — not in this baseline.
        Set ``meta={'video_title': ..., 'video_description': ...}`` to
        trigger a (stub) video upload flow.
        """
        access_token = self.credentials.get('access_token')
        channel_id   = self.credentials.get('channel_id') or self.config.get('channel_id')

        if not access_token:
            return PublishResult(success=False, error_message='access_token is required for publishing.')

        try:
            # Community post via activities.insert
            body = {
                'snippet': {
                    'description': content,
                },
                'contentDetails': {
                    'bulletin': {'resourceId': {}},
                },
            }
            resp = requests.post(
                f'{YT_API_BASE}/activities',
                params={'part': 'snippet,contentDetails'},
                headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'},
                json=body,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return PublishResult(success=True, platform_post_id=data.get('id'), raw_response=data)

        except requests.RequestException as exc:
            self._log_error('publish_post', exc)
            return PublishResult(success=False, error_message=str(exc))

    # ------------------------------------------------------------------
    # Collection
    # ------------------------------------------------------------------

    def collect_recent(self, since_id: str | None = None, limit: int = 50) -> list[CollectedItem]:
        """Collect recent public videos from the channel."""
        api_key    = self.credentials.get('api_key')
        channel_id = self.credentials.get('channel_id') or self.config.get('channel_id')

        if not api_key or not channel_id:
            logger.error('YouTube: api_key and channel_id required')
            return []

        try:
            params = {
                'part': 'snippet',
                'channelId': channel_id,
                'maxResults': min(limit, 50),
                'order': 'date',
                'type': 'video',
                'key': api_key,
            }
            if since_id:
                params['pageToken'] = since_id

            resp = requests.get(f'{YT_API_BASE}/search', params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            return [
                CollectedItem(
                    platform_content_id=item['id'].get('videoId', ''),
                    content_type='post',
                    raw_text=item['snippet'].get('title', '') + ' ' + item['snippet'].get('description', ''),
                    author_username=item['snippet'].get('channelTitle'),
                    platform_created_at=item['snippet'].get('publishedAt'),
                    extra=item,
                )
                for item in data.get('items', [])
            ]
        except requests.RequestException as exc:
            self._log_error('collect_recent', exc)
            return []

    def collect_comments(self, video_id: str, limit: int = 100) -> list[CollectedItem]:
        """Collect top-level comments on a video."""
        api_key = self.credentials.get('api_key')
        try:
            params = {
                'part': 'snippet',
                'videoId': video_id,
                'maxResults': min(limit, 100),
                'key': api_key,
            }
            resp = requests.get(f'{YT_API_BASE}/commentThreads', params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            items = []
            for thread in data.get('items', []):
                snippet = thread.get('snippet', {}).get('topLevelComment', {}).get('snippet', {})
                items.append(CollectedItem(
                    platform_content_id=thread.get('id', ''),
                    content_type='comment',
                    raw_text=snippet.get('textDisplay', ''),
                    author_username=snippet.get('authorDisplayName'),
                    platform_created_at=snippet.get('publishedAt'),
                    likes=snippet.get('likeCount', 0),
                    extra=thread,
                ))
            return items
        except requests.RequestException as exc:
            self._log_error('collect_comments', exc)
            return []

    def get_account_info(self) -> dict:
        api_key    = self.credentials.get('api_key')
        channel_id = self.credentials.get('channel_id') or self.config.get('channel_id')
        try:
            resp = requests.get(
                f'{YT_API_BASE}/channels',
                params={'part': 'snippet,statistics', 'id': channel_id, 'key': api_key},
                timeout=10,
            )
            resp.raise_for_status()
            items = resp.json().get('items', [])
            return items[0] if items else {}
        except requests.RequestException as exc:
            self._log_error('get_account_info', exc)
            return {}
