from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio

from app.db.repositories.task_repository import TaskRepository
from app.schemas.config import Template, TransferMode
from app.schemas.domain.download import (
    DownloadFileInfo,
    DownloadInfoLookupStatus,
    TaskContext,
    TaskData,
    TaskErrorStage,
    TaskStatus,
    TransferFileResult,
)
from app.schemas.domain.event import EventType
from app.schemas.domain.library import LibraryFileArtifactStatus, LibraryFileArtifactType
from app.schemas.domain.resource_attributes import ResourceAttributes
from app.schemas.domain.torrent import TorrentFileItem, TorrentMetadata, TorrentCoverageKind
from app.schemas.exception.exceptions import TransferException
from app.schemas.media_id import MediaID
from app.services.domain.library.service import library_service
from app.services.audit.event_service import event_service
from app.services.domain.transfer.execution import TransferExecutionContext
from app.services.domain.transfer.ready_files import find_ready_file_indices
from app.services.domain.transfer.service import transfer_service


pytestmark = [pytest.mark.drift, pytest.mark.aggregation]


@pytest_asyncio.fixture
async def setup_import(tmp_path, monkeypatch):
    media_id = MediaID.parse(f"tmdb:tv:{uuid4().int % 1000000000 + 1}")
    task = TaskData(
        id=str(uuid4()), torrent_hash="hash", media_id=media_id,
        status=TaskStatus.DOWNLOADING, progress=0.4, downloader_id="qb",
        save_path=str(tmp_path / "downloads"),
        context=TaskContext(
            download_url="https://example.com/test.torrent", directory_id="dir",
            media={"media_id": media_id, "title": "Early Import", "year": 2020, "season_number": 1},
            selected_files=[2, 5, 9],
        ),
        metadata=TorrentMetadata(
            hash="hash", name="Show", size=12,
            files=[
                TorrentFileItem(index=index, filename=f"Show/E{episode}.mkv", size=4,
                                attrs=ResourceAttributes(seasons=[1], episodes=[episode], resolution="1080p"))
                for index, episode in [(2, 1), (5, 2), (9, 3)]
            ],
        ),
    )
    await TaskRepository().insert(task)
    for item in task.metadata.files:
        source = Path(task.save_path) / item.filename
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(b"test")  # Includes preallocated but unfinished files.
    live = [
        DownloadFileInfo(index=item.index, name=item.filename, size=4, priority=1, progress=1.0 if n == 0 else 0.5)
        for n, item in enumerate(task.metadata.files)
    ]
    info = SimpleNamespace(save_path=task.save_path, state="downloading", files_readable=True)
    client = SimpleNamespace(
        get_torrent_info=AsyncMock(return_value=info),
        lookup_torrent_info=AsyncMock(
            return_value=SimpleNamespace(status=DownloadInfoLookupStatus.FOUND, info=info),
        ),
        get_torrent_files=AsyncMock(return_value=live),
    )
    monkeypatch.setattr("app.services.domain.transfer.ready_files.download_service.task_service.resolve_task_client", lambda _: client)
    monkeypatch.setattr("app.services.domain.transfer.service.download_service.find_task_by_id", AsyncMock(return_value=task))
    context = TransferExecutionContext(
        source_base_path=Path(task.save_path), destination_base_path=tmp_path / "library",
        template_config=Template(dir_template="{title}/Season {season:00}", file_template="{title} - S{season:00}E{episode:00}"),
        media_info=task.context.media, title="Early Import", year=2020, season_number=1,
    )
    async def build_context(_):
        return context.model_copy(deep=True)
    monkeypatch.setattr("app.services.domain.transfer.execution.build_transfer_execution_context", build_context)
    monkeypatch.setattr("app.services.domain.transfer.service.media_service.refresh_profile_safely", AsyncMock())
    async def update_state(_, state, **kwargs):
        task.status = state
        return True
    state_update = AsyncMock(side_effect=update_state)
    monkeypatch.setattr("app.services.domain.transfer.service.download_service.update_task_state", state_update)
    # Quality policy is irrelevant to these files, which have a distinct media id.
    monkeypatch.setattr("app.services.domain.transfer.replacement.library_replacement_policy._quality_profile", lambda: None)
    return SimpleNamespace(
        task=task, live=live, info=info, client=client,
        state_update=state_update, context=context,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", [TransferMode.HARDLINK, TransferMode.COPY])
async def test_incremental_import_preserves_previous_batches_and_finishes_without_reimport(setup_import, mode):
    env = setup_import
    env.context.transfer_mode = mode
    assert await find_ready_file_indices(env.task) == [2]
    first = await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[2, 5])
    assert [item.file_index for item in first.transferred_files] == [2]
    destination = Path(first.transferred_files[0].destination_path)
    source = Path(first.transferred_files[0].source_path)
    assert destination.read_bytes() == source.read_bytes() == b"test"
    assert (source.stat().st_ino == destination.stat().st_ino) == (mode == TransferMode.HARDLINK)
    inode = destination.stat().st_ino
    env.state_update.assert_not_awaited()
    assert env.task.status == TaskStatus.DOWNLOADING

    assert (await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[2])).transferred_files == []
    assert (await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[])).transferred_files == []
    assert event_service.list_events(task_id=env.task.id, types=[EventType.MEDIA_IMPORT_COMPLETED])[0] == 1

    env.live[1].progress = env.live[2].progress = 1.0
    batch = await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[5, 9])
    assert len(batch.transferred_files) == 2
    files = await library_service.get_files_by_task(env.task.id)
    assert {item.file_index for item in files} == {2, 5, 9}
    assert destination.stat().st_ino == inode
    assert event_service.list_events(task_id=env.task.id, types=[EventType.MEDIA_IMPORT_COMPLETED])[0] == 2

    env.task.status = TaskStatus.FINISHED
    final = await transfer_service.perform_transfer_by_task_id(env.task.id)
    assert final.transferred_files == []
    assert env.task.status == TaskStatus.COMPLETED
    assert len(await library_service.get_files_by_task(env.task.id)) == 3
    assert event_service.list_events(task_id=env.task.id, types=[EventType.MEDIA_IMPORT_COMPLETED])[0] == 2


