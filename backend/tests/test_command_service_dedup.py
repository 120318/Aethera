import os
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError
from sqlalchemy import delete

pytestmark = [pytest.mark.drift, pytest.mark.health]

os.environ.setdefault("DATA_PATH", f"/tmp/aethera-test-data-{uuid.uuid4()}")

from app.schemas.domain.command import (
    CommandCreateRequest,
    CommandInitiator,
    CommandRecord,
    CommandStatus,
    CommandTargetType,
    CommandType,
    ProfileRefreshCommandRecordPayload,
    ResourceSearchCommandRecordPayload,
    SubscriptionRunCommandRequestPayload,
    SubscriptionRunCommandRecordPayload,
    TaskCreateCommandRecordPayload,
    TaskTransferCommandRequestPayload,
    TaskDeleteCommandRecordPayload,
    TaskTransferCommandRecordPayload,
)
from app.schemas.constants.event_types import EventTypes
from app.schemas.domain.media import MediaIdentity, MediaTarget
from app.schemas.exception import InvalidRequestException
from app.schemas.media_id import MediaID
from app.db.repositories.command_repository import CommandRepository
from app.db.sql.models import CommandORM
from app.db.sql.session import SessionLocal
from app.services.audit.event_message_i18n import event_message_key, event_message_params
from app.services.application.commands.service import CommandService


def _command(*, command_id: str, uniq_key: str | None) -> CommandRecord:
    media_id = MediaID.parse("tmdb:tv:1")
    return CommandRecord(
        id=command_id,
        type=CommandType.TASK_TRANSFER,
        message="Sample",
        payload=TaskTransferCommandRecordPayload(
            target=MediaTarget(media_id=media_id, season_number=1),
            resolved_task_id="task-1",
        ),
        initiator=CommandInitiator.MANUAL,
        media_id=media_id,
        target=MediaTarget(media_id=media_id, season_number=1),
        uniq_key=uniq_key,
        target_type=CommandTargetType.TASK,
        target_id="task-1",
        created_at=datetime.now(),
    )


def _media_command(command_id: str, command_type: CommandType, *, season_number: int | None = None) -> CommandRecord:
    media_id = MediaID.parse("tmdb:tv:1")
    media = MediaIdentity(media_id=media_id, season_number=season_number, title="Sample", year=2026)
    target = MediaTarget(media_id=media_id, season_number=season_number)
    payload = (
        ResourceSearchCommandRecordPayload(media=media)
        if command_type == CommandType.RESOURCE_SEARCH
        else ProfileRefreshCommandRecordPayload(target=target)
    )
    return CommandRecord(
        id=command_id,
        type=command_type,
        message="Sample",
        payload=payload,
        initiator=CommandInitiator.MANUAL,
        media_id=media_id,
        target=target,
        uniq_key=None,
        target_type=CommandTargetType.MEDIA,
        target_id=str(media_id),
        created_at=datetime.now(),
    )


def _task_create_command(command_id: str, *, season_number: int) -> CommandRecord:
    media_id = MediaID.parse("tmdb:tv:1")
    return CommandRecord(
        id=command_id,
        type=CommandType.TASK_CREATE,
        message="Sample",
        payload=TaskCreateCommandRecordPayload(
            media=MediaIdentity(media_id=media_id, title="Sample", year=2026, season_number=season_number),
            result_id="result-1",
            directory_id="dir-1",
            resource_title="Sample.Release.S01.2160p",
        ),
        initiator=CommandInitiator.MANUAL,
        media_id=media_id,
        target=MediaTarget(media_id=media_id, season_number=season_number),
        uniq_key=None,
        target_type=CommandTargetType.MEDIA,
        target_id=str(media_id),
        created_at=datetime.now(),
    )


def _task_operation_command(command_id: str, command_type: CommandType, *, season_number: int) -> CommandRecord:
    media_id = MediaID.parse("tmdb:tv:1")
    target = MediaTarget(media_id=media_id, season_number=season_number)
    return CommandRecord(
        id=command_id,
        type=command_type,
        message="Sample",
        payload=TaskDeleteCommandRecordPayload(
            target=target,
            resolved_task_id=f"{command_id}-task",
        ),
        initiator=CommandInitiator.MANUAL,
        media_id=media_id,
        target=target,
        uniq_key=None,
        target_type=CommandTargetType.TASK,
        target_id=f"{command_id}-task",
        created_at=datetime.now(),
    )


