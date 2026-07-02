"""Celery application configuration for District360 background tasks.

Usage::

    from app.services.infrastructure.celery_app import celery_app

    @celery_app.task
    def my_background_task(arg1, arg2):
        ...

Run the worker::

    celery -A app.services.infrastructure.celery_app worker --loglevel=info

Run beat scheduler::

    celery -A app.services.infrastructure.celery_app beat --loglevel=info
"""

from __future__ import annotations
import logging
import os

logger = logging.getLogger(__name__)

try:
    from celery import Celery

    def make_celery(app_name: str = 'district360') -> Celery:
        broker_url = os.getenv('CELERY_BROKER_URL', os.getenv('REDIS_URL', 'redis://localhost:6379/1'))
        result_backend = os.getenv('CELERY_RESULT_BACKEND', os.getenv('REDIS_URL', 'redis://localhost:6379/2'))

        celery_app = Celery(
            app_name,
            broker=broker_url,
            backend=result_backend,
        )

        celery_app.conf.update(
            task_serializer='json',
            accept_content=['json'],
            result_serializer='json',
            timezone='UTC',
            enable_utc=True,
            task_track_started=True,
            task_soft_time_limit=int(os.getenv('CELERY_TASK_SOFT_LIMIT', 300)),
            task_time_limit=int(os.getenv('CELERY_TASK_TIME_LIMIT', 600)),
            worker_max_tasks_per_child=int(os.getenv('CELERY_MAX_TASKS_PER_CHILD', 1000)),
            worker_prefetch_multiplier=1,
            beat_schedule={
                'check-sla-breaches': {
                    'task': 'app.services.infrastructure.tasks.check_sla_breaches_task',
                    'schedule': 300.0,  # every 5 minutes
                },
                'run-due-schedules': {
                    'task': 'app.services.infrastructure.tasks.run_due_schedules_task',
                    'schedule': 60.0,  # every 1 minute
                },
                'clean-expired-otps': {
                    'task': 'app.services.infrastructure.tasks.clean_expired_otps_task',
                    'schedule': 3600.0,  # every hour
                },
                'collect-social-comments': {
                    'task': 'app.services.infrastructure.tasks.collect_social_comments_task',
                    'schedule': float(os.getenv('SOCIAL_COLLECTOR_INTERVAL_SECONDS', 900)),
                },
            },
        )

        return celery_app

    celery_app = make_celery()

except ImportError:
    celery_app = None
    logger.warning('Celery not installed. Background tasks will not be available.')


# ---------------------------------------------------------------------------
# Helper to run tasks synchronously when Celery is unavailable
# ---------------------------------------------------------------------------

def run_sync(fn, *args, **kwargs):
    """Run a background-task function synchronously (Celery not required).

    Useful in development or when the task must complete before the response.
    """
    logger.info('Running task %s synchronously (Celery not available).', fn.__name__)
    return fn(*args, **kwargs)
