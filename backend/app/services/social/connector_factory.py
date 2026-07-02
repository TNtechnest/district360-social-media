"""ConnectorFactory — resolves the correct platform connector for a SocialAccount.

Usage::

    from app.services.social.connector_factory import ConnectorFactory
    connector = ConnectorFactory.get(social_account)
    result    = connector.publish_post("Hello world!")
"""
import logging

from app.models.social_account import SocialAccount
from app.services.social.base_connector import BaseSocialConnector

logger = logging.getLogger(__name__)


class ConnectorFactory:
    """Returns an initialised connector for a given SocialAccount."""

    _REGISTRY: dict[str, type] = {}

    @classmethod
    def register(cls, platform: str, connector_class: type) -> None:
        """Register a connector class for a platform name."""
        cls._REGISTRY[platform] = connector_class

    @classmethod
    def get(cls, account: SocialAccount) -> BaseSocialConnector:
        """Return an initialised connector for *account*.

        Args:
            account: A :class:`SocialAccount` model instance.

        Returns:
            Initialised subclass of :class:`BaseSocialConnector`.

        Raises:
            ValueError: If no connector is registered for the platform.
        """
        connector_class = cls._REGISTRY.get(account.platform)
        if not connector_class:
            raise ValueError(f"No connector registered for platform '{account.platform}'.")
        return connector_class(credentials=account.credentials, config=account.config)


# ---------------------------------------------------------------------------
# Register all built-in connectors
# ---------------------------------------------------------------------------

def _register_defaults():
    from app.services.social.facebook_connector  import FacebookConnector
    from app.services.social.instagram_connector import InstagramConnector
    from app.services.social.youtube_connector   import YouTubeConnector
    from app.services.social.x_connector         import XConnector
    from app.services.social.telegram_connector  import TelegramConnector

    ConnectorFactory.register('facebook',  FacebookConnector)
    ConnectorFactory.register('instagram', InstagramConnector)
    ConnectorFactory.register('youtube',   YouTubeConnector)
    ConnectorFactory.register('x',         XConnector)
    ConnectorFactory.register('telegram',  TelegramConnector)


_register_defaults()