@pytest.mark.asyncio
async def test_submit_command_reuses_existing_active_command_by_uniq_key(monkeypatch):
    service = CommandService()
    incoming = _command(command_id="cmd-new", uniq_key="command:task.transfer:task-1")
    existing = _command(command_id="cmd-existing", uniq_key="command:task.transfer:task-1")

    monkeypatch.setattr(service.repo, "find_active_by_uniq_key", AsyncMock(return_value=existing))
    insert_mock = AsyncMock()
    monkeypatch.setattr(service.repo, "insert", insert_mock)
    create_action_mock = Mock()
    monkeypatch.setattr(service, "_create_command_action", create_action_mock)

    result = await service._submit_command(incoming, source="api")

    assert result.id == "cmd-existing"
    insert_mock.assert_not_awaited()
    create_action_mock.assert_not_called()


@pytest.mark.asyncio
async def test_submit_command_without_uniq_key_is_enqueued_normally(monkeypatch):
    service = CommandService()
    incoming = _command(command_id="cmd-new", uniq_key=None)

    find_mock = AsyncMock()
    monkeypatch.setattr(service.repo, "find_active_by_uniq_key", find_mock)
    insert_mock = AsyncMock()
    monkeypatch.setattr(service.repo, "insert", insert_mock)
    create_action_mock = Mock()
    monkeypatch.setattr(service, "_create_command_action", create_action_mock)

    result = await service._submit_command(incoming, source="api")

    assert result.id == "cmd-new"
    find_mock.assert_not_awaited()
    insert_mock.assert_awaited_once()
    create_action_mock.assert_called_once_with(incoming, source="api")


@pytest.mark.asyncio
async def test_run_next_queued_command_stores_app_exception_as_error_key(monkeypatch):
    service = CommandService()
    command = _command(command_id="cmd-app-error", uniq_key=None)
    updated = []

    class FakeRegistry:
        async def execute(self, _command):
            raise InvalidRequestException("backendErrors.seasonRequired")

    monkeypatch.setattr(service.repo, "find_next_queued", AsyncMock(return_value=command))
    monkeypatch.setattr(service.repo, "find_by_id", AsyncMock(return_value=None))
    monkeypatch.setattr(service.repo, "update", AsyncMock(side_effect=lambda item, _cond: updated.append(item.model_copy(deep=True)) or True))
    monkeypatch.setattr(service, "_get_registry", lambda: FakeRegistry())
    monkeypatch.setattr(service, "_mark_command_running", lambda _command: None)
    monkeypatch.setattr(service, "_mark_command_failed", lambda _command: None)
    monkeypatch.setattr(service, "_emit_command_failed_event", lambda _command: None)

    result = await service.run_next_queued_command()

    assert result is True
    failed = updated[-1]
    assert failed.status == CommandStatus.FAILED
    assert failed.error is None
    assert failed.error_key == "backendErrors.seasonRequired"
    assert failed.error_params == {}


@pytest.mark.asyncio
async def test_list_media_active_commands_filters_season_scoped_tv_commands(monkeypatch):
    service = CommandService()
    media_id = MediaID.parse("tmdb:tv:1")
    season_two = _media_command("search-s2", CommandType.RESOURCE_SEARCH, season_number=2)
    profile_season_two = _media_command("profile-refresh-s2", CommandType.PROFILE_REFRESH, season_number=2)
    find_mock = AsyncMock(return_value=[season_two, profile_season_two])
    monkeypatch.setattr(service.repo, "find_active_by_media", find_mock)

    commands = await service.list_media_active_commands(media_id, season_number=2)

    find_mock.assert_awaited_once_with(
        str(media_id),
        target_season_number=2,
        command_types=None,
    )
    assert {command.id for command in commands} == {"search-s2", "profile-refresh-s2"}


def test_tv_media_target_requires_season_number():
    with pytest.raises(ValidationError):
        MediaTarget(media_id=MediaID.parse("tmdb:tv:1"))