@pytest.mark.asyncio
async def test_empty_final_batch_does_not_require_transfer_context(setup_import, monkeypatch):
    env = setup_import
    for item in env.live:
        item.progress = 1.0
    await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[2, 5, 9])
    env.task.status = TaskStatus.FINISHED
    build_context = AsyncMock(side_effect=TransferException("backendErrors.transferTaskContextMissing"))
    monkeypatch.setattr(
        "app.services.domain.transfer.service.execution.build_transfer_execution_context",
        build_context,
    )

    result = await transfer_service.perform_transfer_by_task_id(env.task.id)

    assert result.transferred_files == []
    assert env.task.status == TaskStatus.COMPLETED
    build_context.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["uploading", "seeding", "paused"])
async def test_final_import_only_adds_remaining_files(setup_import, state):
    env = setup_import
    await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[2])
    env.task.status = TaskStatus.FINISHED
    env.info.state = state
    env.live[1].progress = env.live[2].progress = 1.0
    result = await transfer_service.perform_transfer_by_task_id(env.task.id)
    assert {item.file_index for item in result.transferred_files} == {5, 9}
    assert len(await library_service.get_files_by_task(env.task.id)) == 3
    assert env.task.status == TaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_stale_finished_state_cannot_publish_unfinished_files(setup_import):
    env = setup_import
    await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[2])
    env.task.status = TaskStatus.FINISHED
    assert (await transfer_service.perform_transfer_by_task_id(env.task.id)).transferred_files == []
    assert len(await library_service.get_files_by_task(env.task.id)) == 1
    env.state_update.assert_not_awaited()


@pytest.mark.asyncio
async def test_downloader_file_list_failure_is_treated_as_waiting(setup_import):
    env = setup_import
    env.client.get_torrent_files.side_effect = OSError("downloader disconnected")

    assert await find_ready_file_indices(env.task) == []
    result = await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[2])

    assert result.transferred_files == []
    assert env.task.status == TaskStatus.DOWNLOADING


@pytest.mark.asyncio
async def test_finished_incremental_import_ignores_missing_source_for_satisfied_index(setup_import):
    env = setup_import
    first = await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[2])
    Path(first.transferred_files[0].source_path).unlink()
    env.task.status = TaskStatus.FINISHED

    result = await transfer_service.perform_transfer_by_task_id(env.task.id)

    assert result.transferred_files == []
    assert {item.file_index for item in await library_service.get_files_by_task(env.task.id)} == {2}
    assert env.task.status == TaskStatus.FINISHED
    env.state_update.assert_not_awaited()


