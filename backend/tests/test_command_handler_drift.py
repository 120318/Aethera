import os
import uuid
from unittest.mock import AsyncMock

import pytest

pytestmark = [pytest.mark.drift, pytest.mark.health]

os.environ.setdefault("DATA_PATH", f"/tmp/aethera-test-data-{uuid.uuid4()}")

from app.schemas.media_id import MediaID
from app.schemas.config import DirectoryConfig
from app.schemas.domain.command import (
    CommandCreateRequest,
    CommandInitiator,
    CommandRecord,
    CommandTargetType,
    CommandType,
    DirectoryIntegrityScanCommandRequestPayload,
    DirectoryIntegrityRepairCommandRequestPayload,
    LibraryFileDanmuGenerateCommandRecordPayload,
    LibraryFileDanmuGenerateCommandRequestPayload,
    LibraryFileMediaServerSyncCommandRequestPayload,
    MediaDeleteCommandRequestPayload,
    MediaDeleteCommandRecordPayload,
    ResourceSearchCommandRecordPayload,
    SubscriptionRunCommandRequestPayload,
    TaskDeleteCommandRecordPayload,
)
from app.schemas.domain.library import LibraryFile
from app.schemas.domain.media import MediaExecutionSnapshot, MediaIdentity, MediaTarget
from app.schemas.domain.download import TaskContext, TaskData, TaskStatus
from app.schemas.runtime.directory_integrity import (
    DirectoryIntegrityIssueType,
    DirectoryIntegrityItem,
    DirectoryIntegrityResult,
    DirectoryIntegrityScope,
    DirectoryIntegritySummary,
)
from app.services.application.commands.handlers.directory_integrity import DirectoryIntegrityRepairCommandHandler, DirectoryIntegrityScanCommandHandler
from app.services.application.commands.handlers.download import TaskDeleteCommandHandler
from app.services.application.commands.handlers.library import LibraryFileDanmuGenerateCommandHandler, LibraryFileMediaServerSyncCommandHandler, MediaDeleteCommandHandler
from app.services.application.commands.handlers.search import ResourceSearchCommandHandler
from app.services.application.commands.handlers.subscription import SubscriptionRunCommandHandler


def _task(task_id: str) -> TaskData:
    media_id = MediaID.parse("tmdb:tv:1")
    return TaskData(
        id=task_id,
        torrent_hash=f"hash-{task_id}",
        media_id=media_id,
        status=TaskStatus.COMPLETED,
        context=TaskContext(
            download_url="https://example.com/file.torrent",
            directory_id="dir-1",
            media={"media_id": media_id, "title": "Test Show", "year": 2024},
        ),
    )


@pytest.mark.asyncio
async def test_directory_integrity_scan_command_uses_global_directory_target(monkeypatch):
    latest = DirectoryIntegrityResult(
        scan_id="scan-1",
        scanned_at=1,
        summary=DirectoryIntegritySummary(total=1),
        items=[_directory_integrity_item("item-1")],
    )
    monkeypatch.setattr(
        "app.services.application.commands.handlers.directory_integrity.directory_integrity_service.scan",
        AsyncMock(return_value=latest),
    )
    handler = DirectoryIntegrityScanCommandHandler()

    command = await handler.build(
        CommandCreateRequest(
            type=CommandType.DIRECTORY_INTEGRITY_SCAN,
            initiator=CommandInitiator.MANUAL,
            payload=DirectoryIntegrityScanCommandRequestPayload(),
        )
    )
    result = await handler.execute(command)

    assert command.target_type == CommandTargetType.DIRECTORY
    assert command.target_id == "directory_integrity"
    assert command.uniq_key == "command:directory.integrity_scan:directory_integrity"
    assert command.target_label == "目录完整性扫描"
    assert result.result_count == 1


@pytest.mark.asyncio
async def test_directory_integrity_scan_command_uses_selected_directory_target(monkeypatch):
    latest = DirectoryIntegrityResult(
        scan_id="scan-1",
        scanned_at=1,
        summary=DirectoryIntegritySummary(total=2),
        items=[],
    )
    scan_mock = AsyncMock(return_value=latest)
    monkeypatch.setattr(
        "app.services.application.commands.handlers.directory_integrity.directory_integrity_service.scan",
        scan_mock,
    )
    monkeypatch.setattr(
        "app.services.application.commands.handlers.directory_integrity.settings_service.get_directory_by_id",
        lambda directory_id: DirectoryConfig(id=directory_id, name="Movies"),
    )
    handler = DirectoryIntegrityScanCommandHandler()

    command = await handler.build(
        CommandCreateRequest(
            type=CommandType.DIRECTORY_INTEGRITY_SCAN,
            initiator=CommandInitiator.MANUAL,
            payload=DirectoryIntegrityScanCommandRequestPayload(directory_id="dir-1"),
        )
    )
    result = await handler.execute(command)

    assert command.target_type == CommandTargetType.DIRECTORY
    assert command.target_id == "dir-1"
    assert command.uniq_key == "command:directory.integrity_scan:dir-1"
    assert command.target_label == "Movies"
    assert command.payload.directory_id == "dir-1"
    scan_mock.assert_awaited_once_with("dir-1")
    assert result.result_count == 2


