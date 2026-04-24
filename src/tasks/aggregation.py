import asyncio
from typing import Any

from celery.utils.log import get_task_logger

from src.api.v1.schemas.batch import BatchAggregationResponse
from src.celery_app import celery_app
from src.core.database import AsyncSessionLocal
from src.domain.exceptions import DomainError
from src.domain.services import BatchService

logger = get_task_logger(__name__)


async def _aggregate_products_batch_async(
    task_id: str,
    batch_id: int,
    unique_codes: list[str],
) -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        service = BatchService(session)

        async def report_progress(current: int, total: int) -> None:
            progress = int((current / total) * 100) if total else 100
            celery_app.backend.store_result(
                task_id,
                {
                    "current": current,
                    "total": total,
                    "progress": progress,
                },
                state="PROGRESS",
            )

        response: BatchAggregationResponse = await service.aggregate_products_by_codes(
            batch_id=batch_id,
            unique_codes=unique_codes,
            progress_callback=report_progress,
        )
        return response.model_dump(mode="json")


@celery_app.task(bind=True, max_retries=3)
def aggregate_products_batch(
    self,
    batch_id: int,
    unique_codes: list[str],
    user_id: int | None = None,
) -> dict[str, Any]:
    try:
        self.update_state(
            state="PROGRESS",
            meta={
                "current": 0,
                "total": len(unique_codes),
                "progress": 0,
            },
        )
        result = asyncio.run(
            _aggregate_products_batch_async(
                task_id=self.request.id,
                batch_id=batch_id,
                unique_codes=unique_codes,
            )
        )
        result["success"] = True
        if user_id is not None:
            result["user_id"] = user_id
        return result
    except DomainError:
        logger.exception(
            "Batch aggregation task failed without retry",
            extra={"batch_id": batch_id},
        )
        raise
    except Exception as exc:
        logger.exception("Batch aggregation task failed", extra={"batch_id": batch_id})
        raise self.retry(exc=exc, countdown=min(2**self.request.retries, 30)) from exc
