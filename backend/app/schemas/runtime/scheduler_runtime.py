from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.runtime.scheduler_types import SchedulerConfigScope, SchedulerJobSourceType, SchedulerJobTriggerType
from app.addons.registry import CronSpec


class SchedulerJobSource(BaseModel):
    source_type: SchedulerJobSourceType
    source_name: str
    enabled: bool = True


class SchedulerRuntimeJobSnapshot(BaseModel):
    id: str
    name: str
    source_type: SchedulerJobSourceType
    source_name: str
    enabled: bool
    trigger_type: SchedulerJobTriggerType
    interval_seconds: int | None = None
    cron: CronSpec = Field(default_factory=CronSpec)
    next_run_time: str | None = None
    max_instances: int
    latest_action: SchedulerLatestAction | None = None


class SchedulerRuntimeSnapshot(BaseModel):
    id: str = "runtime"
    running: bool = False
    items: list[SchedulerRuntimeJobSnapshot] = Field(default_factory=list)
    pending_manual_triggers: list[str] = Field(default_factory=list)
    updated_at: float = 0


class SchedulerLatestAction(BaseModel):
    ts: str
    status: str
    message_key: str | None = None
    message_params: dict[str, str] = Field(default_factory=dict)
    error: str | None = None
    duration_ms: int | None = None


class SchedulerJobInfo(BaseModel):
    id: str
    name: str
    source_type: SchedulerJobSourceType
    source_name: str
    enabled: bool
    trigger_type: SchedulerJobTriggerType
    interval_seconds: int | None = None
    cron: CronSpec = Field(default_factory=CronSpec)
    next_run_time: str | None = None
    max_instances: int
    latest_action: SchedulerLatestAction | None = None
    config_scope: SchedulerConfigScope
    config_target: str
    editable_in_scheduler: bool = False


class SchedulerJobsSummary(BaseModel):
    running: bool
    total: int
    system_count: int
    addon_count: int


class SchedulerJobsResponse(BaseModel):
    summary: SchedulerJobsSummary
    items: list[SchedulerJobInfo]
