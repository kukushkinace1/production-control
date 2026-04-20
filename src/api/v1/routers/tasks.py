from celery.result import AsyncResult
from fastapi import APIRouter

from src.api.v1.schemas.task import TaskStatusResponse
from src.celery_app import celery_app

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str) -> TaskStatusResponse:
    task_result = AsyncResult(task_id, app=celery_app)
    result = task_result.info if isinstance(task_result.info, dict) else {}

    if task_result.failed():
        error_message = str(task_result.info) if task_result.info is not None else "Task failed."
        result = {"error": error_message}

    return TaskStatusResponse(
        task_id=task_id,
        status=task_result.status,
        result=result,
    )
