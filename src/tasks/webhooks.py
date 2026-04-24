from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from celery.utils.log import get_task_logger

from src.celery_app import celery_app
from src.core.database import AsyncSessionLocal
from src.data.repositories import WebhookRepository
from src.domain.services import WebhookService
from src.utils.hmac_utils import build_hmac_signature

logger = get_task_logger(__name__)


async def _send_webhook_delivery_async(delivery_id: int) -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        service = WebhookService(session)
        delivery = await service.get_delivery(delivery_id)
        repository = WebhookRepository(session)
        subscription = await repository.get_subscription(delivery.subscription_id)
        if subscription is None:
            raise ValueError(f"Webhook subscription {delivery.subscription_id} not found.")

        body = json.dumps(
            delivery.payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        signature = build_hmac_signature(body, subscription.secret_key)
        headers = {
            "Content-Type": "application/json",
            "X-Signature": signature,
            "X-Webhook-Event": delivery.event_type,
            "X-Webhook-Delivery": str(delivery.id),
        }

        try:
            async with httpx.AsyncClient(timeout=subscription.timeout) as client:
                response = await client.post(
                    subscription.url,
                    content=body,
                    headers=headers,
                )
            if 200 <= response.status_code < 300:
                await service.mark_delivery_success(
                    delivery_id,
                    response_status=response.status_code,
                    response_body=response.text,
                )
                return {
                    "success": True,
                    "delivery_id": delivery_id,
                    "status": "success",
                    "response_status": response.status_code,
                }

            final = delivery.attempts + 1 >= subscription.retry_count + 1
            await service.mark_delivery_failure(
                delivery_id,
                error_message=f"Webhook returned HTTP {response.status_code}",
                response_status=response.status_code,
                response_body=response.text,
                final=final,
            )
            raise WebhookDeliveryError(
                f"Webhook returned HTTP {response.status_code}",
                final=final,
            )
        except httpx.HTTPError as exc:
            final = delivery.attempts + 1 >= subscription.retry_count + 1
            await service.mark_delivery_failure(
                delivery_id,
                error_message=str(exc),
                final=final,
            )
            raise WebhookDeliveryError(str(exc), final=final) from exc


class WebhookDeliveryError(Exception):
    def __init__(self, message: str, *, final: bool) -> None:
        super().__init__(message)
        self.final = final


@celery_app.task(bind=True, max_retries=10)
def send_webhook_delivery(self, delivery_id: int) -> dict[str, Any]:
    try:
        return asyncio.run(_send_webhook_delivery_async(delivery_id))
    except WebhookDeliveryError as exc:
        if exc.final:
            logger.exception(
                "Webhook delivery failed permanently",
                extra={"delivery_id": delivery_id},
            )
            raise
        countdown = min(2 ** (self.request.retries + 1), 300)
        logger.warning(
            "Webhook delivery failed; retrying",
            extra={"delivery_id": delivery_id, "countdown": countdown},
        )
        raise self.retry(exc=exc, countdown=countdown) from exc
    except Exception as exc:
        logger.exception("Webhook delivery failed", extra={"delivery_id": delivery_id})
        raise self.retry(exc=exc, countdown=min(2 ** (self.request.retries + 1), 300)) from exc
