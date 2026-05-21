import os
import uuid
from types import SimpleNamespace

import pytest

os.environ.setdefault("DATA_PATH", f"/tmp/aethera-test-data-{uuid.uuid4()}")

pytestmark = [pytest.mark.health]

from app.core.scheduler import SCHEDULER_MISFIRE_GRACE_SECONDS, TaskScheduler
from app.addons.registry import AddonDescriptor, AddonJobSpec
from app.schemas.config import SchedulerConfig


def test_scheduler_config_defaults_schedule_refresh_to_one_hour():
    assert SchedulerConfig().schedule_refresh_sweep_interval_seconds == 3600
    assert SchedulerConfig().directory_integrity_audit_interval_seconds == 21600


def test_scheduler_start_registers_core_system_jobs(monkeypatch):
    scheduler = TaskScheduler()
    added_jobs = []

    monkeypatch.setattr(
        "app.core.scheduler.settings_service.get_scheduler_config",
        lambda: SimpleNamespace(
            sync_active_downloads_interval_seconds=30,
            process_completed_tasks_interval_seconds=60,
            subscription_sweep_interval_seconds=600,
            schedule_refresh_sweep_interval_seconds=3600,
            cleanup_inactive_managed_media_profiles_interval_seconds=3600,
            directory_integrity_audit_interval_seconds=21600,
            cleanup_expired_sessions_interval_seconds=3600,
        ),
    )
    monkeypatch.setattr(
        "app.core.scheduler.media_server_sync_config.get_incremental_sync_scheduler_interval_seconds",
        lambda: 900,
    )
    monkeypatch.setattr(scheduler, "_register_addon_jobs", lambda: None)
    monkeypatch.setattr(scheduler.scheduler, "start", lambda: None)

    def _capture_add_system_job(func, *, trigger, job_id, name, max_instances):
        added_jobs.append(job_id)

    monkeypatch.setattr(scheduler, "_add_system_job", _capture_add_system_job)

    scheduler.start()

    assert added_jobs == [
        "sync_active_downloads",
        "process_completed_tasks",
        "subscription_sweep",
        "schedule_refresh_sweep",
        "cleanup_inactive_managed_media_profiles",
        "directory_integrity_audit",
        "media_server_sync_incremental_sweep",
        "cleanup_expired_sessions",
    ]


def test_scheduler_syncs_addon_jobs_when_config_changes(monkeypatch):
    scheduler = TaskScheduler()
    job = AddonJobSpec(
        id="danmu.backfill",
        name="Sample",
        trigger="interval",
        interval_seconds=600,
        handler=lambda: None,
    )
    addon = AddonDescriptor(
        name="danmu",
        display_name="Sample",
        scheduled_jobs=lambda: [job],
    )

    monkeypatch.setattr("app.core.scheduler.addon_service.list_addons", lambda: [addon])
    monkeypatch.setattr("app.core.scheduler.addon_service.is_addon_enabled", lambda name: True)

    scheduler.sync_addon_jobs()

    assert scheduler.scheduler.get_job("danmu.backfill") is not None

    monkeypatch.setattr("app.core.scheduler.addon_service.is_addon_enabled", lambda name: False)

    scheduler.sync_addon_jobs()

    assert scheduler.scheduler.get_job("danmu.backfill") is None


def test_scheduler_does_not_replace_unchanged_addon_job(monkeypatch):
    scheduler = TaskScheduler()
    job = AddonJobSpec(
        id="danmu.backfill",
        name="Sample",
        trigger="interval",
        interval_seconds=600,
        handler=lambda: None,
    )
    addon = AddonDescriptor(
        name="danmu",
        display_name="Sample",
        scheduled_jobs=lambda: [job],
    )
    registrations = []
    original_add_addon_job = scheduler._add_addon_job

    def capture_add_addon_job(addon_arg, job_arg):
        registrations.append(job_arg.interval_seconds)
        original_add_addon_job(addon_arg, job_arg)

    monkeypatch.setattr("app.core.scheduler.addon_service.list_addons", lambda: [addon])
    monkeypatch.setattr("app.core.scheduler.addon_service.is_addon_enabled", lambda name: True)
    monkeypatch.setattr(scheduler, "_add_addon_job", capture_add_addon_job)

    scheduler.sync_addon_jobs()
    scheduler.sync_addon_jobs()

    assert registrations == [600]


def test_scheduler_replaces_addon_job_when_schedule_changes(monkeypatch):
    scheduler = TaskScheduler()
    current_job = AddonJobSpec(
        id="danmu.backfill",
        name="Sample",
        trigger="interval",
        interval_seconds=600,
        handler=lambda: None,
    )
    addon = AddonDescriptor(
        name="danmu",
        display_name="Sample",
        scheduled_jobs=lambda: [current_job],
    )
    registrations = []
    original_add_addon_job = scheduler._add_addon_job

    def capture_add_addon_job(addon_arg, job_arg):
        registrations.append(job_arg.interval_seconds)
        original_add_addon_job(addon_arg, job_arg)

    monkeypatch.setattr("app.core.scheduler.addon_service.list_addons", lambda: [addon])
    monkeypatch.setattr("app.core.scheduler.addon_service.is_addon_enabled", lambda name: True)
    monkeypatch.setattr(scheduler, "_add_addon_job", capture_add_addon_job)

    scheduler.sync_addon_jobs()
    current_job.interval_seconds = 1200
    scheduler.sync_addon_jobs()

    assert registrations == [600, 1200]


def test_scheduler_jobs_allow_short_runtime_misfires(monkeypatch):
    scheduler = TaskScheduler()
    calls = []

    def capture_add_job(*args, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(scheduler.scheduler, "add_job", capture_add_job)

    scheduler._add_system_job(
        lambda: None,
        trigger=object(),
        job_id="system.sample",
        name="System Sample",
        max_instances=1,
    )
    scheduler._add_addon_job(
        AddonDescriptor(name="sample"),
        AddonJobSpec(
            id="sample.job",
            name="Sample",
            trigger="interval",
            interval_seconds=60,
            handler=lambda: None,
        ),
    )

    assert [call["misfire_grace_time"] for call in calls] == [
        SCHEDULER_MISFIRE_GRACE_SECONDS,
        SCHEDULER_MISFIRE_GRACE_SECONDS,
    ]
    assert [call["coalesce"] for call in calls] == [True, True]