@pytest.mark.asyncio
async def test_finished_incremental_import_repairs_truncated_registered_file(setup_import):
    env = setup_import
    first = await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[2])
    destination = Path(first.transferred_files[0].destination_path)
    destination.unlink()
    destination.write_bytes(b"x")
    env.task.status = TaskStatus.FINISHED
    env.info.state = "seeding"
    for item in env.live:
        item.progress = 1.0

    result = await transfer_service.perform_transfer_by_task_id(env.task.id)

    assert {item.file_index for item in result.transferred_files} == {2, 5, 9}
    assert destination.read_bytes() == b"test"
    assert env.task.status == TaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_finished_incremental_import_waits_for_resume_data_check(setup_import):
    env = setup_import
    await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[2])
    env.task.status = TaskStatus.FINISHED
    env.info.state = "checkingResumeData"

    result = await transfer_service.perform_transfer_by_task_id(env.task.id)

    assert result.transferred_files == []
    assert len(await library_service.get_files_by_task(env.task.id)) == 1
    assert env.task.status == TaskStatus.FINISHED
    env.state_update.assert_not_awaited()


@pytest.mark.asyncio
async def test_finished_incremental_import_fails_when_remaining_source_is_missing(setup_import):
    env = setup_import
    await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[2])
    env.task.status = TaskStatus.FINISHED
    (Path(env.task.save_path) / env.task.metadata.files[1].filename).unlink()

    with pytest.raises(TransferException, match="backendErrors.transferSourceFileNotFound"):
        await transfer_service.perform_transfer_by_task_id(env.task.id)

    assert env.state_update.await_args.kwargs["error_stage"] == TaskErrorStage.TRANSFER


@pytest.mark.asyncio
async def test_finished_incremental_import_uses_visible_sources_when_torrent_is_confirmed_missing(setup_import):
    env = setup_import
    await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[2])
    env.task.status = TaskStatus.FINISHED
    env.client.lookup_torrent_info.return_value = SimpleNamespace(
        status=DownloadInfoLookupStatus.MISSING,
        info=None,
    )

    result = await transfer_service.perform_transfer_by_task_id(env.task.id)

    assert {item.file_index for item in result.transferred_files} == {5, 9}
    assert env.task.status == TaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_finished_incremental_import_waits_when_downloader_is_unavailable(setup_import):
    env = setup_import
    await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[2])
    env.task.status = TaskStatus.FINISHED
    env.client.lookup_torrent_info.return_value = SimpleNamespace(
        status=DownloadInfoLookupStatus.UNAVAILABLE,
        info=None,
    )

    result = await transfer_service.perform_transfer_by_task_id(env.task.id)

    assert result.transferred_files == []
    assert env.task.status == TaskStatus.FINISHED


@pytest.mark.asyncio
async def test_finished_incremental_import_converts_library_stat_error(setup_import, monkeypatch):
    env = setup_import
    first = await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[2])
    env.task.status = TaskStatus.FINISHED
    library_path = Path(first.transferred_files[0].destination_path)
    original_is_file = Path.is_file

    def fail_library_stat(path):
        if path == library_path:
            raise OSError("library unavailable")
        return original_is_file(path)

    monkeypatch.setattr(Path, "is_file", fail_library_stat)

    with pytest.raises(TransferException, match="backendErrors.transferFailed") as exc_info:
        await transfer_service.perform_transfer_by_task_id(env.task.id)

    assert exc_info.value.params == {"reason": "library unavailable"}
    assert env.task.status == TaskStatus.FINISHED


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state",
    ["checkingDL", "checkingUP", "checkingResumeData", "moving", "allocating", "error", "missingFiles", "checking", "missing", "unknown"],
)
async def test_unsafe_downloader_states_do_not_import(setup_import, state):
    env = setup_import
    env.info.state = state
    assert await find_ready_file_indices(env.task) == []


@pytest.mark.asyncio
async def test_selection_progress_path_and_visibility_are_checked(setup_import):
    env = setup_import
    env.live[0].progress = 0.9999
    assert await find_ready_file_indices(env.task) == []
    env.live[0].progress = 1.0
    env.live[0].priority = 0
    assert await find_ready_file_indices(env.task) == []
    env.live[0].priority = 1
    env.task.context.selected_files = [5, 9]
    assert await find_ready_file_indices(env.task) == []
    env.task.context.selected_files = [2, 5, 9]
    env.live[0].name = "Show/renamed.mkv"
    assert await find_ready_file_indices(env.task) == []
    env.live[0].name = "Show/E1.mkv"
    source = Path(env.task.save_path) / "Show/E1.mkv"
    source.write_bytes(b"incomplete")
    assert await find_ready_file_indices(env.task) == []
    source.unlink()
    assert await find_ready_file_indices(env.task) == []


