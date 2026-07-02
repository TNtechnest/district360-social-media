"""Telegram Bot API connector.

Required credentials:
  - ``bot_token``:  BotFather token (e.g. ``123456:ABCdef...``).
  - ``chat_id``:    Target channel / group / chat ID (can be @channelusername
                    or a numeric ID).  Also stored in ``config.chat_id``.

Telegram bots can send messages AND receive updates via getUpdates (polling)
or webhooks.  This connector uses polling for collection and sendMessage for
publishing.

API docs: https://core.telegram.org/bots/api
"""
import logging
import requests

from app.services.social.base_connector import BaseSocialConnector, PublishResult, CollectedItem

logger = logging.getLogger(__name__)
TG_BASE = 'https://api.telegram.org/bot{token}'


class TelegramConnector(BaseSocialConnector):
    """Telegram Bot connector."""

    platform_name = 'telegram'

    @property
    def _base(self) -> str:
        token = self.credentials.get('bot_token', '')
        return TG_BASE.format(token=token)

    @property
    def _chat_id(self) -> str:
        return self.credentials.get('chat_id') or self.config.get('chat_id', '')

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    def publish_post(self, content: str, media_urls: list[str] | None = None,
                     meta: dict | None = None) -> PublishResult:
        """Send a message (optionally with a photo) to the configured channel / group."""
        try:
            if media_urls:
                # Send first image as a photo with caption
                resp = requests.post(
                    f'{self._base}/sendPhoto',
                    json={
                        'chat_id': self._chat_id,
                        'photo': media_urls[0],
                        'caption': content,
                        'parse_mode': 'HTML',
                    },
                    timeout=15,
                )
            else:
                resp = requests.post(
                    f'{self._base}/sendMessage',
                    json={
                        'chat_id': self._chat_id,
                        'text': content,
                        'parse_mode': 'HTML',
                    },
                    timeout=15,
                )
            resp.raise_for_status()
            data = resp.json()
            msg_id = str(data.get('result', {}).get('message_id', ''))
            return PublishResult(success=True, platform_post_id=msg_id, raw_response=data)

        except requests.RequestException as exc:
            self._log_error('publish_post', exc)
            return PublishResult(success=False, error_message=str(exc))

    # ------------------------------------------------------------------
    # Collection (polling via getUpdates)
    # ------------------------------------------------------------------

    def collect_recent(self, since_id: str | None = None, limit: int = 50) -> list[CollectedItem]:
        """Poll recent updates from the bot.

        Args:
            since_id: Offset (last update_id + 1) for incremental polling.
            limit:    Max updates to fetch (capped at 100).
        """
        try:
            params = {'limit': min(limit, 100), 'timeout': 0}
            if since_id:
                params['offset'] = int(since_id)

            resp = requests.get(f'{self._base}/getUpdates', params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()

            items = []
            for update in data.get('result', []):
                msg = update.get('message') or update.get('channel_post') or {}
                text = msg.get('text') or msg.get('caption') or ''
                if not text:
                    continue
                frm  = msg.get('from') or msg.get('sender_chat') or {}
                items.append(CollectedItem(
                    platform_content_id=str(update.get('update_id', '')),
                    content_type='post' if 'channel_post' in update else 'dm',
                    raw_text=text,
                    author_platform_id=str(frm.get('id', '')),
                    author_username=frm.get('username') or frm.get('title'),
                    platform_created_at=str(msg.get('date', '')),
                    extra=update,
                ))
            return items

        except requests.RequestException as exc:
            self._log_error('collect_recent', exc)
            return []

    def get_account_info(self) -> dict:
        try:
            resp = requests.get(f'{self._base}/getMe', timeout=10)
            resp.raise_for_status()
            return resp.json().get('result', {})
        except requests.RequestException as exc:
            self._log_error('get_account_info', exc)
            return {}
