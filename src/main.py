from typing import Annotated

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.routers import api_v1_router
from src.core.config import get_settings
from src.core.database import get_db_session
from src.core.exceptions import register_exception_handlers

settings = get_settings()
DbSession = Annotated[AsyncSession, Depends(get_db_session)]

app = FastAPI(title=settings.app_name, version=settings.app_version)
app.include_router(api_v1_router)
register_exception_handlers(app)


@app.get("/health", tags=["health"])
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/db", tags=["health"])
async def database_healthcheck(session: DbSession) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "ok"}
