from celery import Celery
from celery.schedules import crontab

from src.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "production_control",
    broker=settings.rabbitmq_url,
    backend=settings.redis_url,
    include=[
        "src.tasks.aggregation",
        "src.tasks.exports",
        "src.tasks.imports",
        "src.tasks.reports",
        "src.tasks.scheduled",
        "src.tasks.webhooks",
    ],
)

celery_app.conf.update(
    task_serializer=settings.celery_task_serializer,
    result_serializer=settings.celery_result_serializer,
    accept_content=[settings.celery_accept_content],
    task_track_started=True,
    result_extended=True,
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "auto-close-expired-batches": {
            "task": "src.tasks.scheduled.auto_close_expired_batches",
            "schedule": crontab(hour=1, minute=0),
        },
        "cleanup-old-files": {
            "task": "src.tasks.scheduled.cleanup_old_files",
            "schedule": crontab(hour=2, minute=0),
        },
        "update-cached-statistics": {
            "task": "src.tasks.scheduled.update_cached_statistics",
            "schedule": crontab(minute="*/5"),
        },
        "retry-failed-webhooks": {
            "task": "src.tasks.scheduled.retry_failed_webhooks",
            "schedule": crontab(minute="*/15"),
        },
    },
)
