from fastapi import APIRouter
from pydantic import BaseModel

from app.schemas.exception.exceptions import RequestParamException, ResourceNotFoundException
from app.schemas.runtime.task_view import TaskViewItem
from app.services.domain.download import download_service
from app.services.application.views.task import task_view_service

router = APIRouter()


class TaskSyncFinishedRequest(BaseModel):
    task_id: str


class TaskSyncFinishedResponse(BaseModel):
    task: TaskViewItem


@router.post("/sync_finished", response_model=TaskSyncFinishedResponse, response_model_exclude_none=True)
async def sync_finished_task(body: TaskSyncFinishedRequest) -> TaskSyncFinishedResponse:
    if not body.task_id:
        raise RequestParamException("task_id", str(body.task_id))

    await download_service.sync_active_task(body.task_id)
    task = await task_view_service.get_task_view(body.task_id)
    if task is None:
        raise ResourceNotFoundException("backendErrors.taskNotFound")
    return TaskSyncFinishedResponse(task=task)
