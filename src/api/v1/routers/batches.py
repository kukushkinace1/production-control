from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from src.api.v1.schemas.batch import (
    BatchCreateRequest,
    BatchFilterParams,
    BatchListResponse,
    BatchResponse,
    BatchUpdateRequest,
)
from src.core.dependencies import get_batch_service
from src.domain.services import BatchService

router = APIRouter(prefix="/batches", tags=["batches"])
BatchServiceDep = Annotated[BatchService, Depends(get_batch_service)]


@router.post("", response_model=list[BatchResponse], status_code=status.HTTP_201_CREATED)
async def create_batches(
    payload: list[BatchCreateRequest],
    service: BatchServiceDep,
) -> list[BatchResponse]:
    batches = await service.create_batches(payload)
    return [BatchResponse.model_validate(batch) for batch in batches]


@router.get("/{batch_id}", response_model=BatchResponse)
async def get_batch(batch_id: int, service: BatchServiceDep) -> BatchResponse:
    batch = await service.get_batch(batch_id)
    return BatchResponse.model_validate(batch)


@router.patch("/{batch_id}", response_model=BatchResponse)
async def update_batch(
    batch_id: int,
    payload: BatchUpdateRequest,
    service: BatchServiceDep,
) -> BatchResponse:
    batch = await service.update_batch(batch_id, payload)
    return BatchResponse.model_validate(batch)


@router.get("", response_model=BatchListResponse)
async def list_batches(
    service: BatchServiceDep,
    is_closed: bool | None = None,
    batch_number: int | None = None,
    batch_date: str | None = None,
    work_center_id: int | None = None,
    work_center_identifier: str | None = None,
    shift: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> BatchListResponse:
    filters = BatchFilterParams(
        is_closed=is_closed,
        batch_number=batch_number,
        batch_date=batch_date,
        work_center_id=work_center_id,
        work_center_identifier=work_center_identifier,
        shift=shift,
        offset=offset,
        limit=limit,
    )
    batches, total = await service.list_batches(filters)
    return BatchListResponse(
        items=[BatchResponse.model_validate(batch) for batch in batches],
        total=total,
        limit=filters.limit,
        offset=filters.offset,
    )


@router.post("/{batch_id}/aggregate", response_model=BatchResponse)
async def aggregate_batch(batch_id: int, service: BatchServiceDep) -> BatchResponse:
    batch = await service.aggregate_batch_products(batch_id)
    return BatchResponse.model_validate(batch)
