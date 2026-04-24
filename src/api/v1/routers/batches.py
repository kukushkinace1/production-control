from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Query, UploadFile, status

from src.api.v1.schemas.batch import (
    BatchAggregationRequest,
    BatchAggregationResponse,
    BatchAsyncAggregationRequest,
    BatchCreateRequest,
    BatchDetailResponse,
    BatchExportRequest,
    BatchFilterParams,
    BatchListResponse,
    BatchReportRequest,
    BatchResponse,
    BatchStatisticsResponse,
    BatchUpdateRequest,
)
from src.api.v1.schemas.task import TaskAcceptedResponse
from src.core.config import get_settings
from src.core.dependencies import get_batch_service
from src.domain.services import BatchService
from src.storage import MinIOService
from src.tasks.aggregation import aggregate_products_batch
from src.tasks.exports import export_batches_to_file
from src.tasks.imports import import_batches_from_file
from src.tasks.reports import generate_batch_report

router = APIRouter(prefix="/batches", tags=["batches"])
BatchServiceDep = Annotated[BatchService, Depends(get_batch_service)]
BatchImportFile = Annotated[UploadFile, File(...)]


@router.post("", response_model=list[BatchResponse], status_code=status.HTTP_201_CREATED)
async def create_batches(
    payload: list[BatchCreateRequest],
    service: BatchServiceDep,
) -> list[BatchResponse]:
    batches = await service.create_batches(payload)
    return [BatchResponse.model_validate(batch) for batch in batches]


@router.post(
    "/import",
    response_model=TaskAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def import_batches(file: BatchImportFile) -> TaskAcceptedResponse:
    settings = get_settings()
    suffix = Path(file.filename or "batches").suffix.lower()
    object_name = (
        f"batch-imports/{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_"
        f"{uuid4().hex}{suffix}"
    )
    content = await file.read()

    minio_service = MinIOService()
    minio_service.ensure_bucket(settings.minio_imports_bucket)
    minio_service.upload_bytes(
        bucket=settings.minio_imports_bucket,
        object_name=object_name,
        data=content,
        content_type=file.content_type,
    )
    task = import_batches_from_file.delay(
        bucket=settings.minio_imports_bucket,
        object_name=object_name,
        file_name=file.filename or object_name,
    )
    return TaskAcceptedResponse(
        task_id=task.id,
        status="PENDING",
        message="File uploaded, import started",
    )


@router.post(
    "/export",
    response_model=TaskAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def export_batches(payload: BatchExportRequest) -> TaskAcceptedResponse:
    task = export_batches_to_file.delay(
        filters=payload.filters.model_dump(mode="json", exclude_none=True),
        report_format=payload.format,
    )
    return TaskAcceptedResponse(
        task_id=task.id,
        status="PENDING",
        message="Batch export task started",
    )


@router.get("/{batch_id}/statistics", response_model=BatchStatisticsResponse)
async def get_batch_statistics(
    batch_id: int,
    service: BatchServiceDep,
) -> BatchStatisticsResponse:
    return BatchStatisticsResponse.model_validate(await service.get_batch_statistics(batch_id))


@router.get("/{batch_id}", response_model=BatchDetailResponse)
async def get_batch(batch_id: int, service: BatchServiceDep) -> BatchDetailResponse:
    return BatchDetailResponse.model_validate(
        await service.get_batch_detail_response_data(batch_id),
    )


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


@router.post("/{batch_id}/aggregate", response_model=BatchAggregationResponse)
async def aggregate_batch(
    batch_id: int,
    payload: BatchAggregationRequest,
    service: BatchServiceDep,
) -> BatchAggregationResponse:
    return await service.aggregate_batch_products(batch_id, payload)


@router.post(
    "/{batch_id}/aggregate-async",
    response_model=TaskAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def aggregate_batch_async(
    batch_id: int,
    payload: BatchAsyncAggregationRequest,
    service: BatchServiceDep,
) -> TaskAcceptedResponse:
    await service.get_batch(batch_id)
    task = aggregate_products_batch.delay(batch_id=batch_id, unique_codes=payload.unique_codes)
    return TaskAcceptedResponse(
        task_id=task.id,
        status="PENDING",
        message="Aggregation task started",
    )


@router.post(
    "/{batch_id}/reports",
    response_model=TaskAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_batch_report(
    batch_id: int,
    payload: BatchReportRequest,
    service: BatchServiceDep,
) -> TaskAcceptedResponse:
    await service.get_batch(batch_id)
    task = generate_batch_report.delay(batch_id=batch_id, report_format=payload.format)
    return TaskAcceptedResponse(
        task_id=task.id,
        status="PENDING",
        message="Report generation task started",
    )
