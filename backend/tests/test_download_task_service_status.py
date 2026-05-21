from datetime import datetime

import pytest

from app.schemas.config import DirectoryConfig
from app.schemas.domain.download import DownloadInfo, TaskContext, TaskData, TaskStatus
from app.schemas.domain.torrent_status import TorrentState, TorrentStatus
from app.schemas.exception.exceptions import DownloadException
from app.schemas.media_id import MediaID
from app.services.domain.download.tasks import DownloadTaskService
from app.services.integration.download.client import DownloadClientCapabilities


class _FakeRepo:
    def __init__(self, tasks: list[TaskData]) -> None:
        self.tasks = {task.id: task for task in tasks}

    async def find_by_ids(self, task_ids: list[str]) -> list[TaskData]:
        return [self.tasks[task_id] for task_id in task_ids if task_id in self.tasks]

    async def find_by_id(self, task_id: str) -> TaskData | None:
        return self.tasks.get(task_id)

    async def delete_by_id(self, task_id: str) -> bool:
        return self.tasks.pop(task_id, None) is not None


class _FakeClient:
    def __init__(
        self,
        statuses: list[TorrentStatus],
        *,
        info: DownloadInfo | None = None,
        capabilities: DownloadClientCapabilities | None = None,
        delete_result: bool = True,
        on_delete=None,
    ) -> None:
        self.statuses = statuses
        self.info = info
        self._capabilities = capabilities or DownloadClientCapabilities()
        self._delete_result = delete_result
        self._on_delete = on_delete
        self.requested_hashes: list[list[str]] = []
        self.deleted: list[tuple[str, bool]] = []

    async def get_torrents(self, hashes: list[str]) -> list[TorrentStatus]:
        self.requested_hashes.append(list(hashes))
        requested = {item.lower() for item in hashes}
        return [status for status in self.statuses if status.hash.lower() in requested]

    async def get_torrent_info(self, torrent_hash: str) -> DownloadInfo | None:
        return self.info if self.info and self.info.hash == torrent_hash else None

    async def delete_torrent(self, torrent_hash: str, delete_files: bool = False) -> bool:
        self.deleted.append((torrent_hash, delete_files))
        if self._on_delete:
            self._on_delete()
        return self._delete_result

    def capabilities(self) -> DownloadClientCapabilities:
        return self._capabilities


class _FakeClientFactory:
    def __init__(self, client: _FakeClient) -> None:
        self.client = client

    def get_download_client(self, downloader_id=None):
        return self.client


