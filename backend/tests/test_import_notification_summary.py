from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.schemas.config import AddonsConfig
from app.schemas.domain.addon_events import MediaImportCompletedEventMeta
from app.schemas.domain.command import (
    AddonRunCommandRecordPayload, CommandRecord, CommandResult, CommandStatus, CommandType,
)
from app.schemas.domain.event import Event, EventType
from app.schemas.domain.media import MediaIdentity, MediaTarget
from app.schemas.persistence.event_dispatch import EventDispatchDeferred, EventDispatchRecord, EventDispatchStatus
from app.schemas.runtime.import_notification import ImportNotificationMeta
from app.services.application.workflows.notifications import import_summary


def _event(event_id="batch-1"):
    media = MediaIdentity(media_id="tmdb:tv:123", title="Example", year=2026, season_number=1)
    return Event(
        id=event_id,
        type=EventType.MEDIA_IMPORT_COMPLETED,
        media=media,
        task_id="same-task",
        meta=MediaImportCompletedEventMeta(
            task_id="same-task", directory_id="tv", media_id=media.media_id,
            imported_files=[{"destination_path": "/library/Example.S01E01.mkv", "episode_number": 1}],
        ).model_dump_json(),
    )


def _command(event_id="batch-1", status=CommandStatus.SUCCEEDED, result=None):
    target = MediaTarget(media_id="tmdb:tv:123", season_number=1)
    return CommandRecord(
        id=f"danmu-{event_id}", type=CommandType.ADDON_RUN, target=target, media_id=target.media_id,
        target_type="media", target_id=str(target.media_id),
        payload=AddonRunCommandRecordPayload(addon_id="danmu", operation_id="generate", target=target, event_id=event_id),
        status=status, result=result,
    )


@pytest.fixture
def dependencies(monkeypatch):
    config = AddonsConfig()
    config.danmu.enabled = True
    config.danmu.directory_ids = ["tv"]
    dispatches = [EventDispatchRecord(
        id="dispatch-danmu", event_id="batch-1", consumer_name="danmu", status=EventDispatchStatus.SUCCEEDED,
    )]
    commands = [_command(result=CommandResult(result_count=1))]
    monkeypatch.setattr(import_summary, "settings_service", SimpleNamespace(get_addons_config=lambda: config))
    monkeypatch.setattr(import_summary, "event_dispatch_service", SimpleNamespace(list_event_dispatches=AsyncMock(return_value=dispatches)))
    monkeypatch.setattr(import_summary, "command_service", SimpleNamespace(list_addon_commands_for_event=AsyncMock(return_value=commands)))
    monkeypatch.setattr(import_summary, "event_service", SimpleNamespace(list_correlated_events=lambda _: []))
    monkeypatch.setattr(import_summary, "media_server_sync_config", SimpleNamespace(resolve_server_for_directory_id=lambda _: None))
    return config, dispatches, commands


@pytest.mark.asyncio
async def test_import_summary_waits_for_running_plugin_without_blocking_worker(dependencies):
    _, _, commands = dependencies
    commands[0].status = CommandStatus.RUNNING
    with pytest.raises(EventDispatchDeferred):
        await import_summary.import_notification_summary_service.build_notification(_event())


@pytest.mark.asyncio
async def test_import_summary_includes_terminal_plugin_result(dependencies):
    notification = await import_summary.import_notification_summary_service.build_notification(_event())
    meta = ImportNotificationMeta.model_validate_json(notification.meta)
    assert [(step.name, step.status.value) for step in meta.postprocessing] == [("danmu", "completed")]
    assert notification.id == "batch-1"


@pytest.mark.asyncio
async def test_import_summary_no_content_is_skipped_not_failed(dependencies):
    _, _, commands = dependencies
    commands[0].result = CommandResult(skipped_count=1)
    notification = await import_summary.import_notification_summary_service.build_notification(_event())
    assert ImportNotificationMeta.model_validate_json(notification.meta).postprocessing[0].status.value == "skipped"


