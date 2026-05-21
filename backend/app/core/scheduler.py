"""
High-throughput task scan and maintenance scheduler.

The scheduler only coordinates timing and concurrency; business logic stays in
domain and application services.
"""
import asyncio
import functools
import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from app.core.action_context import action_context
from app.schemas.exception.base import AppException
from app.schemas.domain.action import ActionActor, ActionKind, ActionRecord, ActionSource, ActionStatus, ActionTargetType, ActionTrigger
from app.schemas.domain.action_meta import SchedulerQueuedActionMeta
from app.schemas.runtime.scheduler_runtime import (
    SchedulerJobSource,
    SchedulerJobSourceType,
    SchedulerJobTriggerType,
    SchedulerLatestAction,
    SchedulerRuntimeJobSnapshot,
)
from app.schemas.runtime.cache_runtime import CacheCleanupResult
from app.services.audit.action_catalog import (
    SCHEDULER_JOB_CLEANUP_EXPIRED_SESSIONS,
    SCHEDULER_JOB_CLEANUP_INACTIVE_MANAGED_MEDIA_PROFILES,
    SCHEDULER_JOB_DIRECTORY_INTEGRITY_AUDIT,
    SCHEDULER_JOB_MEDIA_SERVER_SYNC_INCREMENTAL_SWEEP,
    SCHEDULER_JOB_PROCESS_COMPLETED_TASKS,
    SCHEDULER_JOB_SCHEDULE_REFRESH_SWEEP,
    SCHEDULER_JOB_SUBSCRIPTION_SWEEP,
    SCHEDULER_JOB_SYNC_ACTIVE_DOWNLOADS,
)
from app.services.audit.action_service import action_service
from app.services.application.events.dispatch import event_dispatch_service
from app.services.domain.download import download_service
from app.addons.registry import AddonDescriptor, CronSpec, AddonJobSpec, addon_service
from app.services.integration.torrent import torrent_service
from app.services.application.workflows.follow_reminder import follow_reminder_service
from app.services.application.workflows.directory_integrity import directory_integrity_service
from app.services.audit.log_service import log_service
from app.services.audit.event_service import event_service
from app.services.domain.media import media_service
from app.services.application.workflows.media_server_sync.config import media_server_sync_config
from app.services.application.workflows.media_server_sync.service import media_server_sync_service
from app.services.application.workflows.scheduled_transfer.service import scheduled_transfer_command_service
from app.services.config.settings_service import settings_service
from app.services.application.workflows.subscription.run import subscription_run_application_service
from app.services.platform.runtime_cache import runtime_cache
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger("app.scheduler")
SCHEDULER_MISFIRE_GRACE_SECONDS: int | None = None


