from collections.abc import Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.orm import selectinload

from src.data.models import Batch
from src.data.repositories.base_repository import BaseRepository


class BatchRepository(BaseRepository):
    async def create(self, batch: Batch) -> Batch:
        self.session.add(batch)
        await self.session.flush()
        return batch

    async def get_by_id(self, batch_id: int) -> Batch | None:
        stmt = (
            select(Batch)
            .where(Batch.id == batch_id)
            .options(
                selectinload(Batch.products),
                selectinload(Batch.work_center),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_number_and_date(self, batch_number: int, batch_date) -> Batch | None:
        stmt = select(Batch).where(
            Batch.batch_number == batch_number,
            Batch.batch_date == batch_date,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        is_closed: bool | None = None,
        batch_number: int | None = None,
        batch_date=None,
        work_center_id: int | None = None,
        work_center_identifier: str | None = None,
        shift: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[Sequence[Batch], int]:
        stmt: Select[tuple[Batch]] = (
            select(Batch)
            .options(
                selectinload(Batch.products),
                selectinload(Batch.work_center),
            )
            .order_by(Batch.id.desc())
        )
        count_stmt = select(func.count(Batch.id))

        if is_closed is not None:
            stmt = stmt.where(Batch.is_closed == is_closed)
            count_stmt = count_stmt.where(Batch.is_closed == is_closed)
        if batch_number is not None:
            stmt = stmt.where(Batch.batch_number == batch_number)
            count_stmt = count_stmt.where(Batch.batch_number == batch_number)
        if batch_date is not None:
            stmt = stmt.where(Batch.batch_date == batch_date)
            count_stmt = count_stmt.where(Batch.batch_date == batch_date)
        if work_center_id is not None:
            stmt = stmt.where(Batch.work_center_id == work_center_id)
            count_stmt = count_stmt.where(Batch.work_center_id == work_center_id)
        if shift is not None:
            stmt = stmt.where(Batch.shift == shift)
            count_stmt = count_stmt.where(Batch.shift == shift)
        if work_center_identifier is not None:
            stmt = stmt.where(Batch.work_center.has(identifier=work_center_identifier))
            count_stmt = count_stmt.where(Batch.work_center.has(identifier=work_center_identifier))

        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        items = result.scalars().all()
        total = await self.session.scalar(count_stmt)
        return items, total or 0
