"""Base connector interface for all social platform integrations.

Every platform connector must subclass ``BaseSocialConnector`` and
implement the abstract methods.  The service layer calls these methods
via the ``ConnectorFactory`` to remain platform-agnostic.
"""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class PublishResult:
    """Result returned after attempting to publish a post."""
    success: bool
    platform_post_id: str | None = None
    error_message: str | None = None
    raw_response: dict = field(default_factory=dict)


@dataclass
class CollectedItem:
    """A single piece of content collected from a platform."""
    platform_content_id: str
    content_type: str          # post | comment | mention | dm
    raw_text: str
    author_platform_id: str | None = None
    author_username: str | None = None
    platform_created_at: str | None = None
    likes: int = 0
    comments: int = 0
    shares: int = 0
    extra: dict = field(default_factory=dict)


class BaseSocialConnector(ABC):
    """Abstract base class for social platform connectors."""

    platform_name: str = 'base'

    def __init__(self, credentials: dict, config: dict | None = None):
        """
        Args:
            credentials: Platform-specific auth tokens / API keys.
            config:      Optional extra configuration (page_id, channel_id, etc.).
        """
        self.credentials = credentials
        self.config = config or {}

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    @abstractmethod
    def publish_post(self, content: str, media_urls: list[str] | None = None,
                     meta: dict | None = None) -> PublishResult:
        """Publish a text post (optionally with media) to the platform.

        Args:
            content:    Text body of the post.
            media_urls: Public URLs of attached images / videos.
            meta:       Platform-specific extra parameters.

        Returns:
            :class:`PublishResult`
        """

    # ------------------------------------------------------------------
    # Collection
    # ------------------------------------------------------------------

    @abstractmethod
    def collect_recent(self, since_id: str | None = None,
                       limit: int = 50) -> list[CollectedItem]:
        """Collect recent public posts / comments / mentions.

        Args:
            since_id: Platform content ID to paginate from.
            limit:    Max items to return.

        Returns:
            List of :class:`CollectedItem`.
        """

    # ------------------------------------------------------------------
    # Account info
    # ------------------------------------------------------------------

    @abstractmethod
    def get_account_info(self) -> dict:
        """Return basic account / page / channel metadata."""

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _log_error(self, operation: str, error: Exception) -> None:
        logger.error('[%s] %s failed: %s', self.platform_name, operation, error)
