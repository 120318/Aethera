from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from app.schemas.domain.command import (
    CommandCreateRequest,
    CommandInitiator,
    CommandRecord,
    CommandStatus,
    CommandTargetType,
    CommandType,
    ProfileRefreshCommandRequestPayload,
    ProfileRefreshCommandRecordPayload,
)
from app.schemas.domain.media import MediaExecutionSnapshot, MediaTarget
from app.schemas.exception import DownloadException
from app.schemas.media_id import MediaID
from app.api.v1.media.profile_refresh import refresh_media_profile
from app.services.application.commands.handlers.profile import ProfileRefreshCommandHandler
from app.services.application.workflows.profile_refresh.service import ProfileRefreshCommandService


def _profile_refresh_command(*, command_id: str, status: CommandStatus, season_number: int | None = None) -> CommandRecord:
    media_id = MediaID.parse("tmdb:movie:1")
    target = MediaTarget(media_id=media_id, season_number=season_number)
    season_part = f":season={season_number}" if season_number else ":season=all"
    return CommandRecord(
        id=command_id,
        type=CommandType.PROFILE_REFRESH,
        status=status,
        message="Sample",
        payload=ProfileRefreshCommandRecordPayload(target=target),
        initiator=CommandInitiator.MANUAL,
        media_id=media_id,
        target=target,
        uniq_key=f"command:{CommandType.PROFILE_REFRESH.value}:{media_id}{season_part}",
        target_type=CommandTargetType.MEDIA,
        target_id=str(media_id),
        created_at=datetime.now(),
    )


@pytest.mark.asyncio
async def test_force_requeue_cancels_existing_queued_profile_refresh(monkeypatch):
    service = ProfileRefreshCommandService()
    media_id = MediaID.parse("tmdb:movie:1")
    existing = _profile_refresh_command(command_id="cmd-queued", status=CommandStatus.QUEUED)
    recreated = _profile_refresh_command(command_id="cmd-new", status=CommandStatus.QUEUED)

    monkeypatch.setattr(
        "app.services.application.workflows.profile_refresh.service.command_service.find_active_command_by_uniq_key",
        AsyncMock(return_value=existing),
    )
    cancel_mock = AsyncMock(return_value=existing)
    monkeypatch.setattr(
        "app.services.application.workflows.profile_refresh.service.command_service.cancel_command",
        cancel_mock,
    )
    create_mock = AsyncMock(return_value=recreated)
    monkeypatch.setattr(
        "app.services.application.workflows.profile_refresh.service.command_service.create_command",
        create_mock,
    )

    result = await service.enqueue(media_id, force_requeue=True)

    assert result.id == "cmd-new"
    cancel_mock.assert_awaited_once_with("cmd-queued")
    create_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_force_requeue_submits_followup_when_existing_profile_refresh_is_running(monkeypatch):
    service = ProfileRefreshCommandService()
    media_id = MediaID.parse("tmdb:movie:1")
    existing = _profile_refresh_command(command_id="cmd-running", status=CommandStatus.RUNNING)
    followup = _profile_refresh_command(command_id="cmd-followup", status=CommandStatus.QUEUED)

    monkeypatch.setattr(
        "app.services.application.workflows.profile_refresh.service.command_service.find_active_command_by_uniq_key",
        AsyncMock(return_value=existing),
    )
    create_followup_mock = AsyncMock(return_value=followup)
    monkeypatch.setattr(
        "app.services.application.workflows.profile_refresh.service.command_service.create_command_with_uniq_key",
        create_followup_mock,
    )

    result = await service.enqueue(media_id, force_requeue=True)

    assert result.id == "cmd-followup"
    create_followup_mock.assert_awaited_once()
    assert create_followup_mock.await_args.kwargs["uniq_key"] == f"command:{CommandType.PROFILE_REFRESH.value}:{media_id}:season=all:followup"


