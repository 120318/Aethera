from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.schemas.domain.action import ActionRecord, ActionTargetType
from app.services.audit.action_service import action_service

router = APIRouter(prefix="/scheduler")


class SchedulerJobHistoryResponse(BaseModel):
    total: int
    items: list[ActionRecord]


@router.get("/jobs/{job_id}/history", response_model=SchedulerJobHistoryResponse)
async def get_scheduler_job_history(
    job_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> SchedulerJobHistoryResponse:
    total, items = action_service.list_actions_page_by_target(
        target_type=ActionTargetType.scheduler_job,
        target_id=job_id,
        limit=limit,
        offset=offset,
    )
    return SchedulerJobHistoryResponse(total=total, items=items)