def _task(task_id: str) -> TaskData:
    media_id = MediaID.parse(f"tmdb:tv:{task_id[-1]}")
    return TaskData(
        id=task_id,
        torrent_hash="shared-hash",
        media_id=media_id,
        status=TaskStatus.DOWNLOADING,
        downloader_id="downloader-1",
        context=TaskContext(
            download_url="https://example.invalid/torrent",
            directory_id="dir-1",
            media={"media_id": media_id, "title": "Show", "year": 2026},
        ),
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


@pytest.mark.asyncio
async def test_get_torrent_status_by_task_ids_assigns_shared_hash_status_to_all_matching_tasks():
    task_a = _task("task-1")
    task_b = _task("task-2")
    status = TorrentStatus(
        hash="shared-hash",
        name="Shared",
        size=100,
        progress=0.5,
        state=TorrentState.DOWNLOADING,
        downloader_id="downloader-1",
    )
    client = _FakeClient([status])
    service = DownloadTaskService(
        _FakeRepo([task_a, task_b]),
        _FakeClientFactory(client),
        downloader_display_map_provider=lambda: {},
        refresh_completed_task_health=lambda *_: None,
    )

    result = await service.get_torrent_status_by_task_ids([task_a.id, task_b.id])

    assert result == {task_a.id: status, task_b.id: status}
    assert client.requested_hashes == [["shared-hash"]]


@pytest.mark.asyncio
async def test_delete_task_uses_aethera_managed_download_file_delete(monkeypatch, tmp_path):
    download_root = tmp_path / "downloads"
    content_path = download_root / "Movie.mkv"
    content_path.parent.mkdir()
    content_path.write_text("movie", encoding="utf-8")
    task = _task("task-1")
    info = DownloadInfo(
        hash=task.torrent_hash,
        name="Movie",
        size=content_path.stat().st_size,
        progress=1.0,
        state="seeding",
        save_path=str(download_root),
        content_path=str(content_path),
        added_on=datetime.now(),
    )

    def assert_content_not_deleted_before_downloader_delete():
        assert content_path.exists()

    client = _FakeClient(
        [],
        info=info,
        capabilities=DownloadClientCapabilities(delete_files_requires_aethera=True),
        on_delete=assert_content_not_deleted_before_downloader_delete,
    )
    monkeypatch.setattr(
        "app.services.domain.download.download_file_ops.settings_service.get_directory_by_id",
        lambda directory_id: DirectoryConfig(id=directory_id, download_path=str(download_root)),
    )
    service = DownloadTaskService(
        _FakeRepo([task]),
        _FakeClientFactory(client),
        downloader_display_map_provider=lambda: {},
        refresh_completed_task_health=lambda *_: None,
    )

    deleted = await service.delete_task(task.id, delete_files=True)

    assert deleted is True
    assert not content_path.exists()
    assert client.deleted == [(task.torrent_hash, False)]


@pytest.mark.asyncio
async def test_delete_task_refuses_aethera_managed_delete_without_content_path(monkeypatch, tmp_path):
    download_root = tmp_path / "downloads"
    unrelated_path = download_root / "Other.mkv"
    unrelated_path.parent.mkdir()
    unrelated_path.write_text("other", encoding="utf-8")
    task = _task("task-1")
    info = DownloadInfo(
        hash=task.torrent_hash,
        name="Movie",
        size=1,
        progress=1.0,
        state="seeding",
        save_path=str(download_root),
        content_path="",
        added_on=datetime.now(),
    )
    client = _FakeClient(
        [],
        info=info,
        capabilities=DownloadClientCapabilities(delete_files_requires_aethera=True),
    )
    monkeypatch.setattr(
        "app.services.domain.download.download_file_ops.settings_service.get_directory_by_id",
        lambda directory_id: DirectoryConfig(id=directory_id, download_path=str(download_root)),
    )
    service = DownloadTaskService(
        _FakeRepo([task]),
        _FakeClientFactory(client),
        downloader_display_map_provider=lambda: {},
        refresh_completed_task_health=lambda *_: None,
    )

    with pytest.raises(DownloadException) as exc_info:
        await service.delete_task(task.id, delete_files=True)

    assert exc_info.value.message_key == "backendErrors.downloaderDeleteFilesUnsupported"
    assert unrelated_path.exists()
    assert client.deleted == []


@pytest.mark.asyncio
async def test_delete_task_keeps_aethera_managed_files_when_downloader_delete_fails(monkeypatch, tmp_path):
    download_root = tmp_path / "downloads"
    content_path = download_root / "Movie.mkv"
    content_path.parent.mkdir()
    content_path.write_text("movie", encoding="utf-8")
    task = _task("task-1")
    repo = _FakeRepo([task])
    info = DownloadInfo(
        hash=task.torrent_hash,
        name="Movie",
        size=content_path.stat().st_size,
        progress=1.0,
        state="seeding",
        save_path=str(download_root),
        content_path=str(content_path),
        added_on=datetime.now(),
    )
    client = _FakeClient(
        [],
        info=info,
        capabilities=DownloadClientCapabilities(delete_files_requires_aethera=True),
        delete_result=False,
    )
    monkeypatch.setattr(
        "app.services.domain.download.download_file_ops.settings_service.get_directory_by_id",
        lambda directory_id: DirectoryConfig(id=directory_id, download_path=str(download_root)),
    )
    service = DownloadTaskService(
        repo,
        _FakeClientFactory(client),
        downloader_display_map_provider=lambda: {},
        refresh_completed_task_health=lambda *_: None,
    )

    with pytest.raises(DownloadException) as exc_info:
        await service.delete_task(task.id, delete_files=True)

    assert exc_info.value.message_key == "backendErrors.downloaderDeleteFailed"
    assert content_path.exists()
    assert task.id in repo.tasks
    assert client.deleted == [(task.torrent_hash, False)]