def _task_delete_command() -> CommandRecord:
    media_id = MediaID.parse("tmdb:tv:1")
    return CommandRecord(
        id="cmd-1",
        type=CommandType.TASK_DELETE,
        payload=TaskDeleteCommandRecordPayload(
            resolved_task_id="task-1",
            target=MediaTarget(media_id=media_id, season_number=1),
            delete_files=True,
            delete_library_files=True,
            delete_task=False,
        ),
        initiator=CommandInitiator.MANUAL,
        media_id=media_id,
        target=MediaTarget(media_id=media_id, season_number=1),
        target_type=CommandTargetType.TASK,
        target_id="task-1",
    )


def _media_delete_command() -> CommandRecord:
    media_id = MediaID.parse("tmdb:tv:1")
    return CommandRecord(
        id="cmd-2",
        type=CommandType.MEDIA_DELETE,
        payload=MediaDeleteCommandRecordPayload(
            target=MediaTarget(media_id=media_id, season_number=1),
            mode="tasks_and_library",
            delete_files=True,
            force=True,
        ),
        initiator=CommandInitiator.MANUAL,
        media_id=media_id,
        target=MediaTarget(media_id=media_id, season_number=1),
        target_type=CommandTargetType.MEDIA,
        target_id=str(media_id),
    )


def _resource_search_command() -> CommandRecord:
    media_id = MediaID.parse("tmdb:tv:1")
    return CommandRecord(
        id="cmd-search",
        type=CommandType.RESOURCE_SEARCH,
        payload=ResourceSearchCommandRecordPayload(
            media=MediaIdentity(media_id=media_id, season_number=2, title="Test Show", year=2024),
            site_ids=["site-a"],
        ),
        initiator=CommandInitiator.MANUAL,
        media_id=media_id,
        target=MediaTarget(media_id=media_id, season_number=2),
        target_type=CommandTargetType.MEDIA,
        target_id=str(media_id),
    )


def _library_file(file_id: str = "file-1") -> LibraryFile:
    return LibraryFile(
        id=file_id,
        task_id="task-1",
        directory_id="dir-1",
        media_id=MediaID.parse("tmdb:tv:1"),
        path="/library/Show",
        file_name="Show.S01E01.mkv",
        file_size=100,
        file_index=0,
        created_at=1,
    )


@pytest.mark.asyncio
async def test_directory_integrity_repair_command_targets_single_item(monkeypatch):
    item = _directory_integrity_item("item-1")
    latest = DirectoryIntegrityResult(
        scan_id="scan-1",
        scanned_at=1,
        items=[item],
    )
    monkeypatch.setattr(
        "app.services.application.commands.handlers.directory_integrity.directory_integrity_service.latest",
        AsyncMock(return_value=latest),
    )

    command = await DirectoryIntegrityRepairCommandHandler().build(
        CommandCreateRequest(
            type=CommandType.DIRECTORY_INTEGRITY_REPAIR,
            initiator=CommandInitiator.MANUAL,
            payload=DirectoryIntegrityRepairCommandRequestPayload(
                scan_id="scan-1",
                item_ids=["item-1"],
            ),
        )
    )

    assert command.target_id == "item-1"
    assert command.uniq_key == "command:directory.integrity_repair:item-1"
    assert command.target_label == "未管理的下载项：低智商犯罪 (2026)"


@pytest.mark.asyncio
async def test_directory_integrity_repair_command_uses_distinct_item_uniq_keys(monkeypatch):
    latest = DirectoryIntegrityResult(
        scan_id="scan-1",
        scanned_at=1,
        items=[_directory_integrity_item("item-1"), _directory_integrity_item("item-2")],
    )
    monkeypatch.setattr(
        "app.services.application.commands.handlers.directory_integrity.directory_integrity_service.latest",
        AsyncMock(return_value=latest),
    )
    handler = DirectoryIntegrityRepairCommandHandler()

    first = await handler.build(
        CommandCreateRequest(
            type=CommandType.DIRECTORY_INTEGRITY_REPAIR,
            initiator=CommandInitiator.MANUAL,
            payload=DirectoryIntegrityRepairCommandRequestPayload(scan_id="scan-1", item_ids=["item-1"]),
        )
    )
    second = await handler.build(
        CommandCreateRequest(
            type=CommandType.DIRECTORY_INTEGRITY_REPAIR,
            initiator=CommandInitiator.MANUAL,
            payload=DirectoryIntegrityRepairCommandRequestPayload(scan_id="scan-1", item_ids=["item-2"]),
        )
    )

    assert first.uniq_key != second.uniq_key