@pytest.mark.asyncio
async def test_disabled_plugins_and_scrape_do_not_delay_import(dependencies):
    config, dispatches, commands = dependencies
    config.danmu.enabled = False
    commands.clear()
    dispatches[0].status = EventDispatchStatus.QUEUED
    notification = await import_summary.import_notification_summary_service.build_notification(_event())
    assert ImportNotificationMeta.model_validate_json(notification.meta).postprocessing == []


@pytest.mark.asyncio
async def test_import_summary_has_bounded_wait(dependencies):
    _, _, commands = dependencies
    commands[0].status = CommandStatus.RUNNING
    event = _event()
    event.ts = datetime.now() - timedelta(minutes=11)
    notification = await import_summary.import_notification_summary_service.build_notification(event)
    assert ImportNotificationMeta.model_validate_json(notification.meta).postprocessing[0].status.value == "timed_out"


@pytest.mark.asyncio
async def test_import_summary_distinguishes_partial_success(dependencies):
    _, _, commands = dependencies
    commands[0].result = CommandResult(result_count=1, failed_count=1)
    notification = await import_summary.import_notification_summary_service.build_notification(_event())
    assert ImportNotificationMeta.model_validate_json(notification.meta).postprocessing[0].status.value == "partial"


@pytest.mark.asyncio
async def test_import_summary_waits_for_enqueue_handler_before_assuming_skip(dependencies):
    _, dispatches, commands = dependencies
    commands.clear()
    dispatches[0].status = EventDispatchStatus.RUNNING
    with pytest.raises(EventDispatchDeferred):
        await import_summary.import_notification_summary_service.build_notification(_event())


@pytest.mark.asyncio
async def test_import_summary_reads_its_exact_batch_not_task_id(dependencies):
    await import_summary.import_notification_summary_service.build_notification(_event("batch-2"))
    import_summary.command_service.list_addon_commands_for_event.assert_awaited_once_with("batch-2")
    import_summary.event_dispatch_service.list_event_dispatches.assert_awaited_once_with("batch-2")


@pytest.mark.asyncio
async def test_import_summary_failed_dispatch_is_not_reported_as_skip(dependencies):
    _, dispatches, commands = dependencies
    commands.clear()
    dispatches[0].status = EventDispatchStatus.FAILED
    notification = await import_summary.import_notification_summary_service.build_notification(_event())
    assert ImportNotificationMeta.model_validate_json(notification.meta).postprocessing[0].status.value == "failed"


@pytest.mark.asyncio
async def test_scrape_status_is_correlated_with_import_batch(dependencies, monkeypatch):
    config, dispatches, commands = dependencies
    config.danmu.enabled = False
    commands.clear()
    dispatches.append(EventDispatchRecord(
        id="scrape", event_id="batch-1", consumer_name="media_server_sync", status=EventDispatchStatus.SUCCEEDED,
    ))
    monkeypatch.setattr(import_summary, "media_server_sync_config", SimpleNamespace(resolve_server_for_directory_id=lambda _: True))
    monkeypatch.setattr(import_summary, "event_service", SimpleNamespace(list_correlated_events=lambda _: [
        Event(type=EventType.MEDIA_SERVER_SYNC_COMPLETED, correlation_id="batch-1"),
    ]))

    notification = await import_summary.import_notification_summary_service.build_notification(_event())
    assert [(step.name, step.status.value) for step in ImportNotificationMeta.model_validate_json(notification.meta).postprocessing] == [
        ("media_server_sync", "completed"),
    ]


@pytest.mark.asyncio
async def test_persisted_commands_are_selected_by_import_event_not_media():
    import uuid
    from app.db.repositories.command_repository import CommandRepository

    repo = CommandRepository()
    batch_a, batch_b = str(uuid.uuid4()), str(uuid.uuid4())
    command_a, command_b = _command(batch_a), _command(batch_b)
    await repo.insert(command_a)
    await repo.insert(command_b)

    result = await repo.list_addon_commands_by_event_id(batch_a)

    assert [command.id for command in result] == [command_a.id]
