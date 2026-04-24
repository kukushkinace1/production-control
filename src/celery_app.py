from celery import Celery

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
)
