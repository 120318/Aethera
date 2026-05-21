import os
import uuid
from unittest.mock import AsyncMock, Mock, call

import pytest

os.environ.setdefault("DATA_PATH", f"/tmp/aethera-test-data-{uuid.uuid4()}")

from app.core.scheduler import TaskScheduler
from app.schemas.domain.action import ActionActor, ActionKind, ActionRecord, ActionStatus, ActionTrigger
from app.schemas.runtime.cache_runtime import TorrentCacheCleanupResult


@pytest.mark.asyncio
async def test_run_system_job_records_latest_completed_action(monkeypatch):
    scheduler = TaskScheduler()
    action = ActionRecord(
        id="action-1",
        kind=ActionKind.scheduler,
        action_name="sync_active_downloads",
        status=ActionStatus.queued,
        actor=ActionActor.system,
        trigger=ActionTrigger.scheduler,
        source="scheduler",
        target_type="scheduler_job",
        target_id="sync_active_downloads",
    )
    completed_action = action.model_copy(update={"status": ActionStatus.completed, "message_key": "actionMessages.scheduler.completed"})

    monkeypatch.setattr(scheduler, "_create_scheduler_action", Mock(return_value=action))
    monkeypatch.setattr("app.core.scheduler.action_service.mark_running", Mock(return_value=action))
    monkeypatch.setattr("app.core.scheduler.action_service.mark_completed", Mock(return_value=completed_action))

    await scheduler._run_system_job(AsyncMock(return_value=None), "sync_active_downloads", "Sync Active Downloads")

    latest = scheduler._latest_actions["sync_active_downloads"]
    assert latest.status == "completed"
    assert latest.message_key == "actionMessages.scheduler.completed"


@pytest.mark.asyncio
async def test_run_system_job_records_latest_failed_action(monkeypatch):
    scheduler = TaskScheduler()
    action = ActionRecord(
        id="action-2",
        kind=ActionKind.scheduler,
        action_name="directory_integrity_audit",
        status=ActionStatus.queued,
        actor=ActionActor.system,
        trigger=ActionTrigger.scheduler,
        source="scheduler",
        target_type="scheduler_job",
        target_id="directory_integrity_audit",
    )
    failed_action = action.model_copy(
        update={"status": ActionStatus.failed, "message": "Sample", "error": "boom"}
    )

    monkeypatch.setattr(scheduler, "_create_scheduler_action", Mock(return_value=action))
    monkeypatch.setattr("app.core.scheduler.action_service.mark_running", Mock(return_value=action))
    monkeypatch.setattr("app.core.scheduler.action_service.mark_failed", Mock(return_value=failed_action))

    with pytest.raises(RuntimeError, match="boom"):
        await scheduler._run_system_job(
            AsyncMock(side_effect=RuntimeError("boom")),
            "directory_integrity_audit",
            "Directory Integrity Audit",
        )

    latest = scheduler._latest_actions["directory_integrity_audit"]
    assert latest.status == "failed"
    assert latest.error == "boom"


@pytest.mark.asyncio
async def test_run_system_job_marks_unexpected_exception_failed(monkeypatch):
    scheduler = TaskScheduler()
    action = ActionRecord(
        id="action-unexpected",
        kind=ActionKind.scheduler,
        action_name="cleanup_expired_sessions",
        status=ActionStatus.queued,
        actor=ActionActor.system,
        trigger=ActionTrigger.scheduler,
        source="scheduler",
        target_type="scheduler_job",
        target_id="cleanup_expired_sessions",
    )
    failed_action = action.model_copy(
        update={"status": ActionStatus.failed, "message": "Sample", "error": "bad field"}
    )
    mark_failed = Mock(return_value=failed_action)

    monkeypatch.setattr(scheduler, "_create_scheduler_action", Mock(return_value=action))
    monkeypatch.setattr("app.core.scheduler.action_service.mark_running", Mock(return_value=action))
    monkeypatch.setattr("app.core.scheduler.action_service.mark_failed", mark_failed)

    with pytest.raises(AttributeError, match="bad field"):
        await scheduler._run_system_job(
            AsyncMock(side_effect=AttributeError("bad field")),
            "cleanup_expired_sessions",
            "Sample",
        )

    mark_failed.assert_called_once()
    latest = scheduler._latest_actions["cleanup_expired_sessions"]
    assert latest.status == "failed"
    assert latest.error == "bad field"


