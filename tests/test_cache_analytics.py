from datetime import UTC, datetime

import pytest

from src.main import app


def dashboard_payload() -> dict:
    return {
        "summary": {
            "total_batches": 2,
            "active_batches": 1,
            "closed_batches": 1,
            "total_products": 10,
            "aggregated_products": 7,
            "aggregation_rate": 70.0,
        },
        "today": {
            "batches_created": 1,
            "batches_closed": 0,
            "products_added": 10,
            "products_aggregated": 7,
        },
        "by_shift": {"day": {"batches": 2, "products": 10, "aggregated": 7}},
        "top_work_centers": [
            {
                "id": "WC-1",
                "name": "Line 1",
                "batches_count": 2,
                "products_count": 10,
                "aggregated_products": 7,
                "aggregation_rate": 70.0,
            }
        ],
        "cached_at": datetime.now(UTC).isoformat(),
    }


@pytest.mark.asyncio
async def test_dashboard_endpoint_returns_analytics(client) -> None:
    from src.core.dependencies import get_analytics_service

    class FakeAnalyticsService:
        async def get_dashboard(self):
            return dashboard_payload()

    app.dependency_overrides[get_analytics_service] = lambda: FakeAnalyticsService()

    response = await client.get("/api/v1/analytics/dashboard")

    assert response.status_code == 200
    assert response.json()["summary"]["total_batches"] == 2


@pytest.mark.asyncio
async def test_compare_batches_endpoint_returns_comparison(client) -> None:
    from src.core.dependencies import get_analytics_service

    class FakeAnalyticsService:
        async def compare_batches(self, batch_ids: list[int]):
            assert batch_ids == [1, 2]
            return {
                "comparison": [
                    {
                        "batch_id": 1,
                        "batch_number": 1001,
                        "total_products": 10,
                        "aggregated": 7,
                        "rate": 70.0,
                        "duration_hours": 12.0,
                        "products_per_hour": 0.58,
                    }
                ],
                "average": {"aggregation_rate": 70.0, "products_per_hour": 0.58},
            }

    app.dependency_overrides[get_analytics_service] = lambda: FakeAnalyticsService()

    response = await client.post("/api/v1/analytics/compare-batches", json={"batch_ids": [1, 2]})

    assert response.status_code == 200
    assert response.json()["average"]["aggregation_rate"] == 70.0


@pytest.mark.asyncio
async def test_batch_statistics_endpoint_returns_cached_shape(client) -> None:
    from src.core.dependencies import get_batch_service

    class FakeBatchService:
        async def get_batch_statistics(self, batch_id: int):
            assert batch_id == 1
            return {
                "batch_info": {
                    "id": 1,
                    "batch_number": 1001,
                    "batch_date": "2026-04-24",
                    "is_closed": False,
                },
                "production_stats": {
                    "total_products": 10,
                    "aggregated": 7,
                    "remaining": 3,
                    "aggregation_rate": 70.0,
                },
                "timeline": {
                    "shift_duration_hours": 12.0,
                    "elapsed_hours": 4.0,
                    "products_per_hour": 1.75,
                    "estimated_completion": None,
                },
                "team_performance": {
                    "team": "A",
                    "avg_products_per_hour": 1.75,
                    "efficiency_score": 70.0,
                },
            }

    app.dependency_overrides[get_batch_service] = lambda: FakeBatchService()

    response = await client.get("/api/v1/batches/1/statistics")

    assert response.status_code == 200
    assert response.json()["production_stats"]["remaining"] == 3
