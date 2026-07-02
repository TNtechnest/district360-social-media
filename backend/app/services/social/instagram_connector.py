"""Instagram connector via Meta Graph API (Instagram Basic Display + Content Publishing).

Required credentials:
  - ``instagram_account_id``: Instagram Business / Creator account ID.
  - ``page_access_token``:    Facebook Page access token linked to the IG account.

Publishing flow (two-step):
  1. POST /media    — creates a media container (image/video/carousel).
  2. POST /media_publish — publishes the container.

API docs: https://developers.facebook.com/docs/instagram-api
"""
import logging
import requests

from app.services.social.base_connector import BaseSocialConnector, PublishResult, CollectedItem

logger = logging.getLogger(__name__)
GRAPH_BASE = 'https://graph.facebook.com/v19.0'


class InstagramConnector(BaseSocialConnector):
    """Instagram Business account connector."""

    platform_name = 'instagram'

    # ------------------------------------------------------------------
    # Publishing (Content Publishing API)
    # ------------------------------------------------------------------

    def publish_post(self, content: str, media_urls: list[str] | None = None,
                     meta: dict | None = None) -> PublishResult:
        """Publish an image post to Instagram.

        Args:
            content:    Caption text.
            media_urls: List of public image/video URLs.
                        - 1 URL  → single image post
                        - 2-10 URLs → carousel
            meta:       Optional extra fields (location_id, user_tags, etc.)
        """
        ig_id  = self.credentials.get('instagram_account_id') or self.credentials.get('instagram_id') or self.config.get('instagram_account_id')
        token  = self.credentials.get('page_access_token') or self.credentials.get('access_token')

        if not ig_id or not token:
            return PublishResult(success=False, error_message='instagram_account_id and page_access_token required.')

        meta = meta or {}
        try:
            if not media_urls:
                return PublishResult(success=False, error_message='Instagram requires at least one image URL.')

            if len(media_urls) == 1:
                container_id = self._create_image_container(ig_id, token, media_urls[0], content, meta)
            else:
                container_id = self._create_carousel_container(ig_id, token, media_urls, content, meta)

            if not container_id:
                return PublishResult(success=False, error_message='Failed to create media container.')

            # Step 2 — publish
            pub_resp = requests.post(
                f'{GRAPH_BASE}/{ig_id}/media_publish',
                data={'creation_id': container_id, 'access_token': token},
                timeout=15,
            )
            pub_resp.raise_for_status()
            pub_data = pub_resp.json()
            return PublishResult(success=True, platform_post_id=pub_data.get('id'), raw_response=pub_data)

        except requests.RequestException as exc:
            self._log_error('publish_post', exc)
            return PublishResult(success=False, error_message=str(exc))

    def _create_image_container(self, ig_id, token, image_url, caption, meta) -> str | None:
        payload = {'image_url': image_url, 'caption': caption, 'access_token': token}
        payload.update(meta)
        resp = requests.post(f'{GRAPH_BASE}/{ig_id}/media', data=payload, timeout=15)
        resp.raise_for_status()
        return resp.json().get('id')

    def _create_carousel_container(self, ig_id, token, image_urls, caption, meta) -> str | None:
        child_ids = []
        for url in image_urls[:10]:
            c = requests.post(
                f'{GRAPH_BASE}/{ig_id}/media',
                data={'image_url': url, 'is_carousel_item': True, 'access_token': token},
                timeout=15,
            )
            c.raise_for_status()
            child_ids.append(c.json().get('id'))

        payload = {
            'media_type': 'CAROUSEL',
            'caption': caption,
            'children': ','.join(child_ids),
            'access_token': token,
        }
        payload.update(meta)
        resp = requests.post(f'{GRAPH_BASE}/{ig_id}/media', data=payload, timeout=15)
        resp.raise_for_status()
        return resp.json().get('id')

    # ------------------------------------------------------------------
    # Collection (recent media + comments)
    # ------------------------------------------------------------------

    def collect_recent(self, since_id: str | None = None, limit: int = 50) -> list[CollectedItem]:
        ig_id = self.credentials.get('instagram_account_id') or self.credentials.get('instagram_id') or self.config.get('instagram_account_id')
        token = self.credentials.get('page_access_token') or self.credentials.get('access_token')
        try:
            params = {
                'fields': 'id,caption,timestamp,like_count,comments_count,username',
                'limit': min(limit, 100),
                'access_token': token,
            }
            resp = requests.get(f'{GRAPH_BASE}/{ig_id}/media', params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return [
                CollectedItem(
                    platform_content_id=m.get('id', ''),
                    content_type='post',
                    raw_text=m.get('caption', ''),
                    platform_created_at=m.get('timestamp'),
                    likes=m.get('like_count', 0),
                    comments=m.get('comments_count', 0),
                    extra=m,
                )
                for m in data.get('data', [])
            ]
        except requests.RequestException as exc:
            self._log_error('collect_recent', exc)
            return []

    def collect_comments(self, media_id: str, limit: int = 100) -> list[CollectedItem]:
        token = self.credentials.get('page_access_token') or self.credentials.get('access_token')
        try:
            params = {
                'fields': 'id,text,timestamp,username,like_count,replies{id,text,timestamp,username,like_count}',
                'limit': min(limit, 100),
                'access_token': token,
            }
            resp = requests.get(f'{GRAPH_BASE}/{media_id}/comments', params=params, timeout=15)
            resp.raise_for_status()
            items = []
            for c in resp.json().get('data', []):
                items.append(CollectedItem(
                    platform_content_id=c.get('id', ''),
                    content_type='comment',
                    raw_text=c.get('text', ''),
                    author_username=c.get('username'),
                    platform_created_at=c.get('timestamp'),
                    likes=c.get('like_count', 0),
                    extra={'_replies': c.get('replies', {}).get('data', [])},
                ))
                # Flatten replies as child items
                for r in c.get('replies', {}).get('data', []):
                    items.append(CollectedItem(
                        platform_content_id=r.get('id', ''),
                        content_type='comment',
                        raw_text=r.get('text', ''),
                        author_username=r.get('username'),
                        platform_created_at=r.get('timestamp'),
                        likes=r.get('like_count', 0),
                        extra={'_parent_platform_id': c.get('id')},
                    ))
            return items
        except requests.RequestException as exc:
            self._log_error('collect_comments', exc)
            return []

    def sync_post_comments(
        self,
        post_id: str,
        platform_media_id: str,
        district_id: str,
        limit: int = 100,
    ) -> int:
        """Collect and persist Instagram comments for a published post.

        Args:
            post_id:            Internal SocialPost UUID.
            platform_media_id:  Instagram media ID.
            district_id:        Tenant scope.
            limit:              Max comments to fetch.

        Returns:
            Number of new comments stored.
        """
        from app.services.social.comment_service import upsert_comment

        items = self.collect_comments(platform_media_id, limit=limit)
        new_count = 0

        for item in items:
            if not item.raw_text.strip():
                continue

            parent_platform_id = item.extra.get('_parent_platform_id')
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
                platform='instagram',
                platform_comment_id=item.platform_content_id,
                text=item.raw_text,
                parent_comment_id=parent_db_id,
                author_username=item.author_username,
                platform_created_at=item.platform_created_at,
                likes=item.likes,
                run_ai=False,
            )
            if created:
                new_count += 1

        logger.info('Instagram sync: %d new comments for post %s', new_count, post_id)
        return new_count

    def get_account_info(self) -> dict:
        ig_id = self.credentials.get('instagram_account_id') or self.credentials.get('instagram_id') or self.config.get('instagram_account_id')
        token = self.credentials.get('page_access_token') or self.credentials.get('access_token')
        try:
            resp = requests.get(
                f'{GRAPH_BASE}/{ig_id}',
                params={'fields': 'id,name,username,followers_count,media_count', 'access_token': token},
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            self._log_error('get_account_info', exc)
            return {}
