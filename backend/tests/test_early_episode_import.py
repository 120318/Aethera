from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.schemas.config import Template, TransferMode
from app.schemas.domain.download import DownloadFileInfo, TaskContext, TaskData, TaskStatus, TransferFileResult
from app.schemas.domain.resource_attributes import ResourceAttributes
from app.schemas.domain.torrent import TorrentFileItem, TorrentMetadata, TorrentCoverageKind
from app.schemas.media_id import MediaID
from app.services.domain.library.service import library_service
from app.services.domain.transfer.execution import TransferExecutionContext
from app.services.domain.transfer.ready_files import find_ready_file_indices
from app.services.domain.transfer.service import transfer_service


pytestmark = [pytest.mark.drift, pytest.mark.aggregation]


@pytest.fixture
def setup_import(tmp_path, monkeypatch):
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
    for item in task.metadata.files:
        source = Path(task.save_path) / item.filename
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(b"test")  # Includes preallocated but unfinished files.
    live = [
        DownloadFileInfo(index=item.index, name=item.filename, size=4, priority=1, progress=1.0 if n == 0 else 0.5)
        for n, item in enumerate(task.metadata.files)
    ]
    info = SimpleNamespace(save_path=task.save_path, state="downloading")
    client = SimpleNamespace(get_torrent_info=AsyncMock(return_value=info), get_torrent_files=AsyncMock(return_value=live))
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
    event = AsyncMock()
    monkeypatch.setattr("app.services.domain.transfer.service.emit_media_import_completed", event)
    async def update_state(_, state, **kwargs):
        task.status = state
        return True
    state_update = AsyncMock(side_effect=update_state)
    monkeypatch.setattr("app.services.domain.transfer.service.download_service.update_task_state", state_update)
    # Quality policy is irrelevant to these files, which have a distinct media id.
    monkeypatch.setattr("app.services.domain.transfer.replacement.library_replacement_policy._quality_profile", lambda: None)
    return SimpleNamespace(task=task, live=live, info=info, event=event, state_update=state_update, context=context)


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
    assert env.event.await_count == 1

    env.live[1].progress = env.live[2].progress = 1.0
    batch = await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[5, 9])
    assert len(batch.transferred_files) == 2
    files = await library_service.get_files_by_task(env.task.id)
    assert {item.file_index for item in files} == {2, 5, 9}
    assert destination.stat().st_ino == inode
    assert env.event.await_count == 2  # One event for both episodes.

    env.task.status = TaskStatus.FINISHED
    final = await transfer_service.perform_transfer_by_task_id(env.task.id)
    assert final.transferred_files == []
    assert env.task.status == TaskStatus.COMPLETED
    assert len(await library_service.get_files_by_task(env.task.id)) == 3
    assert env.event.await_count == 2


@pytest.mark.asyncio
async def test_final_import_only_adds_remaining_files(setup_import):
    env = setup_import
    await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[2])
    env.task.status = TaskStatus.FINISHED
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
@pytest.mark.parametrize("state", ["checkingDL", "checkingUP", "moving", "allocating", "error", "missingFiles"])
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
async def test_stale_command_does_not_import_deselected_or_invalidated_files(setup_import):
    env = setup_import
    assert await find_ready_file_indices(env.task) == [2]
    env.task.context.selected_files = [5]
    assert (await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[2])).transferred_files == []
    env.task.context.selected_files = [2]
    env.live[0].progress = 0.3
    assert (await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[2])).transferred_files == []
    env.event.assert_not_awaited()


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
async def test_failed_partial_transfer_keeps_downloading_and_can_retry(setup_import, monkeypatch):
    env = setup_import
    with monkeypatch.context() as patch:
        patch.setattr("app.services.domain.transfer.execution.execute_transfer", AsyncMock(side_effect=OSError("disk full")))
        patch.setattr("app.services.domain.transfer.service.emit_media_import_failed", AsyncMock())
        with pytest.raises(OSError):
            await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[2])
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
    create = AsyncMock()
    monkeypatch.setattr("app.services.application.workflows.scheduled_transfer.service.command_service.create_command", create)
    result = await scheduled_transfer_command_service.enqueue_ready_files()
    assert result.completed == 1
    payload = create.call_args.args[0].payload
    assert payload.file_indices == [2, 5]
    create.side_effect = CommandConflictException()
    assert (await scheduled_transfer_command_service.enqueue_ready_files()).errors == 0
    await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=payload.file_indices)
    create.reset_mock()
    assert (await scheduled_transfer_command_service.enqueue_ready_files()).completed == 0
    create.assert_not_awaited()


@pytest.mark.asyncio
async def test_paused_task_keeps_state_and_task_lock_excludes_concurrent_operations(setup_import):
    from app.schemas.exception.exceptions import TransferException
    from app.services.platform.domain_lock_service import domain_lock_service

    env = setup_import
    env.task.status = TaskStatus.PAUSED
    env.info.state = "stoppedDL"
    async with domain_lock_service.acquire_task_op(env.task.id):
        with pytest.raises(TransferException, match="backendErrors.taskBusy"):
            await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[2])
    await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[2])
    assert env.task.status == TaskStatus.PAUSED
    env.state_update.assert_not_awaited()


@pytest.mark.asyncio
async def test_combined_old_file_is_preserved_until_all_its_episodes_have_replacements(setup_import):
    env = setup_import
    old_path = env.context.destination_base_path / "old-E1-E2.mkv"
    old_path.parent.mkdir(parents=True, exist_ok=True)
    old_path.write_bytes(b"old")
    old_task_id = str(uuid4())
    await library_service.replace_task_entries(
        old_task_id, "dir", env.task.media_id,
        [TransferFileResult(
            source_path=str(old_path), destination_path=str(old_path), file_index=0,
            file_item=TorrentFileItem(index=0, filename=old_path.name, size=3,
                                      attrs=ResourceAttributes(seasons=[1], episodes=[1, 2], resolution="720p")),
            episode_number=1, episode_numbers=[1, 2],
        )],
        season=1,
    )
    await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[2])
    assert old_path.is_file()
    assert len(await library_service.get_files_by_task(old_task_id)) == 1
    env.live[1].progress = 1.0
    await transfer_service.perform_transfer_by_task_id(env.task.id, file_indices=[5])
    assert not old_path.exists()
    assert await library_service.get_files_by_task(old_task_id) == []
    assert len(await library_service.get_files_by_task(env.task.id)) == 2
