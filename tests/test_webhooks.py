import hashlib
import hmac
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from src.main import app
from src.utils.hmac_utils import build_hmac_signature


def make_subscription(subscription_id: int = 1) -> SimpleNamespace:
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=subscription_id,
        url="https://example.com/webhook",
        events=["batch_created", "report_generated"],
        is_active=True,
        retry_count=3,
        timeout=10,
        created_at=now,
        updated_at=now,
    )


def make_delivery(delivery_id: int = 1) -> SimpleNamespace:
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=delivery_id,
        subscription_id=1,
        event_type="batch_created",
        payload={"event": "batch_created", "data": {"id": 1}, "timestamp": now.isoformat()},
        status="pending",
        attempts=0,
        response_status=None,
        response_body=None,
        error_message=None,
        created_at=now,
        delivered_at=None,
    )


def test_build_hmac_signature() -> None:
    payload = b'{"event":"batch_created"}'
    expected = hmac.new(b"secret", payload, hashlib.sha256).hexdigest()

    assert build_hmac_signature(payload, "secret") == f"sha256={expected}"


@pytest.mark.asyncio
async def test_create_webhook_subscription_endpoint(client) -> None:
    from src.core.dependencies import get_webhook_service

    class FakeWebhookService:
        async def create_subscription(self, payload):
            assert str(payload.url) == "https://example.com/webhook"
            assert payload.events == ["batch_created"]
            return make_subscription()

    app.dependency_overrides[get_webhook_service] = lambda: FakeWebhookService()

    response = await client.post(
        "/api/v1/webhooks",
        json={
            "url": "https://example.com/webhook",
            "events": ["batch_created"],
            "secret_key": "secret",
            "retry_count": 3,
            "timeout": 10,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 1
    assert body["events"] == ["batch_created", "report_generated"]


@pytest.mark.asyncio
async def test_list_webhook_deliveries_endpoint(client) -> None:
    from src.core.dependencies import get_webhook_service

    class FakeWebhookService:
        async def list_deliveries(self, *, subscription_id: int, offset: int, limit: int):
            assert subscription_id == 1
            assert offset == 0
            assert limit == 20
            return [make_delivery()], 1

    app.dependency_overrides[get_webhook_service] = lambda: FakeWebhookService()

    response = await client.get("/api/v1/webhooks/1/deliveries")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["status"] == "pending"


@pytest.mark.asyncio
async def test_emit_event_creates_deliveries_and_enqueues(monkeypatch) -> None:
    from src.domain.services import webhook_service as webhook_service_module
    from src.domain.services.webhook_service import WebhookService

    queued: list[int] = []

    class FakeTask:
        def delay(self, delivery_id: int) -> None:
            queued.append(delivery_id)

    class FakeSession:
        async def commit(self) -> None:
            return None

    class FakeRepository:
        def __init__(self, _session) -> None:
            self.next_id = 100

        async def list_active_subscriptions_for_event(self, event_type: str):
            assert event_type == "batch_created"
            return [SimpleNamespace(id=1)]

        async def create_delivery(self, delivery):
            delivery.id = self.next_id
            self.next_id += 1
            return delivery

    monkeypatch.setattr(webhook_service_module, "WebhookRepository", FakeRepository)

    import src.tasks.webhooks as webhook_tasks_module

    monkeypatch.setattr(webhook_tasks_module, "send_webhook_delivery", FakeTask())

    service = WebhookService(FakeSession())
    deliveries = await service.emit_event("batch_created", {"id": 1})

    assert len(deliveries) == 1
    assert deliveries[0].status == "pending"
    assert deliveries[0].payload["event"] == "batch_created"
    assert queued == [100]
