"""
Task control API routes (Pause, Resume)
"""
import logging

from fastapi import APIRouter
from pydantic import BaseModel
from app.services.domain.download import download_service

router = APIRouter()
logger = logging.getLogger(__name__)

class TaskControlRequest(BaseModel):
    task_ids: list[str]

class TaskControlResponse(BaseModel):
    results: dict[str, bool]

@router.post("/pause", response_model=TaskControlResponse)
async def pause_tasks(body: TaskControlRequest) -> TaskControlResponse:
    """
    Pause tasks
    """
    results = await download_service.pause_tasks(body.task_ids)
    return TaskControlResponse(results=results)

@router.post("/resume", response_model=TaskControlResponse)
async def resume_tasks(body: TaskControlRequest) -> TaskControlResponse:
    """
    Resume tasks
    """
    results = await download_service.resume_tasks(body.task_ids)
    return TaskControlResponse(results=results)
