from typing import Annotated

from fastapi import APIRouter, Depends

from src.api.v1.schemas.analytics import (
    CompareBatchesRequest,
    CompareBatchesResponse,
    DashboardAnalyticsResponse,
)
from src.core.dependencies import get_analytics_service
from src.domain.services import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])
AnalyticsServiceDep = Annotated[AnalyticsService, Depends(get_analytics_service)]


@router.get("/dashboard", response_model=DashboardAnalyticsResponse)
async def get_dashboard_analytics(
    service: AnalyticsServiceDep,
) -> DashboardAnalyticsResponse:
    return DashboardAnalyticsResponse.model_validate(await service.get_dashboard())


@router.post("/compare-batches", response_model=CompareBatchesResponse)
async def compare_batches(
    payload: CompareBatchesRequest,
    service: AnalyticsServiceDep,
) -> CompareBatchesResponse:
    return CompareBatchesResponse.model_validate(
        await service.compare_batches(payload.batch_ids),
    )
