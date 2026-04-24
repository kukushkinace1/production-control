from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.orm import selectinload

from src.data.models import WebhookDelivery, WebhookSubscription
from src.data.repositories.base_repository import BaseRepository


class WebhookRepository(BaseRepository):
    async def create_subscription(
        self,
        subscription: WebhookSubscription,
    ) -> WebhookSubscription:
        self.session.add(subscription)
        await self.session.flush()
        return subscription

    async def get_subscription(self, subscription_id: int) -> WebhookSubscription | None:
        stmt = select(WebhookSubscription).where(WebhookSubscription.id == subscription_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_subscriptions(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[Sequence[WebhookSubscription], int]:
        stmt: Select[tuple[WebhookSubscription]] = (
            select(WebhookSubscription)
            .order_by(WebhookSubscription.id.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(func.count(WebhookSubscription.id))
        result = await self.session.execute(stmt)
        total = await self.session.scalar(count_stmt)
        return result.scalars().all(), total or 0

    async def list_active_subscriptions_for_event(
        self,
        event_type: str,
    ) -> list[WebhookSubscription]:
        stmt = select(WebhookSubscription).where(
            WebhookSubscription.is_active.is_(True),
            WebhookSubscription.events.any(event_type),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_delivery(self, delivery: WebhookDelivery) -> WebhookDelivery:
        self.session.add(delivery)
        await self.session.flush()
        return delivery

    async def get_delivery(self, delivery_id: int) -> WebhookDelivery | None:
        stmt = select(WebhookDelivery).where(WebhookDelivery.id == delivery_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_deliveries(
        self,
        *,
        subscription_id: int,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[Sequence[WebhookDelivery], int]:
        stmt: Select[tuple[WebhookDelivery]] = (
            select(WebhookDelivery)
            .where(WebhookDelivery.subscription_id == subscription_id)
            .order_by(WebhookDelivery.id.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(func.count(WebhookDelivery.id)).where(
            WebhookDelivery.subscription_id == subscription_id,
        )
        result = await self.session.execute(stmt)
        total = await self.session.scalar(count_stmt)
        return result.scalars().all(), total or 0

    async def list_retryable_failed_deliveries(self) -> list[WebhookDelivery]:
        stmt = (
            select(WebhookDelivery)
            .join(WebhookDelivery.subscription)
            .where(
                WebhookDelivery.status == "failed",
                WebhookSubscription.is_active.is_(True),
                WebhookDelivery.attempts <= WebhookSubscription.retry_count,
            )
            .options(selectinload(WebhookDelivery.subscription))
            .order_by(WebhookDelivery.id)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
