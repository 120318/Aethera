import asyncio
import logging
import signal
import time

from app.core.logging_config import setup_logging
from app.services.config.settings_service import settings_service
from app.db.migration_guard import assert_database_schema_is_current
from app.core.scheduler import task_scheduler
from app.db.repositories.scheduler_runtime_repository import SchedulerRuntimeRepository
from app.schemas.runtime.scheduler_runtime import SchedulerRuntimeJobSnapshot, SchedulerRuntimeSnapshot
from app.services.audit.action_service import action_service
from app.schemas.domain.action import ActionKind, ActionSource, ActionTargetType
from app.addons.registry import addon_service
from app.services.application.workflows.media_server_sync import register_media_server_sync
from app.services.domain.subscription.repair_service import subscription_repair_service

settings_service.ensure_initialized()
setup_logging()
logger = logging.getLogger("app.scheduler_worker")


class SchedulerWorker:
    def __init__(self) -> None:
        self._stop_event = asyncio.Event()
        self.repo = SchedulerRuntimeRepository()

    def request_stop(self) -> None:
        self._stop_event.set()

    async def run(self) -> None:
        logger.info("Scheduler worker startup")
        assert_database_schema_is_current()
        await subscription_repair_service.repair_missing_media_snapshots()
        addon_service.discover_and_register()
        register_media_server_sync()
        reset_count = action_service.fail_active_actions(
            kinds=[ActionKind.scheduler],
            sources=[ActionSource.scheduler],
            error="Scheduler worker restarted and the job was interrupted",
        )
        if reset_count > 0:
            logger.info("Reset %d interrupted scheduler actions", reset_count)
        current_snapshot = await self.repo.get_snapshot()
        if current_snapshot:
            task_scheduler.hydrate_latest_actions(current_snapshot.items)
        task_scheduler.start()
        self._hydrate_latest_actions_from_history()
        await self._write_runtime_snapshot(running=True)

        try:
            while not self._stop_event.is_set():
                await self._drain_manual_triggers()
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=1)
                except asyncio.TimeoutError:
                    await self._write_runtime_snapshot(running=True)
        finally:
            await self._write_runtime_snapshot(running=False)
            task_scheduler.stop()

        logger.info("Scheduler worker shutdown")

    async def _write_runtime_snapshot(self, running: bool) -> None:
        current_snapshot = await self.repo.get_snapshot()
        if running and task_scheduler.scheduler.running:
            task_scheduler.sync_addon_jobs()
        items = list(task_scheduler.list_job_runtime_info())
        snapshot = SchedulerRuntimeSnapshot(
            running=running and task_scheduler.scheduler.running,
            items=items,
            pending_manual_triggers=list(current_snapshot.pending_manual_triggers) if current_snapshot else [],
            updated_at=time.time(),
        )
        await self.repo.save_snapshot(snapshot)

    async def _drain_manual_triggers(self) -> None:
        pending_job_ids = await self.repo.pop_manual_triggers()
        for job_id in pending_job_ids:
            triggered = task_scheduler.trigger_job(job_id)
            if not triggered:
                logger.warning("Scheduler manual trigger dropped, job not found: %s", job_id)

    def _hydrate_latest_actions_from_history(self) -> None:
        job_ids = [item.id for item in task_scheduler.list_job_runtime_info()]
        if not job_ids:
            return
        latest_actions = action_service.list_latest_actions_by_target(
            target_type=ActionTargetType.scheduler_job,
            target_ids=job_ids,
        )
        for job_id, action in latest_actions.items():
            task_scheduler._record_latest_action(job_id, action)


async def main() -> None:
    worker = SchedulerWorker()
    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, worker.request_stop)
        except NotImplementedError:
            logger.warning("Signal handler unavailable for %s", sig)

    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
