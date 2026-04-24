from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from src.api.v1.schemas.webhook import (
    WebhookDeliveryListResponse,
    WebhookDeliveryResponse,
    WebhookSubscriptionCreateRequest,
    WebhookSubscriptionListResponse,
    WebhookSubscriptionResponse,
    WebhookSubscriptionUpdateRequest,
)
from src.core.dependencies import get_webhook_service
from src.domain.services import WebhookService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
WebhookServiceDep = Annotated[WebhookService, Depends(get_webhook_service)]


@router.post(
    "",
    response_model=WebhookSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_webhook_subscription(
    payload: WebhookSubscriptionCreateRequest,
    service: WebhookServiceDep,
) -> WebhookSubscriptionResponse:
    subscription = await service.create_subscription(payload)
    return WebhookSubscriptionResponse.model_validate(subscription)


@router.get("", response_model=WebhookSubscriptionListResponse)
async def list_webhook_subscriptions(
    service: WebhookServiceDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> WebhookSubscriptionListResponse:
    subscriptions, total = await service.list_subscriptions(offset=offset, limit=limit)
    return WebhookSubscriptionListResponse(
        items=[
            WebhookSubscriptionResponse.model_validate(subscription)
            for subscription in subscriptions
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{subscription_id}", response_model=WebhookSubscriptionResponse)
async def get_webhook_subscription(
    subscription_id: int,
    service: WebhookServiceDep,
) -> WebhookSubscriptionResponse:
    subscription = await service.get_subscription(subscription_id)
    return WebhookSubscriptionResponse.model_validate(subscription)


@router.patch("/{subscription_id}", response_model=WebhookSubscriptionResponse)
async def update_webhook_subscription(
    subscription_id: int,
    payload: WebhookSubscriptionUpdateRequest,
    service: WebhookServiceDep,
) -> WebhookSubscriptionResponse:
    subscription = await service.update_subscription(subscription_id, payload)
    return WebhookSubscriptionResponse.model_validate(subscription)


@router.delete("/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook_subscription(
    subscription_id: int,
    service: WebhookServiceDep,
) -> Response:
    await service.delete_subscription(subscription_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{subscription_id}/deliveries", response_model=WebhookDeliveryListResponse)
async def list_webhook_deliveries(
    subscription_id: int,
    service: WebhookServiceDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> WebhookDeliveryListResponse:
    deliveries, total = await service.list_deliveries(
        subscription_id=subscription_id,
        offset=offset,
        limit=limit,
    )
    return WebhookDeliveryListResponse(
        items=[WebhookDeliveryResponse.model_validate(delivery) for delivery in deliveries],
        total=total,
        limit=limit,
        offset=offset,
    )
