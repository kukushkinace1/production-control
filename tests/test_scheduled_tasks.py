from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from src.celery_app import celery_app
from src.tasks import scheduled as scheduled_module


def test_celery_beat_schedule_contains_maintenance_tasks() -> None:
    schedule = celery_app.conf.beat_schedule

    assert schedule["auto-close-expired-batches"]["task"] == (
        "src.tasks.scheduled.auto_close_expired_batches"
    )
    assert schedule["cleanup-old-files"]["task"] == "src.tasks.scheduled.cleanup_old_files"
    assert schedule["update-cached-statistics"]["task"] == (
        "src.tasks.scheduled.update_cached_statistics"
    )
    assert schedule["retry-failed-webhooks"]["task"] == "src.tasks.scheduled.retry_failed_webhooks"


def test_cleanup_old_files_deletes_from_storage_buckets(monkeypatch) -> None:
    deleted_calls: list[tuple[str, datetime]] = []

    class FakeMinIOService:
        def ensure_bucket(self, bucket: str) -> None:
            return None

        def delete_objects_older_than(self, *, bucket: str, older_than: datetime) -> int:
            deleted_calls.append((bucket, older_than))
            return 2

    monkeypatch.setattr(scheduled_module, "MinIOService", FakeMinIOService)

    result = scheduled_module.cleanup_old_files.run(days=30)

    assert result["success"] is True
    assert result["deleted"] == 6
    assert {bucket for bucket, _ in deleted_calls} == {"reports", "exports", "imports"}
    cutoff_lower_bound = datetime.now(UTC) - timedelta(days=29)
    assert all(older_than < cutoff_lower_bound for _, older_than in deleted_calls)


@pytest.mark.asyncio
async def test_retry_failed_webhooks_enqueues_retryable_deliveries(monkeypatch) -> None:
    queued: list[int] = []

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

    class FakeRepository:
        def __init__(self, _session) -> None:
            return None

        async def list_retryable_failed_deliveries(self):
            return [SimpleNamespace(id=10), SimpleNamespace(id=11)]

    class FakeTask:
        def delay(self, delivery_id: int) -> None:
            queued.append(delivery_id)

    monkeypatch.setattr(scheduled_module, "AsyncSessionLocal", lambda: FakeSession())
    monkeypatch.setattr(scheduled_module, "WebhookRepository", FakeRepository)
    monkeypatch.setattr(scheduled_module, "send_webhook_delivery", FakeTask())

    result = await scheduled_module._retry_failed_webhooks_async()

    assert result == {"success": True, "queued": 2, "delivery_ids": [10, 11]}
    assert queued == [10, 11]
