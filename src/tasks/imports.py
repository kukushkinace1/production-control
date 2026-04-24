from __future__ import annotations

import asyncio
from typing import Any

from celery.utils.log import get_task_logger

from src.celery_app import celery_app
from src.core.database import AsyncSessionLocal
from src.domain.services import BatchService
from src.storage import MinIOService
from src.utils import parse_batch_import_file

logger = get_task_logger(__name__)


async def _import_batches_from_file_async(
    task_id: str,
    bucket: str,
    object_name: str,
    file_name: str,
) -> dict[str, Any]:
    celery_app.backend.store_result(
        task_id,
        {"current": 0, "total": 0, "created": 0, "skipped": 0, "stage": "downloading_file"},
        state="PROGRESS",
    )
    minio_service = MinIOService()
    file_bytes = minio_service.download_bytes(bucket=bucket, object_name=object_name)
    rows, validation_errors = parse_batch_import_file(file_bytes, file_name)

    async with AsyncSessionLocal() as session:
        service = BatchService(session)

        def update_progress(current: int, total: int, created: int, skipped: int) -> None:
            celery_app.backend.store_result(
                task_id,
                {
                    "current": current,
                    "total": total,
                    "created": created,
                    "skipped": skipped + len(validation_errors),
                    "progress": round((current / total) * 100, 2) if total else 100,
                    "stage": "importing_rows",
                },
                state="PROGRESS",
            )

        return await service.import_batch_rows(
            rows=rows,
            validation_errors=validation_errors,
            progress_callback=update_progress,
        )


@celery_app.task(bind=True, max_retries=1)
def import_batches_from_file(
    self,
    bucket: str,
    object_name: str,
    file_name: str,
) -> dict[str, Any]:
    try:
        return asyncio.run(
            _import_batches_from_file_async(
                task_id=self.request.id,
                bucket=bucket,
                object_name=object_name,
                file_name=file_name,
            )
        )
    except Exception as exc:
        logger.exception(
            "Batch import failed",
            extra={"bucket": bucket, "object_name": object_name},
        )
        raise self.retry(exc=exc, countdown=5) from exc
