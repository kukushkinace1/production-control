from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.batch import (
    AggregationError,
    BatchAggregationRequest,
    BatchAggregationResponse,
    BatchCreateRequest,
    BatchDetailResponse,
    BatchFilterParams,
    BatchResponse,
    BatchUpdateRequest,
)
from src.core.cache import CacheService
from src.data.models import Batch, Product, WorkCenter
from src.data.repositories import (
    BatchRepository,
    ProductRepository,
    WebhookRepository,
    WorkCenterRepository,
)
from src.domain.exceptions import ConflictError, NotFoundError


class BatchService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.batch_repository = BatchRepository(session)
        self.product_repository = ProductRepository(session)
        self.webhook_repository = WebhookRepository(session)
        self.work_center_repository = WorkCenterRepository(session)
        self.cache = CacheService()

    async def create_batches(self, payloads: list[BatchCreateRequest]) -> list[Batch]:
        created_batches: list[Batch] = []

        for payload in payloads:
            existing_batch = await self.batch_repository.get_by_number_and_date(
                payload.batch_number,
                payload.batch_date,
            )
            if existing_batch is not None:
                raise ConflictError(
                    "Batch with number "
                    f"{payload.batch_number} and date {payload.batch_date} already exists."
                )

            work_center = await self._get_or_create_work_center(
                payload.work_center_identifier,
                payload.work_center_name,
            )
            batch = Batch(
                is_closed=payload.is_closed,
                closed_at=datetime.now(UTC) if payload.is_closed else None,
                task_description=payload.task_description,
                work_center_id=work_center.id,
                shift=payload.shift,
                team=payload.team,
                batch_number=payload.batch_number,
                batch_date=payload.batch_date,
                nomenclature=payload.nomenclature,
                ekn_code=payload.ekn_code,
                shift_start=payload.shift_start,
                shift_end=payload.shift_end,
            )
            await self.batch_repository.create(batch)
            created_batches.append(batch)

        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("Batch creation conflicts with existing data.") from exc

        batches = [await self.get_batch(batch.id) for batch in created_batches]
        await self.invalidate_batch_cache()
        for batch in batches:
            await self._emit_event("batch_created", self._build_batch_event_payload(batch))
        return batches

    async def get_batch(self, batch_id: int) -> Batch:
        batch = await self.batch_repository.get_by_id(batch_id)
        if batch is None:
            raise NotFoundError(f"Batch {batch_id} not found.")
        return batch

    async def list_batches(self, filters: BatchFilterParams) -> tuple[list[Batch], int]:
        cache_key = f"batches_list:{filters.model_dump_json()}"
        cached = await self.cache.get_json(cache_key)
        if cached is not None:
            return cached["items"], cached["total"]

        items, total = await self.batch_repository.list(
            is_closed=filters.is_closed,
            batch_number=filters.batch_number,
            batch_date=filters.batch_date,
            work_center_id=filters.work_center_id,
            work_center_identifier=filters.work_center_identifier,
            shift=filters.shift,
            offset=filters.offset,
            limit=filters.limit,
        )
        batches = list(items)
        await self.cache.set_json(
            cache_key,
            {
                "items": [
                    BatchResponse.model_validate(batch).model_dump(mode="json")
                    for batch in batches
                ],
                "total": total,
            },
            ttl=60,
        )
        return batches, total

    async def get_batch_detail_response_data(self, batch_id: int) -> dict:
        cache_key = f"batch_detail:{batch_id}"
        cached = await self.cache.get_json(cache_key)
        if cached is not None:
            return cached

        batch = await self.get_batch(batch_id)
        data = BatchDetailResponse.model_validate(batch).model_dump(mode="json")
        await self.cache.set_json(cache_key, data, ttl=600)
        return data

    async def update_batch(self, batch_id: int, payload: BatchUpdateRequest) -> Batch:
        batch = await self.get_batch(batch_id)
        was_closed = batch.is_closed
        updates = payload.model_dump(exclude_unset=True)
        closes_batch = updates.get("is_closed") is True and not was_closed

        if "is_closed" in updates:
            is_closed = updates.pop("is_closed")
            batch.is_closed = is_closed
            batch.closed_at = datetime.now(UTC) if is_closed else None

        for field, value in updates.items():
            setattr(batch, field, value)

        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("Batch update conflicts with existing data.") from exc

        updated_batch = await self.get_batch(batch_id)
        await self.invalidate_batch_cache(batch_id)
        if closes_batch:
            await self._emit_event(
                "batch_closed",
                {
                    **self._build_batch_event_payload(updated_batch),
                    "closed_at": updated_batch.closed_at.isoformat()
                    if updated_batch.closed_at is not None
                    else None,
                    "statistics": self._build_batch_statistics_payload(updated_batch),
                },
            )
        return updated_batch

    async def aggregate_batch_products(
        self,
        batch_id: int,
        payload: BatchAggregationRequest,
    ) -> BatchAggregationResponse:
        return await self.aggregate_products_by_codes(batch_id, payload.unique_codes or [])

    async def aggregate_products_by_codes(
        self,
        batch_id: int,
        unique_codes: list[str],
        progress_callback: Callable[[int, int], Awaitable[None] | None] | None = None,
    ) -> BatchAggregationResponse:
        batch = await self.get_batch(batch_id)
        requested_codes = [code.strip() for code in unique_codes if code.strip()]
        products = await self.product_repository.get_by_unique_codes(requested_codes)
        products_by_code = {product.unique_code: product for product in products}

        aggregated = 0
        aggregated_products: list[Product] = []
        errors: list[AggregationError] = []
        aggregated_at = datetime.now(UTC)
        total = len(requested_codes)

        for index, unique_code in enumerate(requested_codes, start=1):
            product = products_by_code.get(unique_code)
            if product is None:
                errors.append(AggregationError(unique_code=unique_code, error="Product not found."))
            elif product.batch_id != batch.id:
                errors.append(
                    AggregationError(
                        unique_code=unique_code,
                        error=f"Product does not belong to batch {batch.id}.",
                    )
                )
            elif product.is_aggregated:
                errors.append(
                    AggregationError(
                        unique_code=unique_code,
                        error="Product is already aggregated.",
                    )
                )
            else:
                product.is_aggregated = True
                product.aggregated_at = aggregated_at
                aggregated += 1
                aggregated_products.append(product)

            if progress_callback is not None:
                maybe_awaitable = progress_callback(index, total)
                if maybe_awaitable is not None:
                    await maybe_awaitable

        await self.session.commit()
        await self.invalidate_batch_cache(batch.id)

        for product in aggregated_products:
            await self._emit_event(
                "product_aggregated",
                {
                    "unique_code": product.unique_code,
                    "batch_id": batch.id,
                    "batch_number": getattr(batch, "batch_number", None),
                    "aggregated_at": product.aggregated_at.isoformat()
                    if product.aggregated_at is not None
                    else None,
                },
            )

        return BatchAggregationResponse(
            batch_id=batch.id,
            total=total,
            aggregated=aggregated,
            failed=len(errors),
            errors=errors,
        )

    async def get_batch_report_data(self, batch_id: int) -> dict:
        batch = await self.get_batch(batch_id)
        total_products = len(batch.products)
        aggregated_products = sum(1 for product in batch.products if product.is_aggregated)
        remaining_products = total_products - aggregated_products
        shift_duration = batch.shift_end - batch.shift_start
        shift_duration_hours = round(shift_duration.total_seconds() / 3600, 2)
        aggregation_rate = (
            round((aggregated_products / total_products) * 100, 2) if total_products else 0.0
        )

        return {
            "batch": {
                "id": batch.id,
                "batch_number": batch.batch_number,
                "batch_date": batch.batch_date.isoformat(),
                "task_description": batch.task_description,
                "work_center_name": batch.work_center.name,
                "work_center_identifier": batch.work_center.identifier,
                "shift": batch.shift,
                "team": batch.team,
                "nomenclature": batch.nomenclature,
                "ekn_code": batch.ekn_code,
                "is_closed": batch.is_closed,
                "shift_start": batch.shift_start.isoformat(),
                "shift_end": batch.shift_end.isoformat(),
            },
            "products": [
                {
                    "unique_code": product.unique_code,
                    "is_aggregated": product.is_aggregated,
                    "aggregated_at": product.aggregated_at.isoformat()
                    if product.aggregated_at is not None
                    else None,
                    "created_at": product.created_at.isoformat(),
                }
                for product in batch.products
            ],
            "statistics": {
                "total_products": total_products,
                "aggregated_products": aggregated_products,
                "remaining_products": remaining_products,
                "aggregation_rate": aggregation_rate,
                "shift_duration_hours": shift_duration_hours,
            },
            "generated_at": datetime.now(UTC).isoformat(),
        }

    async def import_batch_rows(
        self,
        rows: list[dict],
        validation_errors: list[dict] | None = None,
        progress_callback: Callable[[int, int, int, int], Awaitable[None] | None] | None = None,
    ) -> dict:
        errors = list(validation_errors or [])
        created = 0
        skipped = 0
        total_rows = len(rows) + len(errors)

        for index, row in enumerate(rows, start=1):
            row_number = row.get("_row_number", index)
            existing_batch = await self.batch_repository.get_by_number_and_date(
                row["batch_number"],
                row["batch_date"],
            )
            if existing_batch is not None:
                skipped += 1
                errors.append(
                    {
                        "row": row_number,
                        "error": "Duplicate batch number and date.",
                    }
                )
            else:
                try:
                    work_center = await self._get_or_create_work_center(
                        row["work_center_identifier"],
                        row["work_center_name"],
                    )
                    batch = Batch(
                        is_closed=row["is_closed"],
                        closed_at=datetime.now(UTC) if row["is_closed"] else None,
                        task_description=row["task_description"],
                        work_center_id=work_center.id,
                        shift=row["shift"],
                        team=row["team"],
                        batch_number=row["batch_number"],
                        batch_date=row["batch_date"],
                        nomenclature=row["nomenclature"],
                        ekn_code=row["ekn_code"],
                        shift_start=row["shift_start"],
                        shift_end=row["shift_end"],
                    )
                    await self.batch_repository.create(batch)
                    await self.session.commit()
                    created += 1
                    await self.invalidate_batch_cache(batch.id)
                except IntegrityError as exc:
                    await self.session.rollback()
                    skipped += 1
                    errors.append({"row": row_number, "error": str(exc.orig)})

            if progress_callback is not None:
                maybe_awaitable = progress_callback(index, total_rows, created, skipped)
                if maybe_awaitable is not None:
                    await maybe_awaitable

        skipped += len(validation_errors or [])
        return {
            "success": True,
            "total_rows": total_rows,
            "created": created,
            "skipped": skipped,
            "errors": errors,
        }

    async def get_batches_export_data(self, filters: dict) -> list[dict]:
        date_from = _parse_filter_date(filters.get("date_from"))
        date_to = _parse_filter_date(filters.get("date_to"))
        batches = await self.batch_repository.list_for_export(
            is_closed=filters.get("is_closed"),
            batch_number=filters.get("batch_number"),
            date_from=date_from,
            date_to=date_to,
            work_center_identifier=filters.get("work_center_identifier"),
            shift=filters.get("shift"),
        )
        return [
            {
                "id": batch.id,
                "batch_number": batch.batch_number,
                "batch_date": batch.batch_date,
                "is_closed": batch.is_closed,
                "work_center_identifier": batch.work_center.identifier,
                "work_center_name": batch.work_center.name,
                "shift": batch.shift,
                "team": batch.team,
                "nomenclature": batch.nomenclature,
                "ekn_code": batch.ekn_code,
                "task_description": batch.task_description,
                "shift_start": batch.shift_start,
                "shift_end": batch.shift_end,
                "products_total": len(batch.products),
                "products_aggregated": sum(
                    1 for product in batch.products if product.is_aggregated
                ),
            }
            for batch in batches
        ]

    async def get_batch_statistics(self, batch_id: int) -> dict:
        cache_key = f"batch_statistics:{batch_id}"
        cached = await self.cache.get_json(cache_key)
        if cached is not None:
            return cached

        batch = await self.get_batch(batch_id)
        total_products = len(batch.products)
        aggregated = sum(1 for product in batch.products if product.is_aggregated)
        remaining = total_products - aggregated
        duration_hours = _batch_duration_hours(batch)
        elapsed_hours = _elapsed_hours(batch)
        products_per_hour = round(aggregated / elapsed_hours, 2) if elapsed_hours else 0.0
        remaining_hours = round(remaining / products_per_hour, 2) if products_per_hour else None
        estimated_completion = (
            (datetime.now(UTC) + _hours_delta(remaining_hours)).isoformat()
            if remaining_hours is not None
            else None
        )

        data = {
            "batch_info": {
                "id": batch.id,
                "batch_number": batch.batch_number,
                "batch_date": batch.batch_date.isoformat(),
                "is_closed": batch.is_closed,
            },
            "production_stats": {
                "total_products": total_products,
                "aggregated": aggregated,
                "remaining": remaining,
                "aggregation_rate": _percent(aggregated, total_products),
            },
            "timeline": {
                "shift_duration_hours": duration_hours,
                "elapsed_hours": elapsed_hours,
                "products_per_hour": products_per_hour,
                "estimated_completion": estimated_completion,
            },
            "team_performance": {
                "team": batch.team,
                "avg_products_per_hour": products_per_hour,
                "efficiency_score": min(round(_percent(aggregated, total_products), 2), 100.0),
            },
        }
        await self.cache.set_json(cache_key, data, ttl=300)
        return data

    async def _get_or_create_work_center(self, identifier: str, name: str) -> WorkCenter:
        work_center = await self.work_center_repository.get_by_identifier(identifier)
        if work_center is not None:
            return work_center

        work_center = WorkCenter(identifier=identifier, name=name)
        await self.work_center_repository.create(work_center)
        return work_center

    async def invalidate_batch_cache(self, batch_id: int | None = None) -> None:
        await self.cache.delete("dashboard_stats")
        await self.cache.delete_pattern("batches_list:*")
        if batch_id is not None:
            await self.cache.delete(f"batch_detail:{batch_id}", f"batch_statistics:{batch_id}")

    async def _emit_event(self, event_type: str, payload: dict) -> None:
        subscriptions = await self.webhook_repository.list_active_subscriptions_for_event(
            event_type,
        )
        if not subscriptions:
            return

        from src.domain.services.webhook_service import WebhookService

        service = WebhookService(self.session)
        await service.emit_event(event_type, payload)

    def _build_batch_event_payload(self, batch: Batch) -> dict:
        return {
            "id": batch.id,
            "batch_number": batch.batch_number,
            "batch_date": batch.batch_date.isoformat(),
            "nomenclature": batch.nomenclature,
            "work_center": batch.work_center.name,
            "work_center_identifier": batch.work_center.identifier,
        }

    def _build_batch_statistics_payload(self, batch: Batch) -> dict:
        total_products = len(batch.products)
        aggregated = sum(1 for product in batch.products if product.is_aggregated)
        return {
            "total_products": total_products,
            "aggregated": aggregated,
            "aggregation_rate": round((aggregated / total_products) * 100, 2)
            if total_products
            else 0.0,
        }


def _parse_filter_date(value) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _batch_duration_hours(batch: Batch) -> float:
    return round((batch.shift_end - batch.shift_start).total_seconds() / 3600, 2)


def _elapsed_hours(batch: Batch) -> float:
    now = datetime.now(UTC)
    effective_end = min(now, batch.shift_end)
    if effective_end <= batch.shift_start:
        return 0.0
    return round((effective_end - batch.shift_start).total_seconds() / 3600, 2)


def _hours_delta(hours: float) -> timedelta:
    return timedelta(hours=hours)


def _percent(value: int, total: int) -> float:
    return round((value / total) * 100, 2) if total else 0.0
