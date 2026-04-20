from typing import Any, Literal

from pydantic import Field

from src.api.v1.schemas.common import APIModel

TaskStatus = Literal["PENDING", "PROGRESS", "SUCCESS", "FAILURE", "RETRY", "STARTED"]


class TaskAcceptedResponse(APIModel):
    task_id: str
    status: TaskStatus
    message: str


class TaskStatusResponse(APIModel):
    task_id: str
    status: TaskStatus
    result: dict[str, Any] = Field(default_factory=dict)