@pytest.mark.asyncio
async def test_rootless_live_file_name_matches_rooted_torrent_metadata(setup_import):
    env = setup_import
    env.live[0].name = "E1.mkv"
    assert await find_ready_file_indices(env.task) == [2]


@pytest.mark.asyncio
async def test_early_import_ignores_subtitle_then_final_import_includes_it(setup_import):
    env = setup_import
    subtitle = TorrentFileItem(
        index=11,
        filename="Show/E1.srt",
        size=4,
        attrs=ResourceAttributes(seasons=[1], episodes=[1], resolution="1080p"),
    )
    env.task.metadata.files.append(subtitle)
    env.task.context.selected_files.append(11)
    subtitle_path = Path(env.task.save_path) / subtitle.filename
    subtitle_path.write_bytes(b"subs")
    env.live.append(DownloadFileInfo(index=11, name=subtitle.filename, size=4, priority=1, progress=1.0))

    assert await find_ready_file_indices(env.task) == [2]
    first = await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[2, 11])
    assert {item.file_index for item in first.transferred_files} == {2}

    env.task.status = TaskStatus.FINISHED
    env.info.state = "seeding"
    for item in env.live:
        item.progress = 1.0
    final = await transfer_service.perform_transfer_by_task_id(env.task.id)

    assert {item.file_index for item in final.transferred_files} == {5, 9, 11}
    assert env.task.status == TaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_finished_incremental_import_does_not_wait_forever_for_zero_byte_auxiliary_file(setup_import):
    env = setup_import
    env.task.context.selected_files = [2]
    await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[2])
    auxiliary = TorrentFileItem(index=11, filename="Show/empty.nfo", size=0)
    env.task.metadata.files.append(auxiliary)
    env.task.context.selected_files.append(11)
    auxiliary_path = Path(env.task.save_path) / auxiliary.filename
    auxiliary_path.touch()
    env.live.append(DownloadFileInfo(index=11, name=auxiliary.filename, size=0, priority=1, progress=1.0))
    env.task.status = TaskStatus.FINISHED
    env.info.state = "seeding"

    with pytest.raises(TransferException, match="backendErrors.transferSourceFilesNotReady"):
        await transfer_service.perform_transfer_by_task_id(env.task.id)

    assert env.state_update.await_args_list[-2].args[1] == TaskStatus.TRANSFERRING
    assert env.state_update.await_args.kwargs["error_stage"] == TaskErrorStage.TRANSFER


@pytest.mark.asyncio
async def test_finished_incremental_import_rejects_deselected_live_file_even_when_source_exists(setup_import):
    env = setup_import
    env.task.context.selected_files = [2, 5]
    await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[2])
    env.task.status = TaskStatus.FINISHED
    env.info.state = "seeding"
    env.live[1].priority = 0

    with pytest.raises(TransferException, match="backendErrors.transferSourceFilesNotReady"):
        await transfer_service.perform_transfer_by_task_id(env.task.id)

    assert env.state_update.await_args_list[-2].args[1] == TaskStatus.TRANSFERRING
    assert env.state_update.await_args.kwargs["error_stage"] == TaskErrorStage.TRANSFER


@pytest.mark.asyncio
async def test_replaced_early_file_is_satisfied_by_visible_higher_quality_episode(setup_import):
    env = setup_import
    first = await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[2])
    assert env.task.context.imported_file_indices == [2]
    old_file = (await library_service.get_files_by_task(env.task.id))[0]
    destination = Path(first.transferred_files[0].destination_path)
    higher_task_id = str(uuid4())
    await library_service.replace_task_entries(
        higher_task_id,
        "dir",
        env.task.media_id,
        [TransferFileResult(
            source_path=str(destination),
            destination_path=str(destination),
            file_index=0,
            file_item=TorrentFileItem(
                index=0,
                filename=destination.name,
                size=4,
                attrs=ResourceAttributes(seasons=[1], episodes=[1], resolution="2160p"),
            ),
            episode_number=1,
            episode_numbers=[1],
        )],
        season=1,
        replacement_files=[old_file],
    )
    combined_path = env.context.destination_base_path / "old-E1-E2.mkv"
    combined_path.write_bytes(b"old combined")
    combined_task_id = str(uuid4())
    await library_service.replace_task_entries(
        combined_task_id,
        "dir",
        env.task.media_id,
        [TransferFileResult(
            source_path=str(combined_path),
            destination_path=str(combined_path),
            file_index=0,
            file_item=TorrentFileItem(
                index=0,
                filename=combined_path.name,
                size=combined_path.stat().st_size,
                attrs=ResourceAttributes(seasons=[1], episodes=[1, 2], resolution="720p"),
            ),
            episode_number=1,
            episode_numbers=[1, 2],
        )],
        season=1,
    )

    assert await library_service.get_files_by_task(env.task.id) == []
    assert await find_ready_file_indices(env.task) == []

    env.task.status = TaskStatus.FINISHED
    env.info.state = "seeding"
    env.live[1].progress = env.live[2].progress = 1.0
    final = await transfer_service.perform_transfer_by_task_id(env.task.id)

    assert {item.file_index for item in final.transferred_files} == {5, 9}
    assert env.task.status == TaskStatus.COMPLETED
    assert not combined_path.exists()
    assert await library_service.get_files_by_task(combined_task_id) == []


