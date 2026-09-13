import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

os.environ.setdefault("DATA_PATH", f"/tmp/aethera-test-data-{uuid.uuid4()}")

from app.schemas.config import Template
from app.schemas.domain.download import DownloadFileInfo, TaskContext, TaskData, TaskStatus, TransferFileResult
from app.schemas.domain.library import LibraryEpisode, LibraryFile
from app.schemas.domain.resource_attributes import ResourceAttributes
from app.schemas.domain.torrent import TorrentFileItem, TorrentMetadata
from app.schemas.domain.torrent_status import TorrentState, TorrentStatus
from app.schemas.media_id import MediaID
from app.services.application.workflows.scheduled_transfer.service import scheduled_transfer_command_service
from app.services.domain.transfer import transfer_service
from app.services.domain.transfer.episode_batch import find_ready_episode_file_indices, has_episode_target_collisions
from app.services.domain.transfer.execution import TransferExecutionContext
from app.services.domain.transfer.replacement import library_replacement_policy
from app.services.domain.transfer.service import build_media_import_completed_event


pytestmark = [pytest.mark.drift, pytest.mark.health]


def _task(status: TaskStatus = TaskStatus.DOWNLOADING) -> TaskData:
    media_id = MediaID.parse("tmdb:tv:1")
    files = [
        TorrentFileItem(index=2, filename="Show/Show.S01E01.mkv", size=4, attrs=ResourceAttributes(seasons=[1], episodes=[1], resolution="2160p")),
        TorrentFileItem(index=5, filename="Show/Show.S01E02.mkv", size=4, attrs=ResourceAttributes(seasons=[1], episodes=[2], resolution="2160p")),
        TorrentFileItem(index=8, filename="Show/Show.S01E02.zh.srt", size=4, attrs=ResourceAttributes(seasons=[1], episodes=[2])),
    ]
    return TaskData(
        id="task-1",
        torrent_hash="hash-1",
        media_id=media_id,
        status=status,
        downloader_id="downloader-1",
        save_path="downloads/show",
        context=TaskContext(
            download_url="https://example.com/file.torrent",
            directory_id="dir-1",
            selected_files=[2, 5, 8],
            media={"media_id": media_id, "title": "Show", "year": 2024, "season_number": 1},
        ),
        created_at=datetime.now(),
        updated_at=datetime.now(),
        metadata=TorrentMetadata(hash="hash-1", name="Show", size=12, files=files),
    )


def _context(source_base: Path = Path("/downloads")) -> TransferExecutionContext:
    return TransferExecutionContext(
        source_base_path=source_base,
        destination_base_path=Path("/library"),
        template_config=Template(
            dir_template="{title} ({year})/Season {season:00}",
            file_template="{title} - S{season:00}E{episode:00}",
        ),
        title="Show",
        year=2024,
        season_number=1,
        selected_indices={2, 5, 8},
    )


def _status(save_path: Path) -> TorrentStatus:
    return TorrentStatus(
        hash="hash-1",
        name="Show",
        size=12,
        progress=0.8,
        state=TorrentState.DOWNLOADING,
        files_readable=True,
        downloader_id="downloader-1",
        save_path=str(save_path),
    )