class TaskScheduler:
    """
    High-throughput task scan and audit scheduler.

    It only schedules work and does not own business logic.
    """

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._active_sync_lock = asyncio.Lock()
        self._addon_job_locks: dict[str, asyncio.Lock] = {}
        self._job_sources: dict[str, SchedulerJobSource] = {}
        self._manual_runners: dict[str, Callable[[ActionTrigger], Awaitable[None]]] = {}
        self._latest_actions: dict[str, SchedulerLatestAction] = {}
        self._addon_job_signatures = {}

    async def _sync_active_downloads(self):
        """Synchronize active download task state."""
        if not self._active_sync_lock.locked():
            async with self._active_sync_lock:
                try:
                    result = await download_service.sync_active_downloads()
                    if result.updated > 0:
                        logger.debug("Active sync completed: %s", result)
                except (AppException, RuntimeError, ValueError, OSError) as e:
                    logger.exception("Active sync failed: %s", e)

    async def _process_completed_tasks(self):
        """Enqueue import commands for completed tasks."""
        try:
            recovered = await download_service.recover_stuck_transferring_tasks()
            if recovered > 0:
                logger.info("Recovered %d stuck transferring task(s)", recovered)
            result = await scheduled_transfer_command_service.enqueue_finished_tasks()
            if result.processed > 0:
                logger.debug("Ingest worker completed: %s", result)
        except (AppException, RuntimeError, ValueError, OSError) as e:
            logger.exception("Ingest worker failed: %s", e)

    async def _run_subscriptions(self):
        """Run the subscription sweep."""
        try:
            await subscription_run_application_service.run_all()
        except (AppException, RuntimeError, ValueError, OSError) as e:
            logger.warning("Subscription sweep failed: %s", e)

    async def _refresh_schedule_cache(self):
        """Refresh managed media profiles and follow reminders."""
        try:
            refreshed = await media_service.refresh_active_profiles()
            if refreshed > 0:
                logger.info("Managed media profile refresh completed: %d media entries", refreshed)
            await follow_reminder_service.run_once(window_days=7)
        except (AppException, RuntimeError, ValueError, OSError) as e:
            logger.warning("Managed media profile refresh/reminder failed: %s", e)

    async def _cleanup_inactive_managed_media_profiles(self):
        """Clean inactive managed media profiles and saved search results."""
        try:
            removed = await media_service.cleanup_inactive_profiles()
            if removed > 0:
                logger.info("Managed media profile cleanup completed: %d inactive entries removed", removed)
            self._cleanup_search_results_cache()
        except (AppException, RuntimeError, ValueError, OSError) as e:
            logger.warning("Managed media profile cleanup failed: %s", e)

    async def _audit_directory_integrity(self):
        """Scan configured library/download directories for database drift."""
        try:
            result = await directory_integrity_service.scan()
            if result.summary.total > 0:
                logger.warning("Directory integrity audit found %d issue(s)", result.summary.total)
        except (AppException, RuntimeError, ValueError, OSError) as e:
            logger.warning("Directory integrity audit failed: %s", e)

    async def _run_media_server_incremental_sync(self):
        """Run incremental media server metadata sync."""
        try:
            await media_server_sync_service.run_incremental_once()
        except (AppException, RuntimeError, ValueError, OSError) as e:
            logger.warning("Media server metadata incremental sync failed: %s", e)

    async def _cleanup_expired_sessions(self):
        """Clean expired sessions, logs, actions, events, and runtime cache."""
        try:
            from app.services.platform.auth_service import auth_service
            count = auth_service.cleanup_expired_sessions()
            if count > 0:
                logger.info("Cleaned up %d expired sessions", count)
            log_service.cleanup_retention()
            action_service.cleanup_retention()
            event_service.cleanup_retention()
            event_dispatch_service.cleanup_retention()
            self._cleanup_runtime_caches()
        except (AppException, RuntimeError, ValueError, OSError) as e:
            logger.warning("Expired data cleanup failed: %s", e)

    def _cleanup_runtime_caches(self) -> None:
        """Clean expired runtime cache and torrent file cache."""
        cache_cfg = settings_service.get_base_system_config().cache
        expired_runtime_entries = runtime_cache.cleanup_expired()
        torrent_result = torrent_service.cleanup_cache(
            max_age_seconds=cache_cfg.torrent_cache_max_age_seconds,
            max_files=cache_cfg.torrent_cache_max_files,
        )
        result = CacheCleanupResult(
            expired_runtime_entries=expired_runtime_entries,
            torrent=torrent_result,
        )
        if (
            result.expired_runtime_entries > 0
            or result.torrent.total_removed > 0
            or result.torrent.failed > 0
        ):
            logger.info(
                "Cache cleanup completed: expired_runtime_entries=%d "
                "torrent_removed_by_age=%d torrent_removed_by_count=%d torrent_failed=%d",
                result.expired_runtime_entries,
                result.torrent.removed_by_age,
                result.torrent.removed_by_count,
                result.torrent.failed,
            )

    def _cleanup_search_results_cache(self) -> None:
        """Clean cached indexer search results."""
        removed = (
            runtime_cache.clear_by_prefix("indexer:latest_media:")
            + runtime_cache.clear_by_prefix("indexer:search:")
            + runtime_cache.clear_by_prefix("indexer:result:")
        )
        if removed > 0:
            logger.info("Search result cache cleanup completed: removed_entries=%d", removed)

    def _register_addon_jobs(self):
        for addon in addon_service.list_addons():
            if not addon_service.is_addon_enabled(addon.name):
                continue
            for job in (addon.scheduled_jobs() or []):
                try:
                    self._add_addon_job(addon, job)
                except (AppException, RuntimeError, ValueError, OSError) as e:
                    logger.warning("Failed to register addon job %s for %s: %s", job.id, addon.name, e)

    def sync_addon_jobs(self) -> None:
        desired_job_ids: set[str] = set()
        for addon in addon_service.list_addons():
            if not addon_service.is_addon_enabled(addon.name):
                continue
            for job in (addon.scheduled_jobs() or []):
                desired_job_ids.add(job.id)
                try:
                    signature = self._addon_job_signature(addon, job)
                    if self.scheduler.get_job(job.id) and self._addon_job_signatures.get(job.id) == signature:
                        continue
                    self._add_addon_job(addon, job)
                except (AppException, RuntimeError, ValueError, OSError) as e:
                    logger.warning("Failed to sync addon job %s for %s: %s", job.id, addon.name, e)

        existing_addon_job_ids = [
            job_id
            for job_id, source in self._job_sources.items()
            if source.source_type == SchedulerJobSourceType.addon
        ]
        for job_id in existing_addon_job_ids:
            if job_id in desired_job_ids:
                continue
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
            self._job_sources.pop(job_id, None)
            self._manual_runners.pop(job_id, None)
            self._addon_job_locks.pop(job_id, None)
            self._addon_job_signatures.pop(job_id, None)
            logger.debug("Removed disabled addon job: id=%s", job_id)

    async def _run_addon_job(
        self,
        addon: AddonDescriptor,
        job: AddonJobSpec,
        trigger_kind: ActionTrigger = ActionTrigger.scheduler,
    ) -> None:
        lock = self._addon_job_locks.setdefault(job.id, asyncio.Lock())
        if lock.locked():
            skipped_action = self._create_scheduler_action(
                job.id,
                job.name,
                SchedulerJobSourceType.addon,
                addon.name,
                trigger=trigger_kind,
            )
            skipped_action = action_service.mark_skipped(skipped_action.id)
            self._record_latest_action(job.id, skipped_action)
            return
        async with lock:
            started_at = time.monotonic()
            action = self._create_scheduler_action(
                job.id,
                job.name,
                SchedulerJobSourceType.addon,
                addon.name,
                trigger=trigger_kind,
            )
            running_action = action_service.mark_running(action.id)
            self._record_latest_action(job.id, running_action)
            try:
                with action_context(action.id):
                    await self._execute_addon_job(addon, job)
                completed_action = action_service.mark_completed(
                    action.id,
                    duration_ms=int((time.monotonic() - started_at) * 1000),
                )
                self._record_latest_action(job.id, completed_action)
            except Exception as e:
                failed_action = action_service.mark_failed(
                    action.id,
                    error=str(e),
                    duration_ms=int((time.monotonic() - started_at) * 1000),
                )
                self._record_latest_action(job.id, failed_action)
                logger.warning("Addon job failed: addon=%s job=%s error=%s", addon.name, job.id, e)

    async def _execute_addon_job(self, addon: AddonDescriptor, job: AddonJobSpec) -> None:
        result = job.handler()
        if asyncio.iscoroutine(result):
            await result

    def _addon_job_signature(self, addon: AddonDescriptor, job: AddonJobSpec):
        return (
            addon.name,
            job.name,
            job.trigger,
            job.interval_seconds,
            job.interval_hours,
            tuple(job.cron.present_items()),
            job.max_instances,
        )

    def _add_addon_job(self, addon: AddonDescriptor, job: AddonJobSpec) -> None:
        if job.trigger == SchedulerJobTriggerType.interval.value:
            seconds = job.interval_seconds
            if seconds is None:
                hours = job.interval_hours
                seconds = int(hours) * 3600 if hours is not None else 3600
            trigger = IntervalTrigger(seconds=max(1, int(seconds)))
        else:
            trigger = CronTrigger(**dict(job.cron.present_items()))

        runner = functools.partial(self._run_addon_job, addon, job)
        self.scheduler.add_job(
            runner,
            trigger=trigger,
            id=job.id,
            name=f"{addon.name}: {job.name}",
            max_instances=job.max_instances,
            misfire_grace_time=SCHEDULER_MISFIRE_GRACE_SECONDS,
            coalesce=True,
            replace_existing=True,
        )
        self._job_sources[job.id] = SchedulerJobSource(
            source_type=SchedulerJobSourceType.addon,
            source_name=addon.name,
            enabled=True,
        )
        self._manual_runners[job.id] = runner
        self._addon_job_signatures[job.id] = self._addon_job_signature(addon, job)
        logger.debug("Registered addon job: addon=%s id=%s trigger=%s", addon.name, job.id, job.trigger)

    async def _run_system_job(
        self,
        func: Callable[[], Awaitable[None] | None],
        job_id: str,
        name: str,
        trigger_kind: ActionTrigger = ActionTrigger.scheduler,
    ) -> None:
        started_at = time.monotonic()
        action = self._create_scheduler_action(
            job_id,
            name,
            SchedulerJobSourceType.system,
            SchedulerJobSourceType.system.value,
            trigger=trigger_kind,
        )
        running_action = action_service.mark_running(action.id)
        self._record_latest_action(job_id, running_action)
        try:
            with action_context(action.id):
                result = func()
                if asyncio.iscoroutine(result):
                    await result
            completed_action = action_service.mark_completed(
                action.id,
                duration_ms=int((time.monotonic() - started_at) * 1000),
            )
            self._record_latest_action(job_id, completed_action)
        except Exception as exc:
            failed_action = action_service.mark_failed(
                action.id,
                error=str(exc),
                duration_ms=int((time.monotonic() - started_at) * 1000),
            )
            self._record_latest_action(job_id, failed_action)
            raise

    def _add_system_job(
        self,
        func: Callable[[], Awaitable[None] | None],
        *,
        trigger,
        job_id: str,
        name: str,
        max_instances: int,
    ) -> None:
        runner = functools.partial(self._run_system_job, func, job_id, name)
        self.scheduler.add_job(
            runner,
            trigger=trigger,
            id=job_id,
            name=name,
            max_instances=max_instances,
            misfire_grace_time=SCHEDULER_MISFIRE_GRACE_SECONDS,
            coalesce=True,
            replace_existing=True,
        )
        self._job_sources[job_id] = SchedulerJobSource(
            source_type=SchedulerJobSourceType.system,
            source_name=SchedulerJobSourceType.system.value,
            enabled=True,
        )
        self._manual_runners[job_id] = runner

    def trigger_job(self, job_id: str) -> bool:
        if job_id not in self._manual_runners:
            return False
        runner = self._manual_runners[job_id]
        asyncio.create_task(runner(ActionTrigger.manual))
        return True

    def _create_scheduler_action(
        self,
        job_id: str,
        job_name: str,
        source_type: SchedulerJobSourceType,
        source_name: str,
        *,
        trigger: ActionTrigger,
    ) -> ActionRecord:
        correlation_id = f"scheduler:{job_id}:{uuid.uuid4()}"
        return action_service.create_action(
            kind=ActionKind.scheduler,
            action_name=job_id,
            status=ActionStatus.queued,
            actor=ActionActor.system,
            trigger=trigger,
            source=ActionSource.scheduler,
            target_type=ActionTargetType.scheduler_job,
            target_id=job_id,
            correlation_id=correlation_id,
            meta=SchedulerQueuedActionMeta(
                job_id=job_id,
                job_name=job_name,
                source_type=source_type,
                source_name=source_name,
            ),
        )

    def _reset_job_sources(self) -> None:
        self._job_sources = {}

    def hydrate_latest_actions(self, items: list[SchedulerRuntimeJobSnapshot]) -> None:
        self._latest_actions = {
            item.id: item.latest_action
            for item in items
            if item.latest_action is not None
        }

    def _record_latest_action(self, job_id: str, action: ActionRecord | None) -> None:
        if action is None:
            return
        latest_ts = action.finished_at or action.started_at or action.ts
        self._latest_actions[job_id] = SchedulerLatestAction(
            ts=latest_ts.isoformat(),
            status=action.status.value,
            message_key=action.message_key,
            message_params=action.message_params,
            error=action.error,
            duration_ms=action.duration_ms,
        )

    def job_source(self, job_id: str) -> SchedulerJobSource:
        if job_id in self._job_sources:
            return self._job_sources[job_id]
        return SchedulerJobSource(
            source_type=SchedulerJobSourceType.unknown,
            source_name=SchedulerJobSourceType.unknown.value,
            enabled=True,
        )

    def list_job_runtime_info(self) -> list[SchedulerRuntimeJobSnapshot]:
        items: list[SchedulerRuntimeJobSnapshot] = []
        for job in self.scheduler.get_jobs():
            source = self.job_source(job.id)
            trigger = job.trigger
            trigger_type = SchedulerJobTriggerType.cron
            interval_seconds: int | None = None
            cron = CronSpec()
            if isinstance(trigger, IntervalTrigger):
                trigger_type = SchedulerJobTriggerType.interval
                interval_seconds = int(trigger.interval.total_seconds())
            elif isinstance(trigger, CronTrigger):
                trigger_type = SchedulerJobTriggerType.cron
                fields = [field for field in trigger.fields if not field.is_default]
                cron = CronSpec.model_validate({field.name: str(field) for field in fields})

            items.append(
                SchedulerRuntimeJobSnapshot(
                    id=job.id,
                    name=job.name,
                    source_type=source.source_type,
                    source_name=source.source_name,
                    enabled=source.enabled,
                    trigger_type=trigger_type,
                    interval_seconds=interval_seconds,
                    cron=cron,
                    next_run_time=job.next_run_time.isoformat() if job.next_run_time else None,
                    max_instances=job.max_instances,
                    latest_action=self._latest_actions.get(job.id),
                )
            )
        return items

    def start(self):
        """Start the scheduler."""
        scheduler_cfg = settings_service.get_scheduler_config()
        self._reset_job_sources()

        self._add_system_job(
            self._sync_active_downloads,
            trigger=IntervalTrigger(seconds=scheduler_cfg.sync_active_downloads_interval_seconds),
            job_id=SCHEDULER_JOB_SYNC_ACTIVE_DOWNLOADS,
            name='Sync Active Downloads',
            max_instances=1,
        )

        self._add_system_job(
            self._process_completed_tasks,
            trigger=IntervalTrigger(seconds=scheduler_cfg.process_completed_tasks_interval_seconds),
            job_id=SCHEDULER_JOB_PROCESS_COMPLETED_TASKS,
            name='Process Completed Tasks',
            max_instances=1,
        )

        self._add_system_job(
            self._run_subscriptions,
            trigger=IntervalTrigger(seconds=scheduler_cfg.subscription_sweep_interval_seconds),
            job_id=SCHEDULER_JOB_SUBSCRIPTION_SWEEP,
            name='Subscription Sweep',
            max_instances=1,
        )

        self._add_system_job(
            self._refresh_schedule_cache,
            trigger=IntervalTrigger(seconds=scheduler_cfg.schedule_refresh_sweep_interval_seconds),
            job_id=SCHEDULER_JOB_SCHEDULE_REFRESH_SWEEP,
            name='Media Profile and Reminder Refresh',
            max_instances=1,
        )

        self._add_system_job(
            self._cleanup_inactive_managed_media_profiles,
            trigger=IntervalTrigger(seconds=scheduler_cfg.cleanup_inactive_managed_media_profiles_interval_seconds),
            job_id=SCHEDULER_JOB_CLEANUP_INACTIVE_MANAGED_MEDIA_PROFILES,
            name='Media Profile Cache Maintenance',
            max_instances=1,
        )

        self._add_system_job(
            self._audit_directory_integrity,
            trigger=IntervalTrigger(seconds=scheduler_cfg.directory_integrity_audit_interval_seconds),
            job_id=SCHEDULER_JOB_DIRECTORY_INTEGRITY_AUDIT,
            name='Directory Integrity Audit',
            max_instances=1,
        )

        self._add_system_job(
            self._run_media_server_incremental_sync,
            trigger=IntervalTrigger(seconds=media_server_sync_config.get_incremental_sync_scheduler_interval_seconds()),
            job_id=SCHEDULER_JOB_MEDIA_SERVER_SYNC_INCREMENTAL_SWEEP,
            name='Media Server Metadata Incremental Sync',
            max_instances=1,
        )

        self._add_system_job(
            self._cleanup_expired_sessions,
            trigger=IntervalTrigger(seconds=scheduler_cfg.cleanup_expired_sessions_interval_seconds),
            job_id=SCHEDULER_JOB_CLEANUP_EXPIRED_SESSIONS,
            name='Expired System Data Cleanup',
            max_instances=1,
        )

        self._register_addon_jobs( )

        self.scheduler.start()
        logger.info("High-performance task scheduler started with three-line architecture")

    def stop(self):
        """Stop the scheduler."""
        self.scheduler.shutdown()
        logger.info("Task scheduler stopped")


task_scheduler = TaskScheduler()
