from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.domain.services import BatchService, ProductService

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


async def get_batch_service(session: DbSession) -> BatchService:
    return BatchService(session)


async def get_product_service(session: DbSession) -> ProductService:
    return ProductService(session)
