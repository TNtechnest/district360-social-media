"""Redis service — token blocklist, caching, rate-limit store, pub/sub.

Provides a singleton Redis client that can be used across the application.
Falls back to in-memory stores when Redis is not configured (development).

Set ``REDIS_URL=redis://localhost:6379/0`` in production to enable Redis.
"""

from __future__ import annotations
import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_redis_client = None
_memory_store: dict[str, str] = {}
_memory_expiry: dict[str, float] = {}


def _get_client():
    """Lazy-init Redis client."""
    global _redis_client
    if _redis_client is None:
        redis_url = os.getenv('REDIS_URL', '')
        if redis_url:
            try:
                import redis as _redis
                _redis_client = _redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2,
                )
                _redis_client.ping()
                logger.info('Redis connected: %s', redis_url)
            except Exception as exc:
                logger.warning('Redis unavailable (%s). Falling back to in-memory store.', exc)
                _redis_client = None
        else:
            logger.info('REDIS_URL not set. Using in-memory store.')
    return _redis_client


def is_redis_available() -> bool:
    """Return True if Redis is connected and responsive."""
    client = _get_client()
    if client:
        try:
            return client.ping()
        except Exception:
            return False
    return False


# ---------------------------------------------------------------------------
# Generic Cache (get / set / delete / exists)
# ---------------------------------------------------------------------------

def cache_set(key: str, value: Any, ttl_seconds: int = 300) -> None:
    """Set a cache value with TTL."""
    client = _get_client()
    serialized = json.dumps(value, default=str)
    if client:
        client.setex(key, ttl_seconds, serialized)
    else:
        _memory_store[key] = serialized
        _memory_expiry[key] = __import__('time').time() + ttl_seconds


def cache_get(key: str) -> Any | None:
    """Get a cache value, returning None if missing or expired."""
    client = _get_client()
    if client:
        val = client.get(key)
        return json.loads(val) if val else None
    else:
        import time
        expiry = _memory_expiry.get(key, 0)
        if time.time() > expiry:
            _memory_store.pop(key, None)
            _memory_expiry.pop(key, None)
            return None
        raw = _memory_store.get(key)
        return json.loads(raw) if raw else None


def cache_delete(key: str) -> None:
    """Delete a key from cache."""
    client = _get_client()
    if client:
        client.delete(key)
    else:
        _memory_store.pop(key, None)
        _memory_expiry.pop(key, None)


def cache_exists(key: str) -> bool:
    """Return True if key exists in cache."""
    client = _get_client()
    if client:
        return bool(client.exists(key))
    else:
        import time
        expiry = _memory_expiry.get(key, 0)
        if time.time() > expiry:
            _memory_store.pop(key, None)
            _memory_expiry.pop(key, None)
            return False
        return key in _memory_store


# ---------------------------------------------------------------------------
# Token Blocklist (Redis-backed, replacing in-memory set in auth_service)
# ---------------------------------------------------------------------------

_BLOCKLIST_PREFIX = 'blocklist:'


def block_token(jti: str, ttl_seconds: int = 86400) -> None:
    """Add a JWT's JTI to the blocklist.

    Args:
        jti:         JWT ID claim to revoke.
        ttl_seconds: How long to keep the JTI in the blocklist (default 24h).
    """
    cache_set(f'{_BLOCKLIST_PREFIX}{jti}', 'revoked', ttl_seconds=ttl_seconds)


def is_token_blocked(jti: str) -> bool:
    """Return True if the token JTI is in the blocklist."""
    return cache_exists(f'{_BLOCKLIST_PREFIX}{jti}')


def unblock_token(jti: str) -> None:
    """Remove a JTI from the blocklist (for testing/admin)."""
    cache_delete(f'{_BLOCKLIST_PREFIX}{jti}')


# ---------------------------------------------------------------------------
# Rate Limit Store (used by flask-limiter in production)
# ---------------------------------------------------------------------------

def get_rate_limit_store() -> str:
    """Return the Redis URI for flask-limiter, or 'memory://' fallback."""
    return os.getenv('REDIS_URL', 'memory://')


# ---------------------------------------------------------------------------
# Pub / Sub (simple wrapper)
# ---------------------------------------------------------------------------

def publish(channel: str, message: Any) -> None:
    """Publish a message to a Redis channel."""
    client = _get_client()
    if client:
        serialized = json.dumps(message, default=str)
        client.publish(channel, serialized)
        logger.debug('Published to channel %s', channel)
    else:
        logger.debug('Redis not available — pub/sub to %s skipped.', channel)
