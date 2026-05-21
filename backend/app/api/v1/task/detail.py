from fastapi import APIRouter, Query

from app.schemas.exception.exceptions import ResourceNotFoundException
from app.schemas.runtime.task_view import TaskDetailResponseModel
from app.services.application.views.task import task_view_service

router = APIRouter()


@router.get("/detail", response_model=TaskDetailResponseModel, response_model_exclude_none=True)
async def get_task_detail(task_id: str = Query(..., description="Task id")) -> TaskDetailResponseModel:
    detail = await task_view_service.get_task_detail(task_id)
    if detail is None:
        raise ResourceNotFoundException("backendErrors.taskNotFound")
    return detail
