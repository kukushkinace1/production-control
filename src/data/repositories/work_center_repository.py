from sqlalchemy import select

from src.data.models import WorkCenter
from src.data.repositories.base_repository import BaseRepository


class WorkCenterRepository(BaseRepository):
    async def get_by_identifier(self, identifier: str) -> WorkCenter | None:
        stmt = select(WorkCenter).where(WorkCenter.identifier == identifier)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, work_center: WorkCenter) -> WorkCenter:
        self.session.add(work_center)
        await self.session.flush()
        return work_center