@pytest.mark.asyncio
async def test_replaced_early_file_restores_episode_group_from_context_attributes(setup_import):
    env = setup_import
    first = await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[2])
    old_file = (await library_service.get_files_by_task(env.task.id))[0]
    destination = Path(first.transferred_files[0].destination_path)
    env.task.metadata.files[0].attrs = ResourceAttributes(resolution="1080p")
    env.task.context.parsed_attributes = ResourceAttributes(
        seasons=[1],
        episodes=[1],
        resolution="1080p",
    )
    await library_service.replace_task_entries(
        str(uuid4()),
        "dir",
        env.task.media_id,
        [TransferFileResult(
            source_path=str(destination),
            destination_path=str(destination),
            file_index=0,
            file_item=TorrentFileItem(
                index=0,
                filename=destination.name,
                size=4,
                attrs=ResourceAttributes(seasons=[1], episodes=[1], resolution="2160p"),
            ),
            episode_number=1,
            episode_numbers=[1],
        )],
        season=1,
        replacement_files=[old_file],
    )

    assert env.task.context.imported_file_indices == [2]
    assert await library_service.get_files_by_task(env.task.id) == []
    assert await find_ready_file_indices(env.task) == []


@pytest.mark.asyncio
async def test_imported_single_episodes_satisfy_later_lower_quality_combined_file(setup_import):
    env = setup_import
    env.live[1].progress = 1.0
    await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[2, 5])
    env.task.metadata.files[2].attrs.episodes = [1, 2]
    env.task.metadata.files[2].attrs.resolution = ResourceAttributes(resolution="720p").resolution
    env.live[2].progress = 1.0

    assert env.task.context.imported_file_indices == [2, 5]
    assert await find_ready_file_indices(env.task) == []


@pytest.mark.asyncio
async def test_imported_combined_file_satisfies_later_equal_quality_single_episode(setup_import):
    env = setup_import
    env.task.metadata.files[0].attrs.episodes = [1, 2]
    await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[2])
    env.task.metadata.files[1].attrs.episodes = [1]
    env.live[1].progress = 1.0

    assert env.task.context.imported_file_indices == [2]
    assert await find_ready_file_indices(env.task) == []


@pytest.mark.asyncio
async def test_replaced_combined_file_ignores_total_size_when_single_episodes_match_quality(setup_import):
    env = setup_import
    combined_item = env.task.metadata.files[0]
    combined_item.size = 100
    combined_item.attrs.episodes = [1, 2]
    combined_item.attrs.resolution = ResourceAttributes(resolution="720p").resolution
    source = Path(env.task.save_path) / combined_item.filename
    source.write_bytes(b"x" * 100)
    env.live[0].size = 100

    first = await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[2])
    old_file = (await library_service.get_files_by_task(env.task.id))[0]
    assert env.task.context.imported_file_indices == [2]

    replacement_task_id = str(uuid4())
    replacement_results = []
    for episode in (1, 2):
        path = env.context.destination_base_path / f"replacement-E{episode}.mkv"
        path.write_bytes(b"y" * 40)
        replacement_results.append(TransferFileResult(
            source_path=str(path),
            destination_path=str(path),
            file_index=episode,
            file_item=TorrentFileItem(
                index=episode,
                filename=path.name,
                size=40,
                attrs=ResourceAttributes(seasons=[1], episodes=[episode], resolution="720p"),
            ),
            episode_number=episode,
            episode_numbers=[episode],
        ))
    await library_service.replace_task_entries(
        replacement_task_id,
        "dir",
        env.task.media_id,
        replacement_results,
        season=1,
        replacement_files=[old_file],
    )

    assert await library_service.get_files_by_task(env.task.id) == []
    assert await find_ready_file_indices(env.task) == []
    assert first.transferred_files[0].file_index == 2


