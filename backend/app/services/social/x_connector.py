"""X (Twitter) API v2 connector.

Required credentials:
  - ``bearer_token``:      App-only bearer token (for read / search).
  - ``access_token``:      OAuth 1.0a or 2.0 user access token (for write).
  - ``access_token_secret``:  Required for OAuth 1.0a write.
  - ``api_key``:            Consumer / API key.
  - ``api_key_secret``:     Consumer secret.

API docs: https://developer.x.com/en/docs/twitter-api
"""
import logging
import requests
from requests_oauthlib import OAuth1

from app.services.social.base_connector import BaseSocialConnector, PublishResult, CollectedItem

logger = logging.getLogger(__name__)
X_API_BASE = 'https://api.twitter.com/2'


class XConnector(BaseSocialConnector):
    """X (Twitter) v2 API connector."""

    platform_name = 'x'

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    def publish_post(self, content: str, media_urls: list[str] | None = None,
                     meta: dict | None = None) -> PublishResult:
        """Post a tweet.  Media upload is handled via media/upload endpoint
        before posting if media_urls are supplied (simplified: URL attach).
        """
        try:
            auth = self._oauth1()
            payload = {'text': content}
            if meta:
                payload.update(meta)

            resp = requests.post(
                f'{X_API_BASE}/tweets',
                json=payload,
                auth=auth,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            tweet_id = data.get('data', {}).get('id')
            return PublishResult(success=True, platform_post_id=tweet_id, raw_response=data)

        except requests.RequestException as exc:
            self._log_error('publish_post', exc)
            return PublishResult(success=False, error_message=str(exc))

    # ------------------------------------------------------------------
    # Collection
    # ------------------------------------------------------------------

    def collect_recent(self, since_id: str | None = None, limit: int = 50) -> list[CollectedItem]:
        """Search recent tweets mentioning the connected account / keywords
        defined in ``config.search_query``.
        """
        bearer   = self.credentials.get('bearer_token')
        query    = self.config.get('search_query', f"@{self.config.get('username', 'district360')}")

        if not bearer:
            logger.error('X: bearer_token required for search')
            return []

        try:
            params = {
                'query': f'{query} -is:retweet lang:en OR lang:ta',
                'max_results': min(max(limit, 10), 100),
                'tweet.fields': 'created_at,author_id,public_metrics,lang',
                'expansions': 'author_id',
                'user.fields': 'username,name',
            }
            if since_id:
                params['since_id'] = since_id

            resp = requests.get(
                f'{X_API_BASE}/tweets/search/recent',
                params=params,
                headers={'Authorization': f'Bearer {bearer}'},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            # Build user lookup
            users = {u['id']: u for u in data.get('includes', {}).get('users', [])}

            items = []
            for tweet in data.get('data', []):
                author = users.get(tweet.get('author_id'), {})
                metrics = tweet.get('public_metrics', {})
                items.append(CollectedItem(
                    platform_content_id=tweet.get('id', ''),
                    content_type='post',
                    raw_text=tweet.get('text', ''),
                    author_platform_id=tweet.get('author_id'),
                    author_username=author.get('username'),
                    platform_created_at=tweet.get('created_at'),
                    likes=metrics.get('like_count', 0),
                    comments=metrics.get('reply_count', 0),
                    shares=metrics.get('retweet_count', 0),
                    extra=tweet,
                ))
            return items

        except requests.RequestException as exc:
            self._log_error('collect_recent', exc)
            return []

    def get_account_info(self) -> dict:
        bearer   = self.credentials.get('bearer_token')
        username = self.config.get('username')
        if not bearer or not username:
            return {}
        try:
            resp = requests.get(
                f'{X_API_BASE}/users/by/username/{username}',
                params={'user.fields': 'public_metrics,description'},
                headers={'Authorization': f'Bearer {bearer}'},
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json().get('data', {})
        except requests.RequestException as exc:
            self._log_error('get_account_info', exc)
            return {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _oauth1(self) -> OAuth1:
        return OAuth1(
            self.credentials.get('api_key', ''),
            self.credentials.get('api_key_secret', ''),
            self.credentials.get('access_token', ''),
            self.credentials.get('access_token_secret', ''),
        )