@pytest.mark.asyncio
async def test_ready_episode_batch_groups_video_files_from_same_inspection_and_ignores_sidecars(monkeypatch, tmp_path):
    task = _task()
    root = tmp_path / "Show"
    root.mkdir()
    for name in ("Show.S01E01.mkv", "Show.S01E02.mkv", "Show.S01E02.zh.srt"):
        (root / name).write_bytes(b"data")
    live_files = [
        DownloadFileInfo(index=2, name="Show/Show.S01E01.mkv", size=4, progress=1.0, priority=1),
        DownloadFileInfo(index=5, name="Show/Show.S01E02.mkv", size=4, progress=1.0, priority=1),
        DownloadFileInfo(index=8, name="Show/Show.S01E02.zh.srt", size=4, progress=1.0, priority=1),
    ]
    monkeypatch.setattr(
        "app.services.domain.transfer.episode_batch.build_transfer_planning_context",
        AsyncMock(return_value=_context(tmp_path)),
    )
    monkeypatch.setattr(
        "app.services.domain.transfer.episode_batch.has_episode_target_collisions",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(
        "app.services.domain.transfer.episode_batch.download_service.get_task_torrent_files",
        AsyncMock(return_value=live_files),
    )

    assert await find_ready_episode_file_indices(task, _status(tmp_path)) == [2, 5]


@pytest.mark.asyncio
async def test_scheduler_creates_one_command_for_the_inspection_batch(monkeypatch):
    task = _task()
    monkeypatch.setattr(
        "app.services.application.workflows.scheduled_transfer.service.download_service.get_tasks",
        AsyncMock(return_value=[task]),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.scheduled_transfer.service.download_service.get_torrent_status_by_tasks",
        AsyncMock(return_value={task.id: _status(Path("/downloads"))}),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.scheduled_transfer.service.find_ready_episode_file_indices",
        AsyncMock(return_value=[2, 5]),
    )
    create = AsyncMock(return_value=object())
    monkeypatch.setattr(
        "app.services.application.workflows.scheduled_transfer.service.command_service.create_command",
        create,
    )

    result = await scheduled_transfer_command_service.enqueue_ready_episode_batches()

    assert result.completed == 1
    request = create.await_args.args[0]
    assert request.payload.file_indices == [2, 5]


@pytest.mark.asyncio
async def test_command_recheck_does_not_expand_beyond_captured_inspection(monkeypatch):
    task = _task()
    monkeypatch.setattr(
        "app.services.domain.transfer.service.download_service.find_task_by_id",
        AsyncMock(return_value=task),
    )
    monkeypatch.setattr(
        "app.services.domain.transfer.service.download_service.get_torrent_status_by_tasks",
        AsyncMock(return_value={task.id: _status(Path("/downloads"))}),
    )
    monkeypatch.setattr(
        "app.services.domain.transfer.service.find_ready_episode_file_indices",
        AsyncMock(return_value=[2, 5, 9]),
    )
    perform = AsyncMock(return_value=SimpleNamespace(transferred_files=[]))
    monkeypatch.setattr(transfer_service, "_perform_episode_batch", perform)

    await transfer_service.import_episode_batch(task.id, [2, 5])

    assert perform.await_args.args[1] == {2, 5}


@pytest.mark.asyncio
async def test_finished_task_only_imports_remaining_selected_files(monkeypatch):
    task = _task(TaskStatus.FINISHED)
    task.context.imported_file_indices = [2]
    monkeypatch.setattr(transfer_service, "_lock_task_status", AsyncMock())
    perform = AsyncMock(return_value=SimpleNamespace(transferred_files=[]))
    monkeypatch.setattr(transfer_service, "_perform_episode_batch", perform)

    await transfer_service._finish_episode_batches(task)

    assert perform.await_args.args[1] == {5, 8}
    assert perform.await_args.kwargs["completes_task"] is True


def test_completed_event_contains_one_batch_with_both_episodes():
    task = _task()
    results = [
        TransferFileResult(
            source_path=f"/downloads/e{episode}.mkv",
            destination_path=f"/library/Show - S01E{episode:02d}.mkv",
            file_item=task.metadata.files[index],
            file_index=task.metadata.files[index].index,
            episode_number=episode,
            episode_numbers=[episode],
        )
        for index, episode in ((0, 1), (1, 2))
    ]

    event = build_media_import_completed_event(task, results)

    assert event is not None
    assert [item["episode_number"] for item in json.loads(event.meta)["imported_files"]] == [1, 2]


@pytest.mark.asyncio
async def test_target_collision_disables_early_import(monkeypatch):
    task = _task()
    monkeypatch.setattr(
        "app.services.domain.transfer.episode_batch.library_target_path_policy.build_destination_path",
        lambda **kwargs: Path("/library/same.mkv"),
    )

    assert await has_episode_target_collisions(task, _context()) is True


def _library_file(file_id: str, episodes: list[int], resolution: str, task_id: str) -> LibraryFile:
    return LibraryFile(
        id=file_id,
        task_id=task_id,
        directory_id="dir-1",
        media_id=MediaID.parse("tmdb:tv:1"),
        path="TV/Show/Season 01",
        file_name=f"{file_id}.mkv",
        file_size=100,
        file_index=0,
        created_at=0,
        resource_attributes=ResourceAttributes(seasons=[1], episodes=episodes, resolution=resolution),
    )


@pytest.mark.asyncio
async def test_combined_old_file_waits_until_every_episode_has_equal_or_better_coverage(monkeypatch):
    task = _task()
    old = _library_file("old-e1-e2", [1, 2], "1080p", "old-task")
    imported_e1 = _library_file("new-e1", [1], "2160p", task.id)
    batch_e2 = TransferFileResult(
        source_path="/downloads/e2.mkv",
        destination_path="/library/e2.mkv",
        file_item=task.metadata.files[1],
        file_index=5,
        episode_number=2,
        episode_numbers=[2],
    )
    episodes = [
        LibraryEpisode(media_id=task.media_id, season=1, episode=1, file_id="old-e1-e2", created_at=0),
        LibraryEpisode(media_id=task.media_id, season=1, episode=2, file_id="old-e1-e2", created_at=0),
        LibraryEpisode(media_id=task.media_id, season=1, episode=1, file_id="new-e1", created_at=0),
    ]
    monkeypatch.setattr(
        "app.services.domain.transfer.replacement.library_service.get_episodes_by_media",
        AsyncMock(return_value=episodes),
    )
    monkeypatch.setattr(
        "app.services.domain.transfer.replacement.library_service.get_files_by_task",
        AsyncMock(return_value=[]),
    )

    assert await library_replacement_policy.keep_complete_episode_replacements(
        task, [batch_e2], [old], 1
    ) == []

    monkeypatch.setattr(
        "app.services.domain.transfer.replacement.library_service.get_files_by_task",
        AsyncMock(return_value=[imported_e1]),
    )
    monkeypatch.setattr(
        "app.services.domain.transfer.replacement.library_service.file_exists",
        lambda item: True,
    )
    assert await library_replacement_policy.keep_complete_episode_replacements(
        task, [batch_e2], [old], 1
    ) == [old]
