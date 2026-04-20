from dataclasses import dataclass, field
from datetime import date, datetime
from types import SimpleNamespace

import pytest

from src.core.dependencies import get_batch_service, get_product_service
from src.main import app


@dataclass
class FakeWorkCenter:
    id: int
    identifier: str
    name: str
    created_at: datetime
    updated_at: datetime


@dataclass
class FakeProduct:
    id: int
    unique_code: str
    batch_id: int
    is_aggregated: bool = False
    aggregated_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FakeBatch:
    id: int
    is_closed: bool
    closed_at: datetime | None
    task_description: str
    work_center_id: int
    shift: str
    team: str
    batch_number: int
    batch_date: date
    nomenclature: str
    ekn_code: str
    shift_start: datetime
    shift_end: datetime
    created_at: datetime
    updated_at: datetime
    work_center: FakeWorkCenter
    products: list[FakeProduct] = field(default_factory=list)


class InMemoryStore:
    def __init__(self) -> None:
        self.batch_seq = 1
        self.product_seq = 1
        self.work_center_seq = 1
        self.batches: dict[int, FakeBatch] = {}
        self.products: dict[str, FakeProduct] = {}
        self.work_centers: dict[str, FakeWorkCenter] = {}


class FakeBatchService:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    async def create_batches(self, payloads):
        created: list[FakeBatch] = []
        for payload in payloads:
            now = datetime.utcnow()
            work_center = self.store.work_centers.get(payload.work_center_identifier)
            if work_center is None:
                work_center = FakeWorkCenter(
                    id=self.store.work_center_seq,
                    identifier=payload.work_center_identifier,
                    name=payload.work_center_name,
                    created_at=now,
                    updated_at=now,
                )
                self.store.work_center_seq += 1
                self.store.work_centers[work_center.identifier] = work_center

            batch = FakeBatch(
                id=self.store.batch_seq,
                is_closed=payload.is_closed,
                closed_at=now if payload.is_closed else None,
                task_description=payload.task_description,
                work_center_id=work_center.id,
                shift=payload.shift,
                team=payload.team,
                batch_number=payload.batch_number,
                batch_date=payload.batch_date,
                nomenclature=payload.nomenclature,
                ekn_code=payload.ekn_code,
                shift_start=payload.shift_start,
                shift_end=payload.shift_end,
                created_at=now,
                updated_at=now,
                work_center=work_center,
            )
            self.store.batch_seq += 1
            self.store.batches[batch.id] = batch
            created.append(batch)
        return created

    async def get_batch(self, batch_id: int):
        batch = self.store.batches.get(batch_id)
        if batch is None:
            raise AssertionError(f"Batch {batch_id} is not seeded in fake store.")
        return batch

    async def aggregate_batch_products(self, batch_id: int, payload):
        batch = await self.get_batch(batch_id)
        aggregated = 0
        errors = []

        for code in payload.unique_codes or []:
            product = self.store.products.get(code)
            if product is None:
                errors.append({"unique_code": code, "error": "Product not found."})
                continue
            if product.batch_id != batch.id:
                errors.append(
                    {
                        "unique_code": code,
                        "error": f"Product does not belong to batch {batch.id}.",
                    }
                )
                continue
            if product.is_aggregated:
                errors.append({"unique_code": code, "error": "Product is already aggregated."})
                continue
            product.is_aggregated = True
            product.aggregated_at = datetime.utcnow()
            aggregated += 1

        return {
            "batch_id": batch.id,
            "total": len(payload.unique_codes or []),
            "aggregated": aggregated,
            "failed": len(errors),
            "errors": errors,
        }


class FakeProductService:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    async def create_product(self, payload):
        product = FakeProduct(
            id=self.store.product_seq,
            unique_code=payload.unique_code,
            batch_id=payload.batch_id,
        )
        self.store.product_seq += 1
        self.store.products[product.unique_code] = product
        self.store.batches[payload.batch_id].products.append(product)
        return product


def override_services(store: InMemoryStore) -> None:
    app.dependency_overrides[get_batch_service] = lambda: FakeBatchService(store)
    app.dependency_overrides[get_product_service] = lambda: FakeProductService(store)