@pytest.mark.asyncio
async def test_list_media_active_commands_filters_any_payload_with_season_context(monkeypatch):
    service = CommandService()
    media_id = MediaID.parse("tmdb:tv:1")
    task_delete_s2 = _task_operation_command("task-delete-s2", CommandType.TASK_DELETE, season_number=2)
    find_mock = AsyncMock(return_value=[task_delete_s2])
    monkeypatch.setattr(service.repo, "find_active_by_media", find_mock)

    commands = await service.list_media_active_commands(media_id, season_number=2)

    find_mock.assert_awaited_once_with(
        str(media_id),
        target_season_number=2,
        command_types=None,
    )
    assert {command.id for command in commands} == {"task-delete-s2"}


def test_subscription_run_record_payload_preserves_season_number():
    payload = SubscriptionRunCommandRecordPayload(
        target=MediaTarget(media_id=MediaID.parse("tmdb:tv:1"), season_number=2),
    )

    assert payload.target.season_number == 2


def test_subscription_run_request_preserves_season_number():
    request = CommandCreateRequest(
        type=CommandType.SUBSCRIPTION_RUN,
        payload=SubscriptionRunCommandRequestPayload(
            target=MediaTarget(media_id=MediaID.parse("tmdb:tv:1"), season_number=2),
        ),
    )

    assert request.payload.target.season_number == 2


def test_command_create_request_accepts_envelope_payload():
    request = CommandCreateRequest(
        type=CommandType.TASK_TRANSFER,
        payload=TaskTransferCommandRequestPayload(task_id="task-1"),
    )

    assert request.payload.task_id == "task-1"


def test_command_create_request_rejects_legacy_wide_fields():
    with pytest.raises(ValidationError):
        CommandCreateRequest(
            type=CommandType.TASK_TRANSFER,
            task_id="task-1",
        directory_id="dir-1",
)


def test_command_create_request_rejects_unrelated_payload_fields():
    with pytest.raises(ValidationError):
        CommandCreateRequest(
            type=CommandType.TASK_TRANSFER,
            payload={
                "task_id": "task-1",
                "directory_id": "dir-1",
"target": {"media_id": "tmdb:movie:1"},
            },
        )


def test_command_record_restores_target_from_persisted_media_snapshot():
    media_id = MediaID.parse("tmdb:tv:1")
    command = CommandRecord.model_validate({
        "id": "cmd-restored",
        "type": CommandType.TASK_TRANSFER,
        "message": "Sample",
        "payload": {
            "resolved_task_id": "task-1",
            "target": {"media_id": str(media_id), "season_number": 2},
        },
        "initiator": CommandInitiator.MANUAL,
        "media_id": str(media_id),
        "target_season_number": 2,
        "target_type": CommandTargetType.TASK,
        "target_id": "task-1",
        "created_at": datetime.now(),
    })

    assert command.target == MediaTarget(media_id=media_id, season_number=2)


def test_command_record_rejects_persisted_tv_media_snapshot_without_season_number():
    media_id = MediaID.parse("tmdb:tv:1")

    with pytest.raises(ValidationError):
        CommandRecord.model_validate({
            "id": "cmd-restored",
            "type": CommandType.TASK_TRANSFER,
            "message": "Sample",
            "payload": {
                "resolved_task_id": "task-1",
                "target": {"media_id": str(media_id), "season_number": 1},
            },
            "initiator": CommandInitiator.MANUAL,
            "media_id": str(media_id),
            "target_season_number": 0,
            "target_type": CommandTargetType.TASK,
            "target_id": "task-1",
            "created_at": datetime.now(),
        })


