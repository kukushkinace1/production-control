from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from celery.utils.log import get_task_logger

from src.celery_app import celery_app
from src.core.config import get_settings
from src.core.database import AsyncSessionLocal
from src.domain.services import BatchService
from src.storage import MinIOService
from src.utils import generate_batches_export_csv, generate_batches_export_excel

logger = get_task_logger(__name__)


async def _export_batches_to_file_async(
    task_id: str,
    filters: dict[str, Any],
    report_format: str,
) -> dict[str, Any]:
    settings = get_settings()
    celery_app.backend.store_result(
        task_id,
        {"current": 1, "total": 3, "progress": 33, "stage": "loading_batches"},
        state="PROGRESS",
    )

    async with AsyncSessionLocal() as session:
        service = BatchService(session)
        rows = await service.get_batches_export_data(filters)

    celery_app.backend.store_result(
        task_id,
        {"current": 2, "total": 3, "progress": 66, "stage": "generating_file"},
        state="PROGRESS",
    )
    if report_format == "csv":
        file_bytes = generate_batches_export_csv(rows)
        extension = "csv"
        content_type = "text/csv"
    else:
        file_bytes = generate_batches_export_excel(rows)
        extension = "xlsx"
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    object_name = (
        f"batch-exports/batches_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.{extension}"
    )
    minio_service = MinIOService()
    minio_service.ensure_bucket(settings.minio_exports_bucket)
    url = minio_service.upload_bytes(
        bucket=settings.minio_exports_bucket,
        object_name=object_name,
        data=file_bytes,
        content_type=content_type,
    )

    return {
        "success": True,
        "format": report_format,
        "bucket": settings.minio_exports_bucket,
        "object_name": object_name,
        "url": url,
        "total_batches": len(rows),
    }


@celery_app.task(bind=True, max_retries=3)
def export_batches_to_file(
    self,
    filters: dict[str, Any] | None = None,
    report_format: str = "excel",
) -> dict[str, Any]:
    try:
        return asyncio.run(
            _export_batches_to_file_async(
                task_id=self.request.id,
                filters=filters or {},
                report_format=report_format,
            )
        )
    except Exception as exc:
        logger.exception("Batch export failed", extra={"filters": filters})
        raise self.retry(exc=exc, countdown=min(2**self.request.retries, 30)) from exc