def test_trigger_job_returns_true_for_registered_manual_runner(monkeypatch):
    scheduler = TaskScheduler()
    created = []

    async def _runner(trigger):
        return None

    scheduler._manual_runners["sync_active_downloads"] = _runner
    monkeypatch.setattr(
        "app.core.scheduler.asyncio.create_task",
        lambda coro: (created.append(coro), coro.close())[0],
    )

    assert scheduler.trigger_job("sync_active_downloads") is True
    assert len(created) == 1


def test_trigger_job_returns_false_for_unknown_job():
    scheduler = TaskScheduler()

    assert scheduler.trigger_job("unknown-job") is False


def test_create_scheduler_action_accepts_addon_defined_job_id():
    scheduler = TaskScheduler()

    action = scheduler._create_scheduler_action(
        "addon.custom_job",
        "Custom Job",
        source_type="addon",
        source_name="custom-ext",
        trigger=ActionTrigger.scheduler,
    )

    assert action.action_name == "addon.custom_job"
    assert action.target_id == "addon.custom_job"


@pytest.mark.asyncio
async def test_process_completed_tasks_recovers_stuck_transferring_before_enqueue(monkeypatch):
    scheduler = TaskScheduler()
    calls = []

    async def recover_stuck_transferring_tasks():
        calls.append("recover")
        return 2

    async def enqueue_finished_tasks():
        calls.append("enqueue")
        return Mock(processed=0)

    monkeypatch.setattr(
        "app.core.scheduler.download_service.recover_stuck_transferring_tasks",
        recover_stuck_transferring_tasks,
    )
    monkeypatch.setattr(
        "app.core.scheduler.scheduled_transfer_command_service.enqueue_finished_tasks",
        enqueue_finished_tasks,
    )

    await scheduler._process_completed_tasks()

    assert calls == ["recover", "enqueue"]


def test_cleanup_runtime_caches_cleans_runtime_and_torrent_cache(monkeypatch):
    scheduler = TaskScheduler()
    cache_config = Mock(torrent_cache_max_age_seconds=604800, torrent_cache_max_files=2000)
    system_config = Mock(cache=cache_config)
    torrent_result = TorrentCacheCleanupResult(removed_by_age=1, removed_by_count=1)
    cleanup_expired = Mock(return_value=3)
    clear_by_prefix = Mock()
    cleanup_cache = Mock(return_value=torrent_result)

    monkeypatch.setattr("app.core.scheduler.settings_service.get_base_system_config", Mock(return_value=system_config))
    monkeypatch.setattr("app.core.scheduler.runtime_cache.cleanup_expired", cleanup_expired)
    monkeypatch.setattr("app.core.scheduler.runtime_cache.clear_by_prefix", clear_by_prefix)
    monkeypatch.setattr("app.core.scheduler.torrent_service.cleanup_cache", cleanup_cache)

    scheduler._cleanup_runtime_caches()

    cleanup_expired.assert_called_once_with()
    clear_by_prefix.assert_not_called()
    cleanup_cache.assert_called_once_with(max_age_seconds=604800, max_files=2000)


@pytest.mark.asyncio
async def test_cleanup_inactive_managed_media_profiles_clears_search_results(monkeypatch):
    scheduler = TaskScheduler()
    clear_by_prefix = Mock(side_effect=[1, 2, 3])
    cleanup_inactive_profiles = AsyncMock(return_value=0)

    monkeypatch.setattr(
        "app.core.scheduler.media_service.cleanup_inactive_profiles",
        cleanup_inactive_profiles,
    )
    monkeypatch.setattr("app.core.scheduler.runtime_cache.clear_by_prefix", clear_by_prefix)

    await scheduler._cleanup_inactive_managed_media_profiles()

    cleanup_inactive_profiles.assert_awaited_once_with()
    assert clear_by_prefix.call_args_list == [
        call("indexer:latest_media:"),
        call("indexer:search:"),
        call("indexer:result:"),
    ]
