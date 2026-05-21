from fastapi import APIRouter

from app.schemas.runtime.scheduler_runtime import SchedulerJobsResponse
from app.services.platform.scheduler_runtime_service import scheduler_runtime_service

router = APIRouter(prefix="/scheduler")


@router.get("/jobs", response_model=SchedulerJobsResponse)
async def list_scheduler_jobs() -> SchedulerJobsResponse:
    return await scheduler_runtime_service.list_jobs()
