"""
textAPItext
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.deps import MediaIDParam, require_tv_season
from app.schemas.media_id import MediaID
from app.schemas.runtime.task_view import TaskViewItem
from app.services.application.views.task import task_view_service

router = APIRouter()


class TaskListResponse(BaseModel):
    tasks: list[TaskViewItem]


@router.get("/list", response_model=TaskListResponse, response_model_exclude_none=True)
async def list(
    media_id: MediaID = Depends(MediaIDParam),
    season_number: Annotated[int | None, Query(gt=0)] = None,
) -> TaskListResponse:
    tasks = await task_view_service.list_media_task_views(
        media_id,
        season_number=require_tv_season(media_id, season_number),
    )
    return TaskListResponse(tasks=tasks)