def _directory_integrity_item(item_id: str) -> DirectoryIntegrityItem:
    return DirectoryIntegrityItem(
        id=item_id,
        issue_type=DirectoryIntegrityIssueType.unmanaged_download_entry,
        scope=DirectoryIntegrityScope.download,
        directory_id="dir-1",
        directory_name="剧集",
        media_id="tmdb:tv:1",
        media_title="低智商犯罪",
        media_year=2026,
        display_name=f"低智商犯罪 · {item_id}",
        path=f"/data/download/tv/{item_id}",
        relative_path=f"tv/{item_id}",
        repair_action="delete_path",
    )


def _snapshot(media_id: MediaID | None = None, *, season_number: int | None = 1) -> MediaExecutionSnapshot:
    return MediaExecutionSnapshot(
        media_id=media_id or MediaID.parse("tmdb:tv:1"),
        season_number=season_number,
        title="Test Show",
        year=2024,
    )


@pytest.mark.asyncio
async def test_task_delete_handler_refreshes_health_when_library_side_disappears(monkeypatch):
    handler = TaskDeleteCommandHandler()
    command = _task_delete_command()

    cleanup_mock = AsyncMock(return_value=(2, False))
    monkeypatch.setattr(
        "app.services.application.commands.handlers.download.download_service.delete_task_with_cleanup",
        cleanup_mock,
    )

    result = await handler.execute(command)

    assert result.deleted_library_files_count == 2
    assert result.deleted_task is False
    cleanup_mock.assert_awaited_once_with(
        "task-1",
        delete_files=True,
        force=False,
        delete_library_files=True,
    )


@pytest.mark.asyncio
async def test_media_delete_handler_counts_partial_success_when_some_tasks_are_already_gone(monkeypatch):
    handler = MediaDeleteCommandHandler()
    command = _media_delete_command()
    delete_mock = AsyncMock(return_value=(1, 3))

    monkeypatch.setattr(
        "app.services.application.commands.handlers.library.media_resource_deletion_service.delete_media_resources",
        delete_mock,
    )

    result = await handler.execute(command)

    assert result.deleted_library_files_count == 3
    assert result.deleted_tasks_count == 1
    delete_mock.assert_awaited_once_with(
        command.payload.target.media_id,
        season_number=command.payload.target.season_number,
        mode=command.payload.mode,
        delete_files=command.payload.delete_files,
        force=command.payload.force,
    )


@pytest.mark.asyncio
async def test_subscription_run_build_uses_identity_label_without_media_id_fallback(monkeypatch):
    handler = SubscriptionRunCommandHandler()
    media_id = MediaID.parse("tmdb:tv:1")
    resolve_mock = AsyncMock(return_value=_snapshot(media_id, season_number=2))
    monkeypatch.setattr(
        "app.services.application.commands.handlers.subscription.media_service.resolve_execution_snapshot",
        resolve_mock,
    )

    command = await handler.build(
        CommandCreateRequest(
            type=CommandType.SUBSCRIPTION_RUN,
            payload=SubscriptionRunCommandRequestPayload(
                target=MediaTarget(media_id=media_id, season_number=2),
            ),
        )
    )

    assert command.target_label == "Test Show (2024)"
    assert command.target == MediaTarget(media_id=media_id, season_number=2)
    resolve_mock.assert_awaited_once_with(media_id, season_number=2)


@pytest.mark.asyncio
async def test_media_delete_build_uses_identity_label_without_media_id_fallback(monkeypatch):
    handler = MediaDeleteCommandHandler()
    media_id = MediaID.parse("tmdb:tv:1")
    resolve_mock = AsyncMock(return_value=_snapshot(media_id, season_number=1))
    monkeypatch.setattr(
        "app.services.application.commands.handlers.library.media_service.resolve_execution_snapshot",
        resolve_mock,
    )

    command = await handler.build(
        CommandCreateRequest(
            type=CommandType.MEDIA_DELETE,
            payload=MediaDeleteCommandRequestPayload(
                target=MediaTarget(media_id=media_id, season_number=1),
                mode="tasks_and_library",
            ),
        )
    )

    assert command.target_label == "Test Show (2024)"
    assert command.target == MediaTarget(media_id=media_id, season_number=1)
    resolve_mock.assert_awaited_once_with(media_id, season_number=1)