@pytest.mark.asyncio
async def test_force_requeue_falls_back_to_followup_when_cancel_races_into_running(monkeypatch):
    service = ProfileRefreshCommandService()
    media_id = MediaID.parse("tmdb:movie:1")
    queued = _profile_refresh_command(command_id="cmd-queued", status=CommandStatus.QUEUED)
    running = _profile_refresh_command(command_id="cmd-running", status=CommandStatus.RUNNING)
    followup = _profile_refresh_command(command_id="cmd-followup", status=CommandStatus.QUEUED)

    find_mock = AsyncMock(side_effect=[queued, running])
    monkeypatch.setattr(
        "app.services.application.workflows.profile_refresh.service.command_service.find_active_command_by_uniq_key",
        find_mock,
    )
    cancel_mock = AsyncMock(side_effect=DownloadException("text，text"))
    monkeypatch.setattr(
        "app.services.application.workflows.profile_refresh.service.command_service.cancel_command",
        cancel_mock,
    )
    create_followup_mock = AsyncMock(return_value=followup)
    monkeypatch.setattr(
        "app.services.application.workflows.profile_refresh.service.command_service.create_command_with_uniq_key",
        create_followup_mock,
    )

    result = await service.enqueue(media_id, force_requeue=True)

    assert result.id == "cmd-followup"
    cancel_mock.assert_awaited_once_with("cmd-queued")
    assert find_mock.await_count == 2
    create_followup_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_force_requeue_reuses_existing_followup_uniq_key(monkeypatch):
    service = ProfileRefreshCommandService()
    media_id = MediaID.parse("tmdb:movie:1")
    running = _profile_refresh_command(command_id="cmd-running", status=CommandStatus.RUNNING)
    followup = _profile_refresh_command(command_id="cmd-followup", status=CommandStatus.QUEUED)
    followup.uniq_key = f"command:{CommandType.PROFILE_REFRESH.value}:{media_id}:season=all:followup"

    monkeypatch.setattr(
        "app.services.application.workflows.profile_refresh.service.command_service.find_active_command_by_uniq_key",
        AsyncMock(return_value=running),
    )

    async def _create_followup(body, *, uniq_key, source):
        assert uniq_key == f"command:{CommandType.PROFILE_REFRESH.value}:{media_id}:season=all:followup"
        return followup

    create_followup_mock = AsyncMock(side_effect=_create_followup)
    monkeypatch.setattr(
        "app.services.application.workflows.profile_refresh.service.command_service.create_command_with_uniq_key",
        create_followup_mock,
    )

    first = await service.enqueue(media_id, force_requeue=True)
    second = await service.enqueue(media_id, force_requeue=True)

    assert first.id == "cmd-followup"
    assert second.id == "cmd-followup"
    assert create_followup_mock.await_count == 2


@pytest.mark.asyncio
async def test_profile_refresh_api_uses_force_requeue(monkeypatch):
    media_id = MediaID.parse("tmdb:movie:1")
    command = _profile_refresh_command(command_id="cmd-new", status=CommandStatus.QUEUED)
    enqueue_mock = AsyncMock(return_value=command)
    monkeypatch.setattr(
        "app.api.v1.media.profile_refresh.profile_refresh_command_service.enqueue",
        enqueue_mock,
    )

    response = await refresh_media_profile(media_id, season_number=2)

    assert response.command.id == "cmd-new"
    enqueue_mock.assert_awaited_once_with(
        media_id,
        season_number=None,
        initiator=CommandInitiator.MANUAL,
        force_requeue=True,
    )


@pytest.mark.asyncio
async def test_profile_refresh_handler_executes_target_season(monkeypatch):
    media_id = MediaID.parse("tmdb:tv:272476")
    target = MediaTarget(media_id=media_id, season_number=2)
    command = CommandRecord(
        id="cmd-season-refresh",
        type=CommandType.PROFILE_REFRESH,
        status=CommandStatus.RUNNING,
        payload=ProfileRefreshCommandRecordPayload(target=target),
        initiator=CommandInitiator.MANUAL,
        media_id=media_id,
        target=target,
        uniq_key=f"command:{CommandType.PROFILE_REFRESH.value}:{media_id}:season=2",
        target_type=CommandTargetType.MEDIA,
        target_id=str(media_id),
        created_at=datetime.now(),
    )
    refresh_mock = AsyncMock()
    monkeypatch.setattr(
        "app.services.application.commands.handlers.profile.media_service.refresh_profile_safely",
        refresh_mock,
    )

    await ProfileRefreshCommandHandler().execute(command)

    refresh_mock.assert_awaited_once_with(media_id, 2)


@pytest.mark.asyncio
async def test_profile_refresh_build_uses_identity_label_without_media_id_fallback(monkeypatch):
    media_id = MediaID.parse("tmdb:tv:272476")
    snapshot = MediaExecutionSnapshot(
        media_id=media_id,
        season_number=2,
        title="Test Show",
        year=2026,
    )
    resolve_mock = AsyncMock(return_value=snapshot)
    monkeypatch.setattr(
        "app.services.application.commands.handlers.profile.media_service.resolve_execution_snapshot",
        resolve_mock,
    )

    command = await ProfileRefreshCommandHandler().build(
        CommandCreateRequest(
            type=CommandType.PROFILE_REFRESH,
            payload=ProfileRefreshCommandRequestPayload(
                target=MediaTarget(media_id=media_id, season_number=2),
            ),
        )
    )

    assert command.target_label == "Test Show (2026)"
    assert command.target == MediaTarget(media_id=media_id, season_number=2)
    assert command.uniq_key == f"command:{CommandType.PROFILE_REFRESH.value}:{media_id}:season=2"
    resolve_mock.assert_awaited_once_with(media_id, season_number=2)
