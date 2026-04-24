from __future__ import annotations

from src.api.v1.schemas.common import APIModel


class DashboardAnalyticsResponse(APIModel):
    summary: dict
    today: dict
    by_shift: dict
    top_work_centers: list[dict]
    cached_at: str


class CompareBatchesRequest(APIModel):
    batch_ids: list[int]


class CompareBatchesResponse(APIModel):
    comparison: list[dict]
    average: dict
