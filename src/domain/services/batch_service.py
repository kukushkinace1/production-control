from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.batch import (
    AggregationError,
    BatchAggregationRequest,
    BatchAggregationResponse,
    BatchCreateRequest,
    BatchFilterParams,
    BatchUpdateRequest,
)
from src.data.models import Batch, WorkCenter
from src.data.repositories import BatchRepository, ProductRepository, WorkCenterRepository
from src.domain.exceptions import ConflictError, NotFoundError


class BatchService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.batch_repository = BatchRepository(session)
        self.product_repository = ProductRepository(session)
        self.work_center_repository = WorkCenterRepository(session)

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

        return [await self.get_batch(batch.id) for batch in created_batches]

    async def get_batch(self, batch_id: int) -> Batch:
        batch = await self.batch_repository.get_by_id(batch_id)
        if batch is None:
            raise NotFoundError(f"Batch {batch_id} not found.")
        return batch

    async def list_batches(self, filters: BatchFilterParams) -> tuple[list[Batch], int]:
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
        return list(items), total

    async def update_batch(self, batch_id: int, payload: BatchUpdateRequest) -> Batch:
        batch = await self.get_batch(batch_id)
        updates = payload.model_dump(exclude_unset=True)

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

        return await self.get_batch(batch_id)

    async def aggregate_batch_products(
        self,
        batch_id: int,
        payload: BatchAggregationRequest,
    ) -> BatchAggregationResponse:
        batch = await self.get_batch(batch_id)
        requested_codes = payload.unique_codes or []
        products = await self.product_repository.get_by_unique_codes(requested_codes)
        products_by_code = {product.unique_code: product for product in products}

        aggregated = 0
        errors: list[AggregationError] = []
        aggregated_at = datetime.now(UTC)

        for unique_code in requested_codes:
            product = products_by_code.get(unique_code)
            if product is None:
                errors.append(AggregationError(unique_code=unique_code, error="Product not found."))
                continue

            if product.batch_id != batch.id:
                errors.append(
                    AggregationError(
                        unique_code=unique_code,
                        error=f"Product does not belong to batch {batch.id}.",
                    )
                )
                continue

            if product.is_aggregated:
                errors.append(
                    AggregationError(
                        unique_code=unique_code,
                        error="Product is already aggregated.",
                    )
                )
                continue

            product.is_aggregated = True
            product.aggregated_at = aggregated_at
            aggregated += 1

        await self.session.commit()

        return BatchAggregationResponse(
            batch_id=batch.id,
            total=len(requested_codes),
            aggregated=aggregated,
            failed=len(errors),
            errors=errors,
        )

    async def _get_or_create_work_center(self, identifier: str, name: str) -> WorkCenter:
        work_center = await self.work_center_repository.get_by_identifier(identifier)
        if work_center is not None:
            return work_center

        work_center = WorkCenter(identifier=identifier, name=name)
        await self.work_center_repository.create(work_center)
        return work_center
