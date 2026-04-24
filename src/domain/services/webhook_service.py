from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.webhook import (
    WebhookSubscriptionCreateRequest,
    WebhookSubscriptionUpdateRequest,
)
from src.data.models import WebhookDelivery, WebhookSubscription
from src.data.repositories import WebhookRepository
from src.domain.exceptions import NotFoundError


class WebhookService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = WebhookRepository(session)

    async def create_subscription(
        self,
        payload: WebhookSubscriptionCreateRequest,
    ) -> WebhookSubscription:
        subscription = WebhookSubscription(
            url=str(payload.url),
            events=list(payload.events),
            secret_key=payload.secret_key,
            retry_count=payload.retry_count,
            timeout=payload.timeout,
        )
        await self.repository.create_subscription(subscription)
        await self.session.commit()
        return await self.get_subscription(subscription.id)

    async def get_subscription(self, subscription_id: int) -> WebhookSubscription:
        subscription = await self.repository.get_subscription(subscription_id)
        if subscription is None:
            raise NotFoundError(f"Webhook subscription {subscription_id} not found.")
        return subscription

    async def list_subscriptions(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[WebhookSubscription], int]:
        items, total = await self.repository.list_subscriptions(offset=offset, limit=limit)
        return list(items), total

    async def update_subscription(
        self,
        subscription_id: int,
        payload: WebhookSubscriptionUpdateRequest,
    ) -> WebhookSubscription:
        subscription = await self.get_subscription(subscription_id)
        updates = payload.model_dump(exclude_unset=True)
        if "url" in updates and updates["url"] is not None:
            updates["url"] = str(updates["url"])
        for field, value in updates.items():
            setattr(subscription, field, value)
        await self.session.commit()
        return await self.get_subscription(subscription_id)

    async def delete_subscription(self, subscription_id: int) -> None:
        subscription = await self.get_subscription(subscription_id)
        await self.session.delete(subscription)
        await self.session.commit()

    async def list_deliveries(
        self,
        *,
        subscription_id: int,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[WebhookDelivery], int]:
        await self.get_subscription(subscription_id)
        items, total = await self.repository.list_deliveries(
            subscription_id=subscription_id,
            offset=offset,
            limit=limit,
        )
        return list(items), total

    async def emit_event(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> list[WebhookDelivery]:
        subscriptions = await self.repository.list_active_subscriptions_for_event(event_type)
        deliveries: list[WebhookDelivery] = []
        for subscription in subscriptions:
            delivery = WebhookDelivery(
                subscription_id=subscription.id,
                event_type=event_type,
                payload={
                    "event": event_type,
                    "data": payload,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
                status="pending",
            )
            await self.repository.create_delivery(delivery)
            deliveries.append(delivery)

        await self.session.commit()

        if deliveries:
            from src.tasks.webhooks import send_webhook_delivery

            for delivery in deliveries:
                send_webhook_delivery.delay(delivery.id)

        return deliveries

    async def get_delivery(self, delivery_id: int) -> WebhookDelivery:
        delivery = await self.repository.get_delivery(delivery_id)
        if delivery is None:
            raise NotFoundError(f"Webhook delivery {delivery_id} not found.")
        return delivery

    async def mark_delivery_success(
        self,
        delivery_id: int,
        *,
        response_status: int,
        response_body: str,
    ) -> WebhookDelivery:
        delivery = await self.get_delivery(delivery_id)
        delivery.status = "success"
        delivery.attempts += 1
        delivery.response_status = response_status
        delivery.response_body = response_body[:2000]
        delivery.error_message = None
        delivery.delivered_at = datetime.now(UTC)
        await self.session.commit()
        return delivery

    async def mark_delivery_failure(
        self,
        delivery_id: int,
        *,
        error_message: str,
        response_status: int | None = None,
        response_body: str | None = None,
        final: bool,
    ) -> WebhookDelivery:
        delivery = await self.get_delivery(delivery_id)
        delivery.attempts += 1
        delivery.status = "failed" if final else "pending"
        delivery.response_status = response_status
        delivery.response_body = response_body[:2000] if response_body else None
        delivery.error_message = error_message[:2000]
        await self.session.commit()
        return delivery