@pytest.mark.asyncio
async def test_create_batch_create_products_and_aggregate_sync(client) -> None:
    store = InMemoryStore()
    override_services(store)

    batch_payload = [
        {
            "is_closed": False,
            "task_description": "Aggregation test batch",
            "work_center_name": "Line 1",
            "shift": "day",
            "team": "A",
            "batch_number": 101,
            "batch_date": "2026-04-18",
            "nomenclature": "Widget",
            "ekn_code": "EKN-101",
            "work_center_identifier": "WC-1",
            "shift_start": "2026-04-18T08:00:00Z",
            "shift_end": "2026-04-18T20:00:00Z",
        }
    ]

    create_batch_response = await client.post("/api/v1/batches", json=batch_payload)
    assert create_batch_response.status_code == 201
    batch_id = create_batch_response.json()[0]["id"]

    for unique_code in ("CODE-1", "CODE-2"):
        create_product_response = await client.post(
            "/api/v1/products",
            json={"unique_code": unique_code, "batch_id": batch_id},
        )
        assert create_product_response.status_code == 201
        assert create_product_response.json()["is_aggregated"] is False

    aggregate_response = await client.post(
        f"/api/v1/batches/{batch_id}/aggregate",
        json={"unique_codes": ["CODE-1", "CODE-2", "CODE-MISSING"]},
    )

    assert aggregate_response.status_code == 200
    assert aggregate_response.json() == {
        "batch_id": batch_id,
        "total": 3,
        "aggregated": 2,
        "failed": 1,
        "errors": [{"unique_code": "CODE-MISSING", "error": "Product not found."}],
    }


@pytest.mark.asyncio
async def test_aggregate_async_returns_task_id(client, monkeypatch) -> None:
    store = InMemoryStore()
    override_services(store)
    store.batches[1] = FakeBatch(
        id=1,
        is_closed=False,
        closed_at=None,
        task_description="Batch for async aggregation",
        work_center_id=1,
        shift="day",
        team="A",
        batch_number=1,
        batch_date=date(2026, 4, 18),
        nomenclature="Widget",
        ekn_code="EKN",
        shift_start=datetime.utcnow(),
        shift_end=datetime.utcnow(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        work_center=FakeWorkCenter(
            id=1,
            identifier="WC-1",
            name="Line 1",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ),
    )

    from src.api.v1.routers import batches as batches_router_module

    monkeypatch.setattr(
        batches_router_module.aggregate_products_batch,
        "delay",
        lambda **_: SimpleNamespace(id="task-123"),
    )

    response = await client.post(
        "/api/v1/batches/1/aggregate-async",
        json={"unique_codes": ["CODE-1", "CODE-2"]},
    )

    assert response.status_code == 202
    assert response.json() == {
        "task_id": "task-123",
        "status": "PENDING",
        "message": "Aggregation task started",
    }


@pytest.mark.asyncio
async def test_aggregate_async_rejects_blank_codes(client) -> None:
    store = InMemoryStore()
    override_services(store)
    store.batches[1] = FakeBatch(
        id=1,
        is_closed=False,
        closed_at=None,
        task_description="Batch for async aggregation",
        work_center_id=1,
        shift="day",
        team="A",
        batch_number=1,
        batch_date=date(2026, 4, 18),
        nomenclature="Widget",
        ekn_code="EKN",
        shift_start=datetime.utcnow(),
        shift_end=datetime.utcnow(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        work_center=FakeWorkCenter(
            id=1,
            identifier="WC-1",
            name="Line 1",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ),
    )

    response = await client.post(
        "/api/v1/batches/1/aggregate-async",
        json={"unique_codes": ["   ", "\t"]},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_task_status_exposes_progress_state(client, monkeypatch) -> None:
    from src.api.v1.routers import tasks as tasks_router_module

    monkeypatch.setattr(
        tasks_router_module,
        "AsyncResult",
        lambda task_id, app: SimpleNamespace(
            id=task_id,
            status="PROGRESS",
            info={"current": 2, "total": 5, "progress": 40},
            failed=lambda: False,
        ),
    )

    response = await client.get("/api/v1/tasks/task-123")

    assert response.status_code == 200
    assert response.json() == {
        "task_id": "task-123",
        "status": "PROGRESS",
        "result": {"current": 2, "total": 5, "progress": 40},
    }


@pytest.mark.asyncio
async def test_get_task_status_wraps_failure_message(client, monkeypatch) -> None:
    from src.api.v1.routers import tasks as tasks_router_module

    monkeypatch.setattr(
        tasks_router_module,
        "AsyncResult",
        lambda task_id, app: SimpleNamespace(
            id=task_id,
            status="FAILURE",
            info=RuntimeError("boom"),
            failed=lambda: True,
        ),
    )

    response = await client.get("/api/v1/tasks/task-err")

    assert response.status_code == 200
    assert response.json() == {
        "task_id": "task-err",
        "status": "FAILURE",
        "result": {"error": "boom"},
    }
