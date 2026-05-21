from fastapi import APIRouter
from pydantic import BaseModel

from app.services.platform.scheduler_runtime_service import scheduler_runtime_service

router = APIRouter(prefix="/scheduler")


class TriggerSchedulerJobResponse(BaseModel):
    success: bool = True


@router.post("/jobs/{job_id}/trigger", response_model=TriggerSchedulerJobResponse)
async def trigger_scheduler_job(job_id: str) -> TriggerSchedulerJobResponse:
    await scheduler_runtime_service.trigger_job(job_id)
    return TriggerSchedulerJobResponse()
