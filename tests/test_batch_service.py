from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.domain.services.batch_service import BatchService


@pytest.mark.asyncio
async def test_aggregate_products_by_codes_marks_products_and_collects_errors() -> None:
    session = AsyncMock()
    service = BatchService(session)
    service.get_batch = AsyncMock(return_value=SimpleNamespace(id=1))

    product_ok = SimpleNamespace(
        unique_code="CODE-OK",
        batch_id=1,
        is_aggregated=False,
        aggregated_at=None,
    )
    product_other_batch = SimpleNamespace(
        unique_code="CODE-OTHER-BATCH",
        batch_id=2,
        is_aggregated=False,
        aggregated_at=None,
    )
    product_already_done = SimpleNamespace(
        unique_code="CODE-DONE",
        batch_id=1,
        is_aggregated=True,
        aggregated_at=datetime.now(UTC),
    )

    service.product_repository.get_by_unique_codes = AsyncMock(
        return_value=[product_ok, product_other_batch, product_already_done]
    )

    response = await service.aggregate_products_by_codes(
        batch_id=1,
        unique_codes=["CODE-OK", "CODE-OTHER-BATCH", "CODE-DONE", "CODE-MISSING"],
    )

    assert response.batch_id == 1
    assert response.total == 4
    assert response.aggregated == 1
    assert response.failed == 3
    assert [error.unique_code for error in response.errors] == [
        "CODE-OTHER-BATCH",
        "CODE-DONE",
        "CODE-MISSING",
    ]
    assert product_ok.is_aggregated is True
    assert product_ok.aggregated_at is not None
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_aggregate_products_by_codes_reports_progress_for_each_code() -> None:
    session = AsyncMock()
    service = BatchService(session)
    service.get_batch = AsyncMock(return_value=SimpleNamespace(id=7))

    products = [
        SimpleNamespace(unique_code="A", batch_id=7, is_aggregated=False, aggregated_at=None),
        SimpleNamespace(unique_code="B", batch_id=7, is_aggregated=False, aggregated_at=None),
        SimpleNamespace(unique_code="C", batch_id=7, is_aggregated=False, aggregated_at=None),
    ]
    service.product_repository.get_by_unique_codes = AsyncMock(return_value=products)

    progress_updates: list[tuple[int, int]] = []

    async def progress_callback(current: int, total: int) -> None:
        progress_updates.append((current, total))

    response = await service.aggregate_products_by_codes(
        batch_id=7,
        unique_codes=["A", "B", "C"],
        progress_callback=progress_callback,
    )

    assert response.aggregated == 3
    assert progress_updates == [(1, 3), (2, 3), (3, 3)]
