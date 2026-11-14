from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.schemas.domain.command import CommandCreateRequest
from app.schemas.domain.download import DownloadFileInfo, DownloadTaskCreateInput, TaskContext, TaskData, TaskStatus
from app.schemas.domain.media import MediaExecutionSnapshot
from app.schemas.domain.resource_attributes import ResourceAttributes
from app.schemas.domain.torrent import TorrentFileItem, TorrentMetadata
from app.schemas.media_id import MediaID
from app.services.domain.download.episode_selection import (
    available_episodes,
    episodes_for_file_indices,
    resolve_episode_selection,
)
from app.services.domain.download.episode_selection_service import TaskEpisodeSelectionService


def _metadata() -> TorrentMetadata:
    return TorrentMetadata(
        hash="torrent-hash",
        name="Season 1",
        size=300,
        attrs=ResourceAttributes(seasons=[1]),
        files=[
            TorrentFileItem(index=0, filename="S01E01.mkv", size=100, attrs=ResourceAttributes(seasons=[1], episodes=[1])),
            TorrentFileItem(index=1, filename="S01E02-E03.mkv", size=100, attrs=ResourceAttributes(seasons=[1], episodes=[2, 3])),
            TorrentFileItem(index=2, filename="S01E04.mkv", size=100, attrs=ResourceAttributes(seasons=[1], episodes=[4])),
            TorrentFileItem(index=3, filename="sample.mkv", size=10, attrs=ResourceAttributes(episodes=[])),
        ],
    )


def _task(*, selected_files: list[int], imported_files: list[int] | None = None) -> TaskData:
    media = MediaExecutionSnapshot(
        media_id=MediaID.parse("tmdb:tv:1"),
        title="Example",
        year=2026,
        season_number=1,
        episodes_count=4,
    )
    return TaskData(
        id="task-1",
        media_id=media.media_id,
        torrent_hash="torrent-hash",
        status=TaskStatus.DOWNLOADING,
        downloader_id="qb",
        context=TaskContext(
            download_url="https://example.invalid/torrent",
            media=media,
            directory_id="tv",
            selected_files=selected_files,
            imported_file_indices=imported_files or [],
        ),
        metadata=_metadata(),
    )


def test_episode_selection_maps_multi_episode_files_without_exposing_unmapped_files():
    metadata = _metadata()

    assert available_episodes(metadata, 1) == [1, 2, 3, 4]
    assert resolve_episode_selection(metadata, 1, [2]) == ([1], [2, 3])
    assert episodes_for_file_indices(metadata, [3]) == []


def test_task_create_command_preserves_episode_selection():
    task = _task(selected_files=[])
    request = DownloadTaskCreateInput(
        media=task.context.media,
        directory_id="tv",
        result_id="result-1",
        selected_episodes=[2, 3],
    )

    command = CommandCreateRequest.from_task_create_input(request)

    assert command.payload.selected_episodes == [2, 3]


class _Repo:
    def __init__(self, task: TaskData, siblings: list[TaskData] | None = None) -> None:
        self.task = task
        self.siblings = siblings or []
        self.updated: TaskData | None = None

    async def find_by_id(self, task_id: str):
        return self.task if task_id == self.task.id else None

    async def find_by_hash_and_downloader(self, _torrent_hash: str, _downloader_id: str):
        return [self.task, *self.siblings]

    async def update_task(self, task: TaskData):
        self.updated = task.model_copy(deep=True)
        return True


class _Client:
    def __init__(self, *, fail_priority: int | None = None) -> None:
        self.calls: list[tuple[list[int], int]] = []
        self.fail_priority = fail_priority

    def capabilities(self):
        return SimpleNamespace(can_set_file_priority=True)

    async def get_torrent_files(self, _torrent_hash: str):
        return [
            DownloadFileInfo(index=index, name=f"file-{index}", size=100, progress=0.5, priority=1)
            for index in range(4)
        ]

    async def set_file_priority(self, _torrent_hash: str, indices: list[int], priority: int):
        self.calls.append((indices, priority))
        return priority != self.fail_priority


class _ClientFactory:
    def __init__(self, client: _Client) -> None:
        self.client = client

    def get_download_client(self, _downloader_id: str):
        return self.client


@pytest.mark.asyncio
async def test_task_episode_selection_keeps_imported_episodes_and_updates_downloader():
    task = _task(selected_files=[0, 1, 2], imported_files=[0])
    repo = _Repo(task)
    client = _Client()
    service = TaskEpisodeSelectionService(repo, _ClientFactory(client))

    view = await service.update(task.id, [4])

    assert repo.updated is not None
    assert repo.updated.context.selected_files == [0, 2]
    assert client.calls == [([1, 3], 0)]
    assert view.selected_episodes == [1, 4]
    assert view.locked_episodes == [1]


@pytest.mark.asyncio
async def test_task_episode_selection_preserves_files_selected_by_sibling_task():
    task = _task(selected_files=[0, 1, 2])
    sibling = _task(selected_files=[1])
    sibling.id = "task-2"
    repo = _Repo(task, [sibling])
    client = _Client()
    service = TaskEpisodeSelectionService(repo, _ClientFactory(client))

    await service.update(task.id, [4])

    assert client.calls == [([0, 3], 0)]
    assert repo.updated is not None
    assert repo.updated.context.selected_files == [2]
