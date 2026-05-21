from __future__ import annotations

import time

from app.db.repositories.scheduler_runtime_repository import SchedulerRuntimeRepository
from app.schemas.exception.exceptions import ConfigurationException
from app.schemas.runtime.scheduler_runtime import (
    SchedulerConfigScope,
    SchedulerJobInfo,
    SchedulerJobSourceType,
    SchedulerJobTriggerType,
    SchedulerJobsResponse,
    SchedulerJobsSummary,
)
from app.services.audit.action_catalog import (
    SCHEDULER_JOB_MEDIA_SERVER_SYNC_INCREMENTAL_SWEEP,
    SYSTEM_JOB_CONFIG_FIELDS,
)

SCHEDULER_HEARTBEAT_STALE_SECONDS = 15


class SchedulerRuntimeService:
    def __init__(self) -> None:
        self.repo = SchedulerRuntimeRepository()

    async def list_jobs(self) -> SchedulerJobsResponse:
        snapshot = await self.repo.get_snapshot()
        snapshot_items = snapshot.items if snapshot else []
        items = [
            SchedulerJobInfo(
                id=item.id,
                name=item.name,
                source_type=item.source_type,
                source_name=item.source_name,
                enabled=item.enabled,
                trigger_type=item.trigger_type,
                interval_seconds=item.interval_seconds,
                cron=item.cron,
                next_run_time=item.next_run_time,
                max_instances=item.max_instances,
                latest_action=item.latest_action,
                config_scope=SchedulerConfigScope.addon if item.source_type == SchedulerJobSourceType.addon else SchedulerConfigScope.system,
                config_target=item.source_name if item.source_type == SchedulerJobSourceType.addon else (SYSTEM_JOB_CONFIG_FIELDS[item.id] if item.id in SYSTEM_JOB_CONFIG_FIELDS else ""),
                editable_in_scheduler=item.source_type == SchedulerJobSourceType.system and item.trigger_type == SchedulerJobTriggerType.interval and item.id in SYSTEM_JOB_CONFIG_FIELDS and item.id != SCHEDULER_JOB_MEDIA_SERVER_SYNC_INCREMENTAL_SWEEP,
            )
            for item in snapshot_items
        ]
        heartbeat_fresh = bool(snapshot) and (time.time() - float(snapshot.updated_at or 0) <= SCHEDULER_HEARTBEAT_STALE_SECONDS)
        return SchedulerJobsResponse(
            summary=SchedulerJobsSummary(
                running=bool(snapshot and snapshot.running and heartbeat_fresh),
                total=len(items),
                system_count=sum(1 for item in items if item.source_type == SchedulerJobSourceType.system),
                addon_count=sum(1 for item in items if item.source_type == SchedulerJobSourceType.addon),
            ),
            items=items,
        )

    async def trigger_job(self, job_id: str) -> None:
        snapshot = await self.repo.get_snapshot()
        if snapshot is None or all(item.id != job_id for item in snapshot.items):
            raise ConfigurationException("backendErrors.config.schedulerJobNotFound", params={"id": job_id})
        await self.repo.enqueue_manual_trigger(job_id)


scheduler_runtime_service = SchedulerRuntimeService()
