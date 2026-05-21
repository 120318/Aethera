from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.addons.registry import CronSpec, addon_service

router = APIRouter()


class AddonJobInfo(BaseModel):
    id: str
    name: str
    addon: str
    enabled: bool
    trigger: str
    interval_seconds: int | None = None
    interval_hours: int | None = None
    cron: CronSpec = Field(default_factory=CronSpec)
    max_instances: int


class AddonJobListResponse(BaseModel):
    items: list[AddonJobInfo]


@router.get("/jobs", response_model=AddonJobListResponse)
async def list_addon_jobs() -> AddonJobListResponse:
    items: list[AddonJobInfo] = []
    for addon in addon_service.list_addons():
        if not addon.exposed:
            continue
        enabled = addon_service.is_addon_enabled(addon.name)
        for job in (addon.scheduled_jobs() or []):
            items.append(
                AddonJobInfo(
                    id=job.id,
                    name=job.name,
                    addon=addon.name,
                    enabled=enabled,
                    trigger=job.trigger,
                    interval_seconds=job.interval_seconds,
                    interval_hours=job.interval_hours,
                    cron=job.cron,
                    max_instances=job.max_instances,
                )
            )
    return AddonJobListResponse(items=items)
