from datetime import datetime

from pydantic import Field

from src.api.v1.schemas.common import APIModel


class ProductCreateRequest(APIModel):
    unique_code: str = Field(min_length=1, max_length=255)
    batch_id: int = Field(gt=0)


class ProductResponse(APIModel):
    id: int
    unique_code: str
    batch_id: int
    is_aggregated: bool
    aggregated_at: datetime | None
    created_at: datetime


class ProductBatchItemResponse(APIModel):
    id: int
    unique_code: str
    is_aggregated: bool
    aggregated_at: datetime | None
