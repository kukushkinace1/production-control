from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from celery.utils.log import get_task_logger

from src.celery_app import celery_app
from src.core.config import get_settings
from src.core.database import AsyncSessionLocal
from src.data.repositories import BatchRepository, WebhookRepository
from src.domain.services import AnalyticsService, BatchService
from src.storage import MinIOService
from src.tasks.webhooks import send_webhook_delivery

logger = get_task_logger(__name__)


async def _auto_close_expired_batches_async() -> dict[str, Any]:
    now = datetime.now(UTC)
    async with AsyncSessionLocal() as session:
        repository = BatchRepository(session)
        batches = await repository.list_expired_open_batches(now)
        closed_ids: list[int] = []

        for batch in batches:
            batch.is_closed = True
            batch.closed_at = now
            closed_ids.append(batch.id)

        await session.commit()

        service = BatchService(session)
        await service.invalidate_batch_cache()
        for batch in batches:
            await service._emit_event(
                "batch_closed",
                {
                    **service._build_batch_event_payload(batch),
                    "closed_at": batch.closed_at.isoformat() if batch.closed_at else None,
                    "statistics": service._build_batch_statistics_payload(batch),
                },
            )

    return {"success": True, "closed": len(closed_ids), "batch_ids": closed_ids}


@celery_app.task(name="src.tasks.scheduled.auto_close_expired_batches")
def auto_close_expired_batches() -> dict[str, Any]:
    return asyncio.run(_auto_close_expired_batches_async())


@celery_app.task(name="src.tasks.scheduled.cleanup_old_files")
def cleanup_old_files(days: int = 30) -> dict[str, Any]:
    settings = get_settings()
    cutoff = datetime.now(UTC) - timedelta(days=days)
    service = MinIOService()
    buckets = [
        settings.minio_reports_bucket,
        settings.minio_exports_bucket,
        settings.minio_imports_bucket,
    ]

    deleted_by_bucket: dict[str, int] = {}
    for bucket in buckets:
        try:
            service.ensure_bucket(bucket)
            deleted_by_bucket[bucket] = service.delete_objects_older_than(
                bucket=bucket,
                older_than=cutoff,
            )
        except Exception:
            logger.exception("Failed to cleanup MinIO bucket", extra={"bucket": bucket})
            deleted_by_bucket[bucket] = 0

    return {
        "success": True,
        "days": days,
        "deleted": sum(deleted_by_bucket.values()),
        "buckets": deleted_by_bucket,
    }


async def _update_cached_statistics_async() -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        service = AnalyticsService(session)
        await service.cache.delete("dashboard_stats")
        dashboard = await service.get_dashboard()
    return {
        "success": True,
        "cached": "dashboard_stats",
        "total_batches": dashboard["summary"]["total_batches"],
    }


@celery_app.task(name="src.tasks.scheduled.update_cached_statistics")
def update_cached_statistics() -> dict[str, Any]:
    return asyncio.run(_update_cached_statistics_async())


async def _retry_failed_webhooks_async() -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        repository = WebhookRepository(session)
        deliveries = await repository.list_retryable_failed_deliveries()
        delivery_ids = [delivery.id for delivery in deliveries]

    for delivery_id in delivery_ids:
        send_webhook_delivery.delay(delivery_id)

    return {"success": True, "queued": len(delivery_ids), "delivery_ids": delivery_ids}


@celery_app.task(name="src.tasks.scheduled.retry_failed_webhooks")
def retry_failed_webhooks() -> dict[str, Any]:
    return asyncio.run(_retry_failed_webhooks_async())
