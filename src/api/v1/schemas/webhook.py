from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, HttpUrl, field_validator

from src.api.v1.schemas.common import APIModel, PaginationResponse

WebhookEvent = Literal[
    "batch_created",
    "batch_updated",
    "batch_closed",
    "product_aggregated",
    "report_generated",
    "import_completed",
]
WebhookDeliveryStatus = Literal["pending", "success", "failed"]


class WebhookSubscriptionCreateRequest(APIModel):
    url: HttpUrl
    events: list[WebhookEvent] = Field(min_length=1)
    secret_key: str = Field(min_length=1, max_length=255)
    retry_count: int = Field(default=3, ge=0, le=10)
    timeout: int = Field(default=10, ge=1, le=60)

    @field_validator("events")
    @classmethod
    def deduplicate_events(cls, value: list[WebhookEvent]) -> list[WebhookEvent]:
        return list(dict.fromkeys(value))


class WebhookSubscriptionUpdateRequest(APIModel):
    url: HttpUrl | None = None
    events: list[WebhookEvent] | None = Field(default=None, min_length=1)
    secret_key: str | None = Field(default=None, min_length=1, max_length=255)
    is_active: bool | None = None
    retry_count: int | None = Field(default=None, ge=0, le=10)
    timeout: int | None = Field(default=None, ge=1, le=60)

    @field_validator("events")
    @classmethod
    def deduplicate_events(cls, value: list[WebhookEvent] | None) -> list[WebhookEvent] | None:
        if value is None:
            return None
        return list(dict.fromkeys(value))


class WebhookSubscriptionResponse(APIModel):
    id: int
    url: str
    events: list[str]
    is_active: bool
    retry_count: int
    timeout: int
    created_at: datetime
    updated_at: datetime


class WebhookSubscriptionListResponse(PaginationResponse):
    items: list[WebhookSubscriptionResponse]


class WebhookDeliveryResponse(APIModel):
    id: int
    subscription_id: int
    event_type: str
    payload: dict[str, Any]
    status: WebhookDeliveryStatus
    attempts: int
    response_status: int | None
    response_body: str | None
    error_message: str | None
    created_at: datetime
    delivered_at: datetime | None


class WebhookDeliveryListResponse(PaginationResponse):
    items: list[WebhookDeliveryResponse]
