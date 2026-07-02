"""Health check service — DB, Redis, platform connectivity probes."""
from __future__ import annotations
import logging
import time
from datetime import datetime, timezone

from app.utils.db import check_database_connection

logger = logging.getLogger(__name__)


def get_full_health() -> dict:
    """Run all health probes and return a comprehensive status report.

    Returns:
        Dict with ``status`` (healthy/degraded/unhealthy), ``checks`` (per-component),
        and ``timestamp``.
    """
    checks = {}

    # Database
    checks['database'] = _probe_database()

    # Redis (optional — only if RATE_LIMIT_STORAGE_URI is a Redis URL)
    checks['redis'] = _probe_redis()

    # Disk / memory (lightweight sanity check)
    checks['system'] = _probe_system()

    # Determine overall status
    statuses = [c['status'] for c in checks.values()]
    if all(s == 'healthy' for s in statuses):
        overall = 'healthy'
    elif any(s == 'unhealthy' for s in statuses):
        overall = 'unhealthy'
    else:
        overall = 'degraded'

    return {
        'status': overall,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'checks': checks,
    }


def _probe_database() -> dict:
    start = time.perf_counter()
    ok = check_database_connection()
    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    return {
        'status': 'healthy' if ok else 'unhealthy',
        'latency_ms': latency_ms,
        'message': 'Connected' if ok else 'Connection failed',
    }


def _probe_redis() -> dict:
    import os
    uri = os.getenv('RATE_LIMIT_STORAGE_URI', 'memory://')
    if not uri.startswith('redis'):
        return {'status': 'healthy', 'message': 'Using in-memory store (no Redis configured)'}

    try:
        import redis as _redis
        start = time.perf_counter()
        r = _redis.from_url(uri)
        r.ping()
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return {'status': 'healthy', 'latency_ms': latency_ms, 'message': 'Pong received'}
    except Exception as exc:
        return {'status': 'degraded', 'message': f'Redis unreachable: {exc}'}


def _probe_system() -> dict:
    try:
        import shutil
        total, used, free = shutil.disk_usage('/')
        free_pct = round(free / total * 100, 1)
        status = 'healthy' if free_pct > 10 else 'degraded'
        return {
            'status': status,
            'disk_free_pct': free_pct,
            'message': f'{free_pct}% disk free',
        }
    except Exception:
        return {'status': 'healthy', 'message': 'System probe unavailable'}