@pytest.mark.asyncio
async def test_command_repository_season_filter_does_not_include_unscoped_media_commands():
    media_id = MediaID.parse("tmdb:tv:1")
    valid_payload = TaskTransferCommandRecordPayload(
        target=MediaTarget(media_id=media_id, season_number=2),
        resolved_task_id="task-valid",
    ).model_dump(mode="json")
    invalid_payload = TaskTransferCommandRecordPayload(
        target=MediaTarget(media_id=media_id, season_number=1),
        resolved_task_id="task-unscoped",
    ).model_dump(mode="json")
    now = datetime.now().isoformat()
    with SessionLocal() as session:
        session.add_all([
            CommandORM(
                id="cmd-season-filter-valid",
                type=CommandType.TASK_TRANSFER.value,
                status=CommandStatus.QUEUED.value,
                payload_json=valid_payload,
                initiator=CommandInitiator.MANUAL.value,
                media_id=str(media_id),
                target_season_number=2,
                target_type=CommandTargetType.MEDIA.value,
                target_id=str(media_id),
                created_at=now,
            ),
            CommandORM(
                id="cmd-season-filter-unscoped",
                type=CommandType.TASK_TRANSFER.value,
                status=CommandStatus.QUEUED.value,
                payload_json=invalid_payload,
                initiator=CommandInitiator.MANUAL.value,
                media_id=str(media_id),
                target_season_number=0,
                target_type=CommandTargetType.MEDIA.value,
                target_id=str(media_id),
                created_at=now,
            ),
        ])
        session.commit()

    try:
        commands = await CommandRepository().find_active_filtered(
            target_type=CommandTargetType.MEDIA,
            target_ids=[str(media_id)],
            target_season_number=2,
        )
    finally:
        with SessionLocal() as session:
            session.execute(delete(CommandORM).where(CommandORM.id.in_(["cmd-season-filter-valid", "cmd-season-filter-unscoped"])))
            session.commit()

    assert [command.id for command in commands] == ["cmd-season-filter-valid"]


@pytest.mark.asyncio
async def test_command_repository_preserves_nested_error_params():
    media_id = MediaID.parse("tmdb:tv:1")
    payload = TaskCreateCommandRecordPayload(
        media=MediaIdentity(media_id=media_id, title="Sample", year=2026, season_number=1),
        result_id="result-1",
        directory_id="dir-1",
    ).model_dump(mode="json")
    now = datetime.now().isoformat()
    with SessionLocal() as session:
        session.add(
            CommandORM(
                id="cmd-nested-error-params",
                type=CommandType.TASK_CREATE.value,
                status=CommandStatus.FAILED.value,
                payload_json=payload,
                error_key="backendErrors.downloadTaskCreateFailed",
                error_params_json={
                    "reason_key": "backendErrors.config.directoryNotFound",
                    "reason_params": {"id": "dir-1"},
                },
                initiator=CommandInitiator.MANUAL.value,
                media_id=str(media_id),
                target_season_number=1,
                target_type=CommandTargetType.MEDIA.value,
                target_id=str(media_id),
                created_at=now,
            )
        )
        session.commit()

    try:
        command = await CommandRepository().find_by_id("cmd-nested-error-params")
    finally:
        with SessionLocal() as session:
            session.execute(delete(CommandORM).where(CommandORM.id == "cmd-nested-error-params"))
            session.commit()

    assert command is not None
    assert command.error_params == {
        "reason_key": "backendErrors.config.directoryNotFound",
        "reason_params": {"id": "dir-1"},
    }


def test_task_create_command_failure_emits_download_failed_event(monkeypatch):
    service = CommandService()
    command = _task_create_command("cmd-failed", season_number=1)
    command.status = CommandStatus.FAILED
    command.error = "Sample error"

    emitted = []
    monkeypatch.setattr(
        "app.services.application.commands.service.event_service.emit_media",
        lambda event, meta=None: emitted.append((event, meta)),
    )

    service._emit_command_failed_event(command)

    assert len(emitted) == 1
    event, meta = emitted[0]
    assert event.type == EventTypes.DOWNLOAD_FAILED
    assert event.level.value == "error"
    assert event.media.media_id == command.media_id
    assert event.correlation_id == command.id
    assert event_message_key(event.type) == "eventMessages.downloadFailed"
    params = event_message_params(event, meta)
    assert params["title"] == "Sample"
    assert params["resource_title"] == "Sample.Release.S01.2160p"
    assert "Sample" in params["error"]
    assert meta.command_id == command.id
    assert meta.resource_title == "Sample.Release.S01.2160p"
    assert meta.result_id == "result-1"
    assert meta.directory_id == "dir-1"