@pytest.mark.asyncio
async def test_stale_command_does_not_import_deselected_or_invalidated_files(setup_import):
    env = setup_import
    assert await find_ready_file_indices(env.task) == [2]
    env.task.context.selected_files = [5]
    assert (await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[2])).transferred_files == []
    env.task.context.selected_files = [2]
    env.live[0].progress = 0.3
    assert (await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[2])).transferred_files == []
    assert event_service.list_events(task_id=env.task.id, types=[EventType.MEDIA_IMPORT_COMPLETED])[0] == 0


@pytest.mark.asyncio
async def test_disc_packages_wait_for_full_import(setup_import):
    env = setup_import
    env.task.metadata.coverage_kind = TorrentCoverageKind.DISC_PACKAGE
    assert await find_ready_file_indices(env.task) == []


@pytest.mark.asyncio
async def test_multi_episode_file_registers_every_episode(setup_import):
    env = setup_import
    env.task.metadata.files[0].attrs.episodes = [1, 2]
    result = await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[2])
    assert result.transferred_files[0].episode_numbers == [1, 2]
    files = await library_service.get_files_by_task(env.task.id)
    episodes = await library_service.get_episodes_by_media(env.task.media_id)
    assert {item.episode for item in episodes if item.file_id == files[0].id} == {1, 2}


@pytest.mark.asyncio
async def test_later_incremental_batch_replaces_lower_quality_file_from_same_task(setup_import):
    env = setup_import
    env.context.template_config.file_template = "{title} - S{season:00}E{episode:00} - {resolution}"
    env.task.metadata.files[1].attrs.episodes = [1]
    env.task.metadata.files[1].attrs.resolution = ResourceAttributes(resolution="2160p").resolution

    first = await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[2])
    first_path = Path(first.transferred_files[0].destination_path)
    assert first_path.is_file()
    first_file = (await library_service.get_files_by_task(env.task.id))[0]
    xml_path = first_path.with_suffix(".danmu.xml")
    ass_path = first_path.with_suffix(".danmu.ass")
    xml_path.write_text("xml")
    ass_path.write_text("ass")
    await library_service.mark_artifact(
        library_file_id=first_file.id,
        artifact_type=LibraryFileArtifactType.danmu_xml,
        expected_path=str(xml_path),
        status=LibraryFileArtifactStatus.succeeded,
    )
    await library_service.mark_artifact(
        library_file_id=first_file.id,
        artifact_type=LibraryFileArtifactType.danmu_ass,
        expected_path=str(ass_path),
        status=LibraryFileArtifactStatus.succeeded,
    )

    env.live[1].progress = 1.0
    second = await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[5])
    second_path = Path(second.transferred_files[0].destination_path)
    files = await library_service.get_files_by_task(env.task.id)

    assert not first_path.exists()
    assert not xml_path.exists()
    assert not ass_path.exists()
    assert second_path.is_file()
    assert len(files) == 1
    assert files[0].file_index == 5
    assert str(files[0].resource_attributes.resolution) == "2160p"
    assert await library_service.get_artifacts_by_file_ids([first_file.id]) == []


@pytest.mark.asyncio
async def test_same_incremental_batch_keeps_only_best_video_for_the_same_episode(setup_import):
    env = setup_import
    env.context.template_config.file_template = "{title} - S{season:00}E{episode:00} - {resolution}"
    env.task.metadata.files[0].attrs.resolution = ResourceAttributes(resolution="720p").resolution
    env.task.metadata.files[1].attrs.episodes = [1]
    env.task.metadata.files[1].attrs.resolution = ResourceAttributes(resolution="2160p").resolution
    env.live[1].progress = 1.0

    result = await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[2, 5])
    files = await library_service.get_files_by_task(env.task.id)

    assert [item.file_index for item in result.transferred_files] == [5]
    assert [item.file_index for item in files] == [5]
    assert str(files[0].resource_attributes.resolution) == "2160p"
    assert env.task.context.imported_file_indices == [2, 5]
    assert await find_ready_file_indices(env.task) == []


@pytest.mark.asyncio
async def test_failed_partial_transfer_raises_domain_error_keeps_downloading_and_can_retry(setup_import, monkeypatch):
    env = setup_import
    with monkeypatch.context() as patch:
        patch.setattr("app.services.domain.transfer.execution.execute_transfer_plan", AsyncMock(side_effect=OSError("disk full")))
        patch.setattr("app.services.domain.transfer.service.emit_media_import_failed", AsyncMock())
        with pytest.raises(TransferException, match="backendErrors.transferFailed") as exc_info:
            await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[2])
    assert exc_info.value.params == {"reason": "disk full"}
    assert env.task.status == TaskStatus.DOWNLOADING
    env.state_update.assert_not_awaited()
    assert len((await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[2])).transferred_files) == 1