@pytest.mark.asyncio
async def test_resource_search_handler_uses_identity_snapshot_without_detail_fields(monkeypatch):
    handler = ResourceSearchCommandHandler()
    captured = {}

    async def fake_search(query):
        captured["query"] = query
        return []

    monkeypatch.setattr(
        "app.services.application.commands.handlers.search.resource_search_service.search_media",
        fake_search,
    )

    result = await handler.execute(_resource_search_command())

    assert result.result_count == 0
    assert captured["query"].title == "Test Show"
    assert captured["query"].year == 2024
    assert captured["query"].media_type.value == "tv"
    assert captured["query"].season_number == 2
    assert captured["query"].imdbid is None
    assert captured["query"].douban_id is None


@pytest.mark.asyncio
async def test_library_file_media_server_sync_builds_library_file_target(monkeypatch):
    handler = LibraryFileMediaServerSyncCommandHandler()
    media_id = MediaID.parse("tmdb:tv:1")
    monkeypatch.setattr(
        "app.services.application.commands.handlers.library.library_service.find_file_by_id",
        AsyncMock(return_value=_library_file()),
    )
    resolve_mock = AsyncMock(return_value=_snapshot(media_id, season_number=1))
    monkeypatch.setattr(
        "app.services.application.commands.handlers.library.media_service.resolve_execution_snapshot",
        resolve_mock,
    )

    command = await handler.build(
        CommandCreateRequest(
            type=CommandType.LIBRARY_FILE_MEDIA_SERVER_SYNC,
            payload=LibraryFileMediaServerSyncCommandRequestPayload(
                file_id="file-1",
                target=MediaTarget(media_id=media_id, season_number=1),
            ),
        )
    )

    assert command.type == CommandType.LIBRARY_FILE_MEDIA_SERVER_SYNC
    assert command.target_type == CommandTargetType.LIBRARY_FILE
    assert command.target_id == "file-1"
    assert command.media_id == media_id
    assert command.target_label == "Test Show (2024)"
    resolve_mock.assert_awaited_once_with(media_id, season_number=1)


@pytest.mark.asyncio
async def test_library_file_danmu_generate_build_uses_identity_label_without_media_id_fallback(monkeypatch):
    handler = LibraryFileDanmuGenerateCommandHandler()
    media_id = MediaID.parse("tmdb:tv:1")
    monkeypatch.setattr(
        "app.services.application.commands.handlers.library.library_service.find_file_by_id",
        AsyncMock(return_value=_library_file()),
    )
    resolve_mock = AsyncMock(return_value=_snapshot(media_id, season_number=1))
    monkeypatch.setattr(
        "app.services.application.commands.handlers.library.media_service.resolve_execution_snapshot",
        resolve_mock,
    )

    command = await handler.build(
        CommandCreateRequest(
            type=CommandType.LIBRARY_FILE_DANMU_GENERATE,
            payload=LibraryFileDanmuGenerateCommandRequestPayload(
                file_id="file-1",
                target=MediaTarget(media_id=media_id, season_number=1),
            ),
        )
    )

    assert command.type == CommandType.LIBRARY_FILE_DANMU_GENERATE
    assert command.target_type == CommandTargetType.LIBRARY_FILE
    assert command.target_id == "file-1"
    assert command.media_id == media_id
    assert command.target_label == "Test Show (2024)"
    resolve_mock.assert_awaited_once_with(media_id, season_number=1)


@pytest.mark.asyncio
async def test_library_file_danmu_generate_executes_for_package_files(monkeypatch):
    handler = LibraryFileDanmuGenerateCommandHandler()
    media_id = MediaID.parse("tmdb:tv:1")
    files = [_library_file("file-1"), _library_file("file-2")]
    monkeypatch.setattr(
        "app.services.application.commands.handlers.library.library_service.find_file_by_id",
        AsyncMock(return_value=files[0]),
    )
    monkeypatch.setattr(
        "app.services.application.commands.handlers.library.library_service.get_files_by_media",
        AsyncMock(return_value=files),
    )
    monkeypatch.setattr(
        "app.services.application.commands.handlers.library.library_service.matches_package_root",
        lambda _file, package_root: package_root == "library/Show",
    )
    run_mock = AsyncMock(return_value=2)
    monkeypatch.setattr(
        "app.services.application.commands.handlers.library.danmu_application_service.run_for_library_files",
        run_mock,
    )
    command = CommandRecord(
        id="cmd-danmu",
        type=CommandType.LIBRARY_FILE_DANMU_GENERATE,
        payload=LibraryFileDanmuGenerateCommandRecordPayload(
            file_id="file-1",
            target=MediaTarget(media_id=media_id, season_number=1),
            package_root="library/Show",
        ),
        initiator=CommandInitiator.MANUAL,
        media_id=media_id,
        target=MediaTarget(media_id=media_id, season_number=1),
        target_type=CommandTargetType.LIBRARY_FILE,
        target_id="library/Show",
    )

    result = await handler.execute(command)

    assert result.result_count == 2
    run_mock.assert_awaited_once_with(files)
