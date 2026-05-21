import os
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

pytestmark = [pytest.mark.drift, pytest.mark.health]

os.environ.setdefault("DATA_PATH", f"/tmp/aethera-test-data-{uuid.uuid4()}")

from app.schemas.media_id import MediaID
from app.schemas.domain.download import TaskContext, TaskData, TaskStatus
from app.schemas.domain.library import LibraryTaskFileHealth
from app.schemas.domain.torrent_status import TorrentState, TorrentStatus
from app.services.domain.download.task_runtime_service import TaskRuntimeService


class _FakeRepo:
    def __init__(self, task: TaskData | None) -> None:
        self.task = task

    async def find_by_id(self, task_id: str) -> TaskData | None:
        if self.task and self.task.id == task_id:
            return self.task
        return None

    async def update_fields(self, fields, cond: str) -> bool:
        return True

    def cond_id(self, task_id: str) -> str:
        return task_id


class _FakeClientFactory:
    def __init__(self, torrent_info=None, torrent_statuses=None, exc: Exception | None = None) -> None:
        self.torrent_info = torrent_info
        self.torrent_statuses = torrent_statuses or []
        self.exc = exc

    def get_download_client(self, downloader_id: str | None = None):
        factory = self

        class _Client:
            async def get_torrent_info(self, torrent_hash: str):
                if factory.exc:
                    raise factory.exc
                return factory.torrent_info

            async def get_torrents(self, hashes: list[str]):
                if factory.exc:
                    raise factory.exc
                return list(factory.torrent_statuses)

        return _Client()


def _task(
    task_id: str = "task-1",
    status: TaskStatus = TaskStatus.COMPLETED,
    downloader_id: str | None = "downloader-1",
    updated_at: datetime | None = None,
) -> TaskData:
    media = MediaID.parse("tmdb:tv:1")
    return TaskData(
        id=task_id,
        torrent_hash="abc123",
        media_id=media,
        status=status,
        downloader_id=downloader_id,
        context=TaskContext(
            download_url="https://example.com/file.torrent",
            directory_id="dir-1",
            media={"media_id": media, "title": "Test Show", "year": 2024},
        ),
        created_at=datetime.now(),
        updated_at=updated_at or datetime.now(),
    )


@pytest.mark.asyncio
async def test_refresh_completed_task_health_marks_seeding_absent_when_task_exists_but_torrent_missing():
    task = _task(status=TaskStatus.COMPLETED)
    service = TaskRuntimeService(_FakeRepo(task), _FakeClientFactory(torrent_info=None))
    update_task_state = AsyncMock(return_value=True)
    resolve_library_health = AsyncMock(
        return_value=LibraryTaskFileHealth(total_primary_count=2, existing_primary_count=2)
    )

    updated = await service.refresh_completed_task_health(
        task.id,
        update_task_state,
        resolve_library_health,
    )

    assert updated is True
    update_task_state.assert_awaited_once_with(task.id, TaskStatus.SEEDING_ABSENT, None, None, None)


@pytest.mark.asyncio
async def test_refresh_completed_task_health_marks_file_missing_when_library_files_are_gone():
    task = _task(status=TaskStatus.PARTIAL_MISSING)
    service = TaskRuntimeService(_FakeRepo(task), _FakeClientFactory(torrent_info=object()))
    update_task_state = AsyncMock(return_value=True)
    resolve_library_health = AsyncMock(
        return_value=LibraryTaskFileHealth(total_primary_count=2, existing_primary_count=0)
    )

    updated = await service.refresh_completed_task_health(
        task.id,
        update_task_state,
        resolve_library_health,
    )

    assert updated is True
    update_task_state.assert_awaited_once_with(task.id, TaskStatus.FILE_MISSING, None, None, None)