@pytest.mark.asyncio
async def test_scheduler_enqueues_one_subset_and_skips_imported_files(setup_import, monkeypatch):
    from app.services.application.commands.service import CommandConflictException
    from app.services.application.workflows.scheduled_transfer.service import scheduled_transfer_command_service

    env = setup_import
    env.live[1].progress = 1.0
    monkeypatch.setattr(
        "app.services.application.workflows.scheduled_transfer.service.download_service.get_tasks",
        AsyncMock(return_value=[env.task]),
    )
    statuses = AsyncMock(return_value={env.task.id: env.info})
    monkeypatch.setattr(
        "app.services.application.workflows.scheduled_transfer.service.download_service.get_torrent_status_by_tasks",
        statuses,
    )
    create = AsyncMock()
    monkeypatch.setattr("app.services.application.workflows.scheduled_transfer.service.command_service.create_command", create)
    result = await scheduled_transfer_command_service.enqueue_ready_files()
    assert result.completed == 1
    statuses.assert_awaited_once_with([env.task])
    env.client.get_torrent_info.assert_not_awaited()
    payload = create.call_args.args[0].payload
    assert payload.file_indices == [2, 5]
    create.side_effect = CommandConflictException()
    assert (await scheduled_transfer_command_service.enqueue_ready_files()).errors == 0
    await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=payload.file_indices)
    create.reset_mock()
    assert (await scheduled_transfer_command_service.enqueue_ready_files()).completed == 0
    create.assert_not_awaited()


@pytest.mark.asyncio
async def test_scheduler_skips_batch_status_with_unreadable_files(setup_import, monkeypatch):
    from app.services.application.workflows.scheduled_transfer.service import scheduled_transfer_command_service

    env = setup_import
    env.info.files_readable = False
    monkeypatch.setattr(
        "app.services.application.workflows.scheduled_transfer.service.download_service.get_tasks",
        AsyncMock(return_value=[env.task]),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.scheduled_transfer.service.download_service.get_torrent_status_by_tasks",
        AsyncMock(return_value={env.task.id: env.info}),
    )
    create = AsyncMock()
    monkeypatch.setattr("app.services.application.workflows.scheduled_transfer.service.command_service.create_command", create)

    result = await scheduled_transfer_command_service.enqueue_ready_files()

    assert result.completed == 0
    create.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["stoppedDL", "paused"])
async def test_paused_task_keeps_state_and_task_lock_excludes_concurrent_operations(setup_import, state):
    from app.services.platform.domain_lock_service import domain_lock_service

    env = setup_import
    env.task.status = TaskStatus.PAUSED
    env.info.state = state
    async with domain_lock_service.acquire_task_op(env.task.id):
        with pytest.raises(TransferException, match="backendErrors.taskBusy"):
            await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[2])
    await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[2])
    assert env.task.status == TaskStatus.PAUSED
    env.state_update.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("first_resolution", ["480p", "720p", "1080p"])
@pytest.mark.parametrize("second_resolution", ["720p", "1080p"])
@pytest.mark.parametrize("same_batch", [False, True])
async def test_combined_old_file_requires_equal_or_better_replacements_for_every_episode(setup_import, first_resolution, second_resolution, same_batch):
    env = setup_import
    env.task.metadata.files[0].attrs.resolution = ResourceAttributes(resolution=first_resolution).resolution
    env.task.metadata.files[1].attrs.resolution = ResourceAttributes(resolution=second_resolution).resolution
    old_path = env.context.destination_base_path / "old-E1-E2.mkv"
    old_path.parent.mkdir(parents=True, exist_ok=True)
    old_path.write_bytes(b"old" * 100)
    old_task_id = str(uuid4())
    await library_service.replace_task_entries(
        old_task_id, "dir", env.task.media_id,
        [TransferFileResult(
            source_path=str(old_path), destination_path=str(old_path), file_index=0,
            file_item=TorrentFileItem(index=0, filename=old_path.name, size=300,
                                      attrs=ResourceAttributes(seasons=[1], episodes=[1, 2], resolution="720p")),
            episode_number=1, episode_numbers=[1, 2],
        )],
        season=1,
    )
    if same_batch:
        env.live[1].progress = 1.0
        await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[2, 5])
    else:
        await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[2])
        assert old_path.is_file()
        assert len(await library_service.get_files_by_task(old_task_id)) == 1
        env.live[1].progress = 1.0
        await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[5])
    preserve_old = first_resolution == "480p"
    assert old_path.exists() == preserve_old
    assert len(await library_service.get_files_by_task(old_task_id)) == int(preserve_old)
    assert len(await library_service.get_files_by_task(env.task.id)) == 2


