from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from celery.utils.log import get_task_logger

from src.celery_app import celery_app
from src.core.config import get_settings
from src.core.database import AsyncSessionLocal
from src.domain.exceptions import DomainError
from src.domain.services import BatchService
from src.storage import MinIOService
from src.utils import generate_batch_report_excel

logger = get_task_logger(__name__)


async def _generate_batch_report_async(
    task_id: str,
    batch_id: int,
    report_format: str,
) -> dict[str, Any]:
    settings = get_settings()
    async with AsyncSessionLocal() as session:
        service = BatchService(session)

        celery_app.backend.store_result(
            task_id,
            {"current": 1, "total": 3, "progress": 33, "stage": "loading_batch"},
            state="PROGRESS",
        )
        report_data = await service.get_batch_report_data(batch_id)

    celery_app.backend.store_result(
        task_id,
        {"current": 2, "total": 3, "progress": 66, "stage": "generating_excel"},
        state="PROGRESS",
    )
    workbook_bytes = generate_batch_report_excel(report_data)

    object_name = (
        f"batch-reports/batch-{batch_id}/"
        f"batch_{batch_id}_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.xlsx"
    )
    minio_service = MinIOService()
    minio_service.ensure_bucket(settings.minio_reports_bucket)
    url = minio_service.upload_bytes(
        bucket=settings.minio_reports_bucket,
        object_name=object_name,
        data=workbook_bytes,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    return {
        "success": True,
        "batch_id": batch_id,
        "format": report_format,
        "bucket": settings.minio_reports_bucket,
        "object_name": object_name,
        "url": url,
    }


@celery_app.task(bind=True, max_retries=3)
def generate_batch_report(self, batch_id: int, report_format: str = "excel") -> dict[str, Any]:
    try:
        self.update_state(
            state="PROGRESS",
            meta={"current": 0, "total": 3, "progress": 0, "stage": "queued"},
        )
        return asyncio.run(
            _generate_batch_report_async(
                task_id=self.request.id,
                batch_id=batch_id,
                report_format=report_format,
            )
        )
    except DomainError:
        logger.exception(
            "Batch report generation failed without retry",
            extra={"batch_id": batch_id},
        )
        raise
    except Exception as exc:
        logger.exception("Batch report generation failed", extra={"batch_id": batch_id})
        raise self.retry(exc=exc, countdown=min(2**self.request.retries, 30)) from exc