@pytest.mark.asyncio
async def test_refresh_completed_task_health_degrades_safely_when_torrent_probe_fails():
    task = _task(status=TaskStatus.COMPLETED)
    service = TaskRuntimeService(_FakeRepo(task), _FakeClientFactory(exc=RuntimeError("client down")))
    update_task_state = AsyncMock(return_value=True)
    resolve_library_health = AsyncMock(
        return_value=LibraryTaskFileHealth(total_primary_count=2, existing_primary_count=2)
    )

    updated = await service.refresh_completed_task_health(
        task.id,
        update_task_state,
        resolve_library_health,
    )

    assert updated is False
    update_task_state.assert_not_awaited()


@pytest.mark.asyncio
async def test_sync_active_downloads_voids_downloading_task_when_torrent_disappears():
    task = _task(status=TaskStatus.DOWNLOADING)
    service = TaskRuntimeService(_FakeRepo(task), _FakeClientFactory(torrent_statuses=[]))
    update_task_state = AsyncMock(return_value=True)

    result = await service.sync_active_downloads(
        get_tasks_by_statuses=AsyncMock(return_value=[task]),
        update_task_state=update_task_state,
    )

    assert result.processed == 1
    assert result.updated == 1
    update_task_state.assert_awaited_once_with(task.id, TaskStatus.VOID, None, None, None)


@pytest.mark.asyncio
async def test_sync_active_downloads_marks_pending_task_as_downloading_when_progress_appears():
    task = _task(status=TaskStatus.PENDING)
    torrent = TorrentStatus(
        hash=task.torrent_hash,
        name="Torrent",
        size=100,
        progress=0.42,
        state=TorrentState.DOWNLOADING,
        downloader_id="downloader-1",
    )
    service = TaskRuntimeService(_FakeRepo(task), _FakeClientFactory(torrent_statuses=[torrent]))
    update_task_state = AsyncMock(return_value=True)

    result = await service.sync_active_downloads(
        get_tasks_by_statuses=AsyncMock(return_value=[task]),
        update_task_state=update_task_state,
    )

    assert result.processed == 1
    assert result.updated == 1
    update_task_state.assert_awaited_once_with(task.id, TaskStatus.DOWNLOADING, None, 0.42, None)


@pytest.mark.asyncio
async def test_recover_stuck_transferring_tasks_force_recovers_all_transferring_tasks():
    task = _task(status=TaskStatus.TRANSFERRING)
    service = TaskRuntimeService(_FakeRepo(task), _FakeClientFactory())
    update_task_state = AsyncMock(return_value=True)

    recovered = await service.recover_stuck_transferring_tasks(
        get_tasks=AsyncMock(return_value=[task]),
        update_task_state=update_task_state,
        force=True,
    )

    assert recovered == 1
    update_task_state.assert_awaited_once_with(
        task.id,
        TaskStatus.FINISHED,
        None,
        None,
        None,
    )


@pytest.mark.asyncio
async def test_recover_stuck_transferring_tasks_skips_recent_tasks_without_force():
    task = _task(status=TaskStatus.TRANSFERRING, updated_at=datetime.now())
    service = TaskRuntimeService(_FakeRepo(task), _FakeClientFactory())
    update_task_state = AsyncMock(return_value=True)

    recovered = await service.recover_stuck_transferring_tasks(
        get_tasks=AsyncMock(return_value=[task]),
        update_task_state=update_task_state,
        force=False,
        timeout_seconds=1800,
    )

    assert recovered == 0
    update_task_state.assert_not_awaited()


@pytest.mark.asyncio
async def test_recover_stuck_transferring_tasks_recovers_timed_out_tasks():
    task = _task(status=TaskStatus.TRANSFERRING, updated_at=datetime.now() - timedelta(seconds=1801))
    service = TaskRuntimeService(_FakeRepo(task), _FakeClientFactory())
    update_task_state = AsyncMock(return_value=True)

    recovered = await service.recover_stuck_transferring_tasks(
        get_tasks=AsyncMock(return_value=[task]),
        update_task_state=update_task_state,
        force=False,
        timeout_seconds=1800,
    )

    assert recovered == 1
    update_task_state.assert_awaited_once()