@pytest.mark.asyncio
async def test_combined_file_uses_higher_quality_existing_episode_not_replaced_by_lower_batch_file(setup_import):
    env = setup_import
    env.task.metadata.files[0].attrs.resolution = ResourceAttributes(resolution="480p").resolution
    env.task.metadata.files[1].attrs.resolution = ResourceAttributes(resolution="720p").resolution
    env.live[1].progress = 1.0

    old_path = env.context.destination_base_path / "old-E1-E2.mkv"
    old_path.parent.mkdir(parents=True, exist_ok=True)
    old_path.write_bytes(b"old combined")
    old_task_id = str(uuid4())
    await library_service.replace_task_entries(
        old_task_id,
        "dir",
        env.task.media_id,
        [TransferFileResult(
            source_path=str(old_path),
            destination_path=str(old_path),
            file_index=0,
            file_item=TorrentFileItem(
                index=0,
                filename=old_path.name,
                size=old_path.stat().st_size,
                attrs=ResourceAttributes(seasons=[1], episodes=[1, 2], resolution="720p"),
            ),
            episode_number=1,
            episode_numbers=[1, 2],
        )],
        season=1,
    )
    better_path = env.context.destination_base_path / "better-E1.mkv"
    better_path.write_bytes(b"better")
    better_task_id = str(uuid4())
    await library_service.replace_task_entries(
        better_task_id,
        "dir",
        env.task.media_id,
        [TransferFileResult(
            source_path=str(better_path),
            destination_path=str(better_path),
            file_index=0,
            file_item=TorrentFileItem(
                index=0,
                filename=better_path.name,
                size=better_path.stat().st_size,
                attrs=ResourceAttributes(seasons=[1], episodes=[1], resolution="1080p"),
            ),
            episode_number=1,
            episode_numbers=[1],
        )],
        season=1,
    )

    await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[2, 5])

    assert not old_path.exists()
    assert better_path.exists()
    assert await library_service.get_files_by_task(old_task_id) == []
    assert len(await library_service.get_files_by_task(better_task_id)) == 1


@pytest.mark.asyncio
async def test_subtitle_does_not_prove_combined_video_episode_replacement(setup_import):
    env = setup_import
    env.task.metadata.files[1].attrs.resolution = ResourceAttributes(resolution="720p").resolution
    env.live[1].progress = 1.0

    combined_path = env.context.destination_base_path / "old-E1-E2.mkv"
    combined_path.parent.mkdir(parents=True, exist_ok=True)
    combined_path.write_bytes(b"old combined")
    combined_task_id = str(uuid4())
    await library_service.replace_task_entries(
        combined_task_id,
        "dir",
        env.task.media_id,
        [TransferFileResult(
            source_path=str(combined_path),
            destination_path=str(combined_path),
            file_index=0,
            file_item=TorrentFileItem(
                index=0,
                filename=combined_path.name,
                size=combined_path.stat().st_size,
                attrs=ResourceAttributes(seasons=[1], episodes=[1, 2], resolution="720p"),
            ),
            episode_number=1,
            episode_numbers=[1, 2],
        )],
        season=1,
    )
    subtitle_path = env.context.destination_base_path / "subtitle-E1.srt"
    subtitle_path.write_text("subtitle")
    subtitle_task_id = str(uuid4())
    await library_service.replace_task_entries(
        subtitle_task_id,
        "dir",
        env.task.media_id,
        [TransferFileResult(
            source_path=str(subtitle_path),
            destination_path=str(subtitle_path),
            file_index=0,
            file_item=TorrentFileItem(
                index=0,
                filename=subtitle_path.name,
                size=subtitle_path.stat().st_size,
                attrs=ResourceAttributes(seasons=[1], episodes=[1], resolution="1080p"),
            ),
            episode_number=1,
            episode_numbers=[1],
        )],
        season=1,
    )

    await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[5])

    assert combined_path.is_file()
    assert subtitle_path.is_file()
    assert len(await library_service.get_files_by_task(combined_task_id)) == 1
    assert len(await library_service.get_files_by_task(subtitle_task_id)) == 1
