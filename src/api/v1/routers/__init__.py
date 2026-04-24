from fastapi import APIRouter

from src.api.v1.routers.batches import router as batches_router
from src.api.v1.routers.products import router as products_router
from src.api.v1.routers.tasks import router as tasks_router
from src.api.v1.routers.webhooks import router as webhooks_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(batches_router)
api_v1_router.include_router(products_router)
api_v1_router.include_router(tasks_router)
api_v1_router.include_router(webhooks_router)

__all__ = ["api_v1_router"]
