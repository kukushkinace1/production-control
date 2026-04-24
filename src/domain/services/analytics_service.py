from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.cache import CacheService
from src.data.models import Batch
from src.data.repositories import BatchRepository
from src.domain.exceptions import NotFoundError


class AnalyticsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.batch_repository = BatchRepository(session)
        self.cache = CacheService()

    async def get_dashboard(self) -> dict:
        cached = await self.cache.get_json("dashboard_stats")
        if cached is not None:
            return cached

        batches = await self.batch_repository.list_all_for_analytics()
        today = date.today()
        total_batches = len(batches)
        closed_batches = sum(1 for batch in batches if batch.is_closed)
        active_batches = total_batches - closed_batches
        total_products = sum(len(batch.products) for batch in batches)
        aggregated_products = sum(
            1 for batch in batches for product in batch.products if product.is_aggregated
        )
        aggregation_rate = _percent(aggregated_products, total_products)

        by_shift: dict[str, dict] = defaultdict(
            lambda: {"batches": 0, "products": 0, "aggregated": 0},
        )
        by_work_center: dict[str, dict] = {}
        for batch in batches:
            shift_bucket = by_shift[batch.shift]
            shift_bucket["batches"] += 1
            shift_bucket["products"] += len(batch.products)
            shift_bucket["aggregated"] += sum(
                1 for product in batch.products if product.is_aggregated
            )

            wc_key = batch.work_center.identifier
            wc_bucket = by_work_center.setdefault(
                wc_key,
                {
                    "id": batch.work_center.identifier,
                    "name": batch.work_center.name,
                    "batches_count": 0,
                    "products_count": 0,
                    "aggregated_products": 0,
                },
            )
            wc_bucket["batches_count"] += 1
            wc_bucket["products_count"] += len(batch.products)
            wc_bucket["aggregated_products"] += sum(
                1 for product in batch.products if product.is_aggregated
            )

        top_work_centers = sorted(
            (
                {
                    **item,
                    "aggregation_rate": _percent(
                        item["aggregated_products"],
                        item["products_count"],
                    ),
                }
                for item in by_work_center.values()
            ),
            key=lambda item: item["batches_count"],
            reverse=True,
        )[:5]

        result = {
            "summary": {
                "total_batches": total_batches,
                "active_batches": active_batches,
                "closed_batches": closed_batches,
                "total_products": total_products,
                "aggregated_products": aggregated_products,
                "aggregation_rate": aggregation_rate,
            },
            "today": {
                "batches_created": sum(1 for batch in batches if batch.created_at.date() == today),
                "batches_closed": sum(
                    1
                    for batch in batches
                    if batch.closed_at is not None and batch.closed_at.date() == today
                ),
                "products_added": sum(
                    1
                    for batch in batches
                    for product in batch.products
                    if product.created_at.date() == today
                ),
                "products_aggregated": sum(
                    1
                    for batch in batches
                    for product in batch.products
                    if product.aggregated_at is not None
                    and product.aggregated_at.date() == today
                ),
            },
            "by_shift": dict(by_shift),
            "top_work_centers": top_work_centers,
            "cached_at": datetime.now(UTC).isoformat(),
        }
        await self.cache.set_json("dashboard_stats", result, ttl=300)
        return result

    async def compare_batches(self, batch_ids: list[int]) -> dict:
        batches = await self.batch_repository.list_by_ids(batch_ids)
        if len(batches) != len(set(batch_ids)):
            found_ids = {batch.id for batch in batches}
            missing = [batch_id for batch_id in batch_ids if batch_id not in found_ids]
            raise NotFoundError(f"Batches not found: {missing}")

        comparison = [_build_comparison_item(batch) for batch in batches]
        return {
            "comparison": comparison,
            "average": {
                "aggregation_rate": round(
                    sum(item["rate"] for item in comparison) / len(comparison),
                    2,
                )
                if comparison
                else 0.0,
                "products_per_hour": round(
                    sum(item["products_per_hour"] for item in comparison) / len(comparison),
                    2,
                )
                if comparison
                else 0.0,
            },
        }


def _build_comparison_item(batch: Batch) -> dict:
    total_products = len(batch.products)
    aggregated = sum(1 for product in batch.products if product.is_aggregated)
    duration_hours = _duration_hours(batch)
    products_per_hour = round(aggregated / duration_hours, 2) if duration_hours else 0.0
    return {
        "batch_id": batch.id,
        "batch_number": batch.batch_number,
        "total_products": total_products,
        "aggregated": aggregated,
        "rate": _percent(aggregated, total_products),
        "duration_hours": duration_hours,
        "products_per_hour": products_per_hour,
    }


def _duration_hours(batch: Batch) -> float:
    return round((batch.shift_end - batch.shift_start).total_seconds() / 3600, 2)


def _percent(value: int, total: int) -> float:
    return round((value / total) * 100, 2) if total else 0.0
