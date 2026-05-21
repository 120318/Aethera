from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.schemas.config import DirectoryConfig, QBittorrentConfig
from app.schemas.constants.event_types import EventTypes
from app.schemas.domain.download import DownloadInfo, TaskContext, TaskData, TaskStatus
from app.schemas.domain.library import LibraryFile
from app.schemas.domain.media import MediaExecutionSnapshot
from app.schemas.domain.task_storage_migration import TaskStorageMigrationStatus
from app.schemas.domain.torrent import TorrentFileItem, TorrentMetadata
from app.schemas.media_id import MediaID
from app.services.integration.download.client import DownloadClientCapabilities
from app.services.domain.download.downloader_change import TaskDownloaderChangeRequest, TaskDownloaderChangeService
from app.services.domain.download.downloader_change_file_ops import move_content_if_needed, move_task_library_files
from app.services.domain.download.downloader_change_preview import (
    _resolve_target_content_path,
    _validate_hardlink_safe_move,
    build_change_preview,
    resolve_content_path,
)


class FakeRepo:
    def __init__(self, task):
        self.task = task
        self.updated = None

    async def find_by_id(self, task_id):
        return self.task if task_id == self.task.id else None

    async def update_task(self, task):
        self.updated = task.model_copy(deep=True)
        self.task = task
        return True


class FakeClient:
    def __init__(self, info):
        self.info = info
        self.paused = []
        self.started = []
        self.rechecked = []
        self.locations = []
        self.added = []
        self.deleted = []
        self.file_priorities = []

    async def get_torrent_info(self, torrent_hash):
        if not self.info:
            return None
        return self.info if torrent_hash == self.info.hash else None

    async def pause_torrents(self, hashes):
        self.paused.extend(hashes)
        return True

    async def start_torrents(self, hashes):
        self.started.extend(hashes)
        return True

    async def export_torrent(self, torrent_hash):
        return b"torrent"

    async def add_torrent_file(self, **kwargs):
        self.added.append(kwargs)
        return type("Result", (), {"success": True})()

    async def recheck_torrents(self, hashes):
        self.rechecked.extend(hashes)
        return True

    async def set_torrent_location(self, hashes, location):
        self.locations.append((list(hashes), location))
        if self.info:
            self.info.save_path = location
            self.info.content_path = str(Path(location) / self.info.name)
        return True

    async def set_file_priority(self, torrent_hash, file_ids, priority):
        self.file_priorities.append((torrent_hash, list(file_ids), priority))
        return True

    async def delete_torrent(self, torrent_hash, delete_files=False):
        self.deleted.append((torrent_hash, delete_files))
        return True

    def capabilities(self):
        return DownloadClientCapabilities()


class FakeLimitedClient(FakeClient):
    def __init__(self, info, capabilities):
        super().__init__(info)
        self._capabilities = capabilities

    def capabilities(self):
        return self._capabilities


class FakeAddFailClient(FakeClient):
    async def add_torrent_file(self, **kwargs):
        self.added.append(kwargs)
        return type("Result", (), {"success": False})()


class FakeDeleteFailClient(FakeClient):
    async def delete_torrent(self, torrent_hash, delete_files=False):
        self.deleted.append((torrent_hash, delete_files))
        return False


class FakePriorityFailClient(FakeClient):
    async def set_file_priority(self, torrent_hash, file_ids, priority):
        self.file_priorities.append((torrent_hash, list(file_ids), priority))
        return False


class FakeRecheckFailClient(FakeClient):
    async def recheck_torrents(self, hashes):
        self.rechecked.extend(hashes)
        return False


class FakeLocationFailClient(FakeClient):
    async def set_torrent_location(self, hashes, location):
        self.locations.append((list(hashes), location))
        return False


class FakeAddThenPriorityFailClient(FakePriorityFailClient):
    def __init__(self, added_info):
        super().__init__(None)
        self.added_info = added_info

    async def add_torrent_file(self, **kwargs):
        self.added.append(kwargs)
        self.info = self.added_info
        return type("Result", (), {"success": True})()


class FakePauseFailClient(FakeClient):
    async def pause_torrents(self, hashes):
        self.paused.extend(hashes)
        return False


class FakeMigrationRepo:
    def __init__(self):
        self.items = []

    async def find_active_by_task(self, task_id):
        return next((item for item in self.items if item.task_id == task_id and item.status in {TaskStorageMigrationStatus.PENDING, TaskStorageMigrationStatus.CHECKING}), None)

    async def insert(self, migration):
        self.items.append(migration)
        return migration

    async def update(self, migration):
        return migration

    async def list_active(self, limit=100):
        return [item for item in self.items if item.status in {TaskStorageMigrationStatus.PENDING, TaskStorageMigrationStatus.CHECKING}][:limit]


class FakeFactory:
    def __init__(self, clients):
        self.clients = clients

    def get_download_client(self, downloader_id):
        return self.clients[downloader_id]


def make_task(download_path):
    media = MediaExecutionSnapshot(media_id=MediaID.parse("tmdb:movie:1"), title="Movie", year=2024)
    return TaskData(
        id="task-1",
        media_id=media.media_id,
        torrent_hash="abc",
        status=TaskStatus.DOWNLOADING,
        progress=0.5,
        context=TaskContext(
            download_url="http://example/torrent",
            media=media,
            directory_id="dir-old",
            selected_files=[0],
        ),
        downloader_id="old",
        save_path=download_path,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        metadata=TorrentMetadata(
            hash="abc",
            name="Movie",
            size=20,
            files=[
                TorrentFileItem(index=0, filename="Movie.mkv", size=10),
                TorrentFileItem(index=1, filename="Extra.mkv", size=10),
            ],
        ),
    )


@pytest.mark.asyncio
async def test_change_task_downloader_pauses_source_and_updates_task(monkeypatch, tmp_path):
    save_path = str(tmp_path / "downloads")
    target_path = tmp_path / "target"
    target_path.mkdir()
    Path(save_path).write_text("movie", encoding="utf-8")
    task = make_task(save_path)
    repo = FakeRepo(task)
    source_info = DownloadInfo(
        hash="abc",
        name="Movie",
        size=10,
        progress=0.5,
        state="downloading",
        save_path=save_path,
        added_on=datetime.now(),
        content_path=save_path,
    )
    target_info = DownloadInfo(
        hash="abc",
        name="Movie",
        size=10,
        progress=0.5,
        state="pausedDL",
        save_path=str(target_path),
        added_on=datetime.now(),
        content_path=str(target_path / "Movie"),
    )
    source_client = FakeClient(source_info)
    target_client = FakeClient(target_info)
    service = TaskDownloaderChangeService(repo, FakeFactory({"old": source_client, "new": target_client}))
    service._migration_repo = FakeMigrationRepo()
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.settings_service.list_downloaders",
        lambda: [
            QBittorrentConfig(id="old", name="old", type="qbittorrent", url="http://old"),
            QBittorrentConfig(id="new", name="new", type="qbittorrent", url="http://new"),
        ],
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.settings_service.get_directory_by_id",
        lambda directory_id: DirectoryConfig(
            id=directory_id,
            name="Target",
            path=str(tmp_path / "library"),
            download_path=str(target_path),
            downloader_id="new",
        ),
    )

    async def no_library_files(task_id):
        return []

    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.library_service.get_files_by_task",
        no_library_files,
    )
    emitted_events = []
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_side_effects.event_service.emit_media",
        lambda event, meta=None: emitted_events.append((event, meta)),
    )
    action_updates = []
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_side_effects.action_service.create_action",
        lambda **kwargs: SimpleNamespace(id=kwargs["action_id"]),
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_side_effects.action_service.mark_completed",
        lambda action_id, **kwargs: action_updates.append(("completed", action_id)),
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_side_effects.action_service.mark_failed",
        lambda action_id, **kwargs: action_updates.append(("failed", action_id, kwargs.get("error"))),
    )

    result = await service.execute(
        "task-1",
        TaskDownloaderChangeRequest(
            target_downloader_id="new",
            target_directory_id="dir-new",
        ),
    )

    assert result.ok is True
    assert source_client.paused == ["abc"]
    assert target_client.file_priorities == [("abc", [1], 0), ("abc", [0], 1)]
    assert target_client.rechecked == ["abc"]
    assert target_client.started == []
    assert repo.updated.status == TaskStatus.MIGRATING
    assert repo.updated.downloader_id == "old"
    assert service._migration_repo.items[0].target_downloader_id == "new"
    assert service._migration_repo.items[0].action_id == f"storage-migration:{service._migration_repo.items[0].id}"
    assert len(emitted_events) == 1
    event, meta = emitted_events[0]
    assert event.type == EventTypes.DOWNLOAD_TASK_STORAGE_CHANGE_STARTED
    assert event.action_id == service._migration_repo.items[0].action_id
    assert event.message_params["source_downloader_id"] == "old"
    assert event.message_params["target_downloader_id"] == "new"
    assert meta.task_id == "task-1"

    target_path.joinpath("Movie").touch()
    target_client.info.progress = 1.0
    updated = await service.finalize_active_migrations()

    assert updated == 1
    assert repo.updated.downloader_id == "new"
    assert repo.updated.context.directory_id == "dir-new"
    assert repo.updated.save_path == str(target_path)
    assert repo.updated.status == TaskStatus.FINISHED
    assert target_client.started == ["abc"]
    assert source_client.deleted == [("abc", False)]
    assert service._migration_repo.items[0].status == TaskStorageMigrationStatus.FINALIZED
    assert action_updates == [("completed", service._migration_repo.items[0].action_id)]
    assert emitted_events[-1][0].type == EventTypes.DOWNLOAD_TASK_STORAGE_CHANGED
    assert emitted_events[-1][0].action_id == service._migration_repo.items[0].action_id


@pytest.mark.asyncio
async def test_change_task_downloader_accepts_existing_target_when_source_torrent_missing(monkeypatch, tmp_path):
    save_path = str(tmp_path / "downloads")
    target_path = tmp_path / "target"
    target_path.mkdir()
    target_path.joinpath("Movie").write_text("movie", encoding="utf-8")
    task = make_task(save_path)
    repo = FakeRepo(task)
    target_info = DownloadInfo(
        hash="abc",
        name="Movie",
        size=10,
        progress=0.5,
        state="downloading",
        save_path=str(target_path),
        added_on=datetime.now(),
        content_path=str(target_path / "Movie"),
    )
    source_client = FakePauseFailClient(None)
    target_client = FakeClient(target_info)
    service = TaskDownloaderChangeService(repo, FakeFactory({"old": source_client, "new": target_client}))
    service._migration_repo = FakeMigrationRepo()
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.settings_service.list_downloaders",
        lambda: [
            QBittorrentConfig(id="old", name="old", type="qbittorrent", url="http://old"),
            QBittorrentConfig(id="new", name="new", type="qbittorrent", url="http://new"),
        ],
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.settings_service.get_directory_by_id",
        lambda directory_id: DirectoryConfig(
            id=directory_id,
            name="Target",
            path=str(tmp_path / "library"),
            download_path=str(target_path),
            downloader_id="new",
        ),
    )

    async def no_library_files(task_id):
        return []

    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.library_service.get_files_by_task",
        no_library_files,
    )
    emitted_events = []
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_side_effects.event_service.emit_media",
        lambda event, meta=None: emitted_events.append((event, meta)),
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_side_effects.action_service.create_action",
        lambda **kwargs: SimpleNamespace(id=kwargs["action_id"]),
    )

    result = await service.execute(
        "task-1",
        TaskDownloaderChangeRequest(
            target_downloader_id="new",
            target_directory_id="dir-new",
        ),
    )

    assert result.ok is True
    assert source_client.paused == []
    assert target_client.file_priorities == [("abc", [1], 0), ("abc", [0], 1)]
    assert target_client.rechecked == ["abc"]
    assert repo.updated.status == TaskStatus.MIGRATING
    assert service._migration_repo.items[0].target_downloader_id == "new"


@pytest.mark.asyncio
async def test_change_task_downloader_supports_same_downloader_directory_move(monkeypatch, tmp_path):
    save_path = str(tmp_path / "downloads")
    target_path = tmp_path / "target"
    target_path.mkdir()
    source_file = Path(save_path)
    source_file.write_text("movie", encoding="utf-8")
    task = make_task(save_path)
    repo = FakeRepo(task)
    torrent_info = DownloadInfo(
        hash="abc",
        name="Movie",
        size=10,
        progress=0.5,
        state="downloading",
        save_path=save_path,
        added_on=datetime.now(),
        content_path=save_path,
    )
    client = FakeClient(torrent_info)
    service = TaskDownloaderChangeService(repo, FakeFactory({"old": client}))
    service._migration_repo = FakeMigrationRepo()
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.settings_service.list_downloaders",
        lambda: [
            QBittorrentConfig(id="old", name="old", type="qbittorrent", url="http://old"),
        ],
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.settings_service.get_directory_by_id",
        lambda directory_id: DirectoryConfig(
            id=directory_id,
            name="Target",
            path=str(tmp_path / "library"),
            download_path=str(target_path),
            downloader_id="old",
        ),
    )

    async def no_library_files(task_id):
        return []

    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.library_service.get_files_by_task",
        no_library_files,
    )
    emitted_events = []
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_side_effects.event_service.emit_media",
        lambda event, meta=None: emitted_events.append((event, meta)),
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_side_effects.action_service.create_action",
        lambda **kwargs: SimpleNamespace(id=kwargs["action_id"]),
    )

    preview = await service.preview(
        "task-1",
        TaskDownloaderChangeRequest(target_downloader_id="old", target_directory_id="dir-new"),
    )
    result = await service.execute(
        "task-1",
        TaskDownloaderChangeRequest(target_downloader_id="old", target_directory_id="dir-new"),
    )

    assert preview.ok is True
    assert "target_torrent_save_path_conflict" not in preview.blockers
    assert preview.move_content is False
    assert preview.target_content_path == str(target_path / source_file.name)
    assert result.ok is True
    assert source_file.exists()
    assert not target_path.joinpath("Movie").exists()
    assert client.paused == ["abc"]
    assert client.locations == [(["abc"], str(target_path))]
    assert client.rechecked == ["abc"]
    assert repo.updated.status == TaskStatus.MIGRATING


@pytest.mark.asyncio
async def test_preview_blocks_when_source_cannot_export_missing_target(monkeypatch, tmp_path):
    save_path = str(tmp_path / "downloads")
    target_path = tmp_path / "target"
    target_path.mkdir()
    task = make_task(save_path)
    source_info = DownloadInfo(
        hash="abc",
        name="Movie",
        size=10,
        progress=0.5,
        state="downloading",
        save_path=save_path,
        added_on=datetime.now(),
        content_path=save_path,
    )
    source = FakeLimitedClient(source_info, DownloadClientCapabilities(can_export_torrent=False))
    target = FakeClient(None)

    async def no_library_files(task_id):
        return []

    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_preview.library_service.get_files_by_task",
        no_library_files,
    )

    preview = await build_change_preview(
        task=task,
        target_downloader=QBittorrentConfig(id="new", name="new", type="qbittorrent", url="http://new"),
        target_directory=DirectoryConfig(id="dir-new", name="Target", path=str(tmp_path / "library"), download_path=str(target_path)),
        source_client=source,
        target_client=target,
    )

    assert preview.ok is False
    assert "source_downloader_export_unsupported" in preview.blockers


@pytest.mark.asyncio
async def test_preview_allows_missing_target_when_stored_torrent_exists(monkeypatch, tmp_path):
    save_path = str(tmp_path / "downloads")
    target_path = tmp_path / "target"
    target_path.mkdir()
    task = make_task(save_path)
    source_info = DownloadInfo(
        hash="abc",
        name="Movie",
        size=10,
        progress=0.5,
        state="downloading",
        save_path=save_path,
        added_on=datetime.now(),
        content_path=save_path,
    )
    source = FakeLimitedClient(source_info, DownloadClientCapabilities(can_export_torrent=False))
    target = FakeClient(None)

    async def no_library_files(task_id):
        return []

    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_preview.library_service.get_files_by_task",
        no_library_files,
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_preview.torrent_service.load_stored_blob",
        lambda torrent_hash: b"stored-torrent",
    )

    preview = await build_change_preview(
        task=task,
        target_downloader=QBittorrentConfig(id="new", name="new", type="qbittorrent", url="http://new"),
        target_directory=DirectoryConfig(id="dir-new", name="Target", path=str(tmp_path / "library"), download_path=str(target_path)),
        source_client=source,
        target_client=target,
    )

    assert preview.ok is True
    assert "source_downloader_export_unsupported" not in preview.blockers


@pytest.mark.asyncio
async def test_preview_blocks_same_downloader_location_change_when_unsupported(monkeypatch, tmp_path):
    save_path = str(tmp_path / "downloads")
    target_path = tmp_path / "target"
    target_path.mkdir()
    task = make_task(save_path)
    source_info = DownloadInfo(
        hash="abc",
        name="Movie",
        size=10,
        progress=0.5,
        state="downloading",
        save_path=save_path,
        added_on=datetime.now(),
        content_path=save_path,
    )
    client = FakeLimitedClient(source_info, DownloadClientCapabilities(can_set_location=False))

    async def no_library_files(task_id):
        return []

    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_preview.library_service.get_files_by_task",
        no_library_files,
    )

    preview = await build_change_preview(
        task=task,
        target_downloader=QBittorrentConfig(id="old", name="old", type="qbittorrent", url="http://old"),
        target_directory=DirectoryConfig(id="dir-new", name="Target", path=str(tmp_path / "library"), download_path=str(target_path)),
        source_client=client,
        target_client=client,
    )

    assert preview.ok is False
    assert "target_downloader_location_change_unsupported" in preview.blockers


@pytest.mark.asyncio
async def test_preview_keeps_move_content_for_aethera_managed_location_change(monkeypatch, tmp_path):
    save_path = str(tmp_path / "downloads")
    target_path = tmp_path / "target"
    target_path.mkdir()
    task = make_task(save_path)
    source_info = DownloadInfo(
        hash="abc",
        name="Movie",
        size=10,
        progress=0.5,
        state="downloading",
        save_path=save_path,
        added_on=datetime.now(),
        content_path=save_path,
    )
    client = FakeLimitedClient(
        source_info,
        DownloadClientCapabilities(location_update_requires_aethera_move=True),
    )

    async def no_library_files(task_id):
        return []

    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_preview.library_service.get_files_by_task",
        no_library_files,
    )

    preview = await build_change_preview(
        task=task,
        target_downloader=QBittorrentConfig(id="old", name="old", type="qbittorrent", url="http://old"),
        target_directory=DirectoryConfig(id="dir-new", name="Target", path=str(tmp_path / "library"), download_path=str(target_path)),
        source_client=client,
        target_client=client,
    )

    assert preview.ok is True
    assert preview.move_content is True
    assert preview.target_content_path == str(target_path / "downloads")


@pytest.mark.asyncio
async def test_same_downloader_recheck_failure_restores_relative_source_location(monkeypatch, tmp_path):
    download_root = tmp_path / "download-root"
    source_relative_path = "movie/source"
    source_path = download_root / source_relative_path
    target_path = tmp_path / "target"
    source_path.parent.mkdir(parents=True)
    target_path.mkdir()
    source_path.write_text("movie", encoding="utf-8")
    task = make_task(source_relative_path)
    repo = FakeRepo(task)
    torrent_info = DownloadInfo(
        hash="abc",
        name="Movie",
        size=10,
        progress=0.5,
        state="downloading",
        save_path=str(source_path),
        added_on=datetime.now(),
        content_path=str(source_path),
    )
    client = FakeRecheckFailClient(torrent_info)
    service = TaskDownloaderChangeService(repo, FakeFactory({"old": client}))
    service._migration_repo = FakeMigrationRepo()
    service._recovery._migration_repo = service._migration_repo
    monkeypatch.setattr("app.utils.library_paths.get_download_root", lambda: download_root)
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.settings_service.list_downloaders",
        lambda: [
            QBittorrentConfig(id="old", name="old", type="qbittorrent", url="http://old"),
        ],
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.settings_service.get_directory_by_id",
        lambda directory_id: DirectoryConfig(
            id=directory_id,
            name="Target",
            path=str(tmp_path / "library"),
            download_path=str(target_path),
            downloader_id="old",
        ),
    )

    async def no_library_files(task_id):
        return []

    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.library_service.get_files_by_task",
        no_library_files,
    )
    emitted_events = []
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_side_effects.event_service.emit_media",
        lambda event, meta=None: emitted_events.append((event, meta)),
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_side_effects.action_service.create_action",
        lambda **kwargs: SimpleNamespace(id=kwargs["action_id"]),
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_side_effects.action_service.mark_failed",
        lambda action_id, **kwargs: None,
    )

    result = await service.execute(
        "task-1",
        TaskDownloaderChangeRequest(target_downloader_id="old", target_directory_id="dir-new"),
    )

    assert result.ok is False
    assert "target_recheck_failed" in result.blockers
    assert client.locations == [(["abc"], str(target_path)), (["abc"], str(source_path.resolve(strict=False)))]
    assert service._migration_repo.items[0].status == TaskStorageMigrationStatus.FAILED
    assert service._migration_repo.items[0].reason == "target_recheck_failed"


@pytest.mark.asyncio
async def test_change_task_downloader_rolls_back_when_target_recheck_fails(monkeypatch, tmp_path):
    save_path = str(tmp_path / "downloads")
    target_path = tmp_path / "target"
    target_path.mkdir()
    source_file = Path(save_path)
    source_file.write_text("movie", encoding="utf-8")
    task = make_task(save_path)
    repo = FakeRepo(task)
    source_info = DownloadInfo(
        hash="abc",
        name="Movie",
        size=10,
        progress=0.5,
        state="downloading",
        save_path=save_path,
        added_on=datetime.now(),
        content_path=save_path,
    )
    target_info = DownloadInfo(
        hash="abc",
        name="Movie",
        size=10,
        progress=0.0,
        state="pausedDL",
        save_path=str(target_path),
        added_on=datetime.now(),
        content_path=str(target_path / "Movie"),
    )
    source_client = FakeClient(source_info)
    target_client = FakeRecheckFailClient(target_info)
    service = TaskDownloaderChangeService(repo, FakeFactory({"old": source_client, "new": target_client}))
    service._migration_repo = FakeMigrationRepo()
    service._recovery._migration_repo = service._migration_repo
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.settings_service.list_downloaders",
        lambda: [
            QBittorrentConfig(id="old", name="old", type="qbittorrent", url="http://old"),
            QBittorrentConfig(id="new", name="new", type="qbittorrent", url="http://new"),
        ],
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.settings_service.get_directory_by_id",
        lambda directory_id: DirectoryConfig(
            id=directory_id,
            name="Target",
            path=str(tmp_path / "library"),
            download_path=str(target_path),
            downloader_id="new",
        ),
    )

    async def no_library_files(task_id):
        return []

    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.library_service.get_files_by_task",
        no_library_files,
    )
    emitted_events = []
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_side_effects.event_service.emit_media",
        lambda event, meta=None: emitted_events.append((event, meta)),
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_side_effects.action_service.create_action",
        lambda **kwargs: SimpleNamespace(id=kwargs["action_id"]),
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_side_effects.action_service.mark_failed",
        lambda action_id, **kwargs: None,
    )

    result = await service.execute(
        "task-1",
        TaskDownloaderChangeRequest(
            target_downloader_id="new",
            target_directory_id="dir-new",
        ),
    )

    assert result.ok is False
    assert "target_recheck_failed" in result.blockers
    assert source_file.exists()
    assert not target_path.joinpath("Movie").exists()
    assert repo.task.status == TaskStatus.DOWNLOADING
    assert source_client.started == ["abc"]
    assert target_client.rechecked == ["abc"]
    assert service._migration_repo.items[0].status == TaskStorageMigrationStatus.FAILED
    assert service._migration_repo.items[0].reason == "target_recheck_failed"
    failed_events = [event for event, _meta in emitted_events if event.type == EventTypes.DOWNLOAD_TASK_STORAGE_CHANGE_FAILED]
    assert len(failed_events) == 1
    assert failed_events[0].action_id == service._migration_repo.items[0].action_id


@pytest.mark.asyncio
async def test_finalize_active_downloading_migration_before_completion(monkeypatch, tmp_path):
    save_path = str(tmp_path / "downloads")
    target_path = tmp_path / "target"
    target_path.mkdir()
    Path(save_path).write_text("movie", encoding="utf-8")
    task = make_task(save_path)
    repo = FakeRepo(task)
    source_info = DownloadInfo(
        hash="abc",
        name="Movie",
        size=10,
        progress=0.5,
        state="downloading",
        save_path=save_path,
        added_on=datetime.now(),
        content_path=save_path,
    )
    target_info = DownloadInfo(
        hash="abc",
        name="Movie",
        size=10,
        progress=0.4,
        state="downloading",
        save_path=str(target_path),
        added_on=datetime.now(),
        content_path=str(target_path / "Movie"),
    )
    source_client = FakeClient(source_info)
    target_client = FakeClient(target_info)
    service = TaskDownloaderChangeService(repo, FakeFactory({"old": source_client, "new": target_client}))
    service._migration_repo = FakeMigrationRepo()
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.settings_service.list_downloaders",
        lambda: [
            QBittorrentConfig(id="old", name="old", type="qbittorrent", url="http://old"),
            QBittorrentConfig(id="new", name="new", type="qbittorrent", url="http://new"),
        ],
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.settings_service.get_directory_by_id",
        lambda directory_id: DirectoryConfig(
            id=directory_id,
            name="Target",
            path=str(tmp_path / "library"),
            download_path=str(target_path),
            downloader_id="new",
        ),
    )

    async def no_library_files(task_id):
        return []

    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.library_service.get_files_by_task",
        no_library_files,
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_side_effects.event_service.emit_media",
        lambda event, meta=None: None,
    )
    action_updates = []
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_side_effects.action_service.create_action",
        lambda **kwargs: SimpleNamespace(id=kwargs["action_id"]),
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_side_effects.action_service.mark_completed",
        lambda action_id, **kwargs: action_updates.append(("completed", action_id)),
    )

    result = await service.execute(
        "task-1",
        TaskDownloaderChangeRequest(
            target_downloader_id="new",
            target_directory_id="dir-new",
        ),
    )
    updated = await service.finalize_active_migrations()

    assert result.ok is True
    assert updated == 1
    assert repo.updated.downloader_id == "new"
    assert repo.updated.status == TaskStatus.DOWNLOADING
    assert repo.updated.progress == 0.4
    assert target_client.started == ["abc"]
    assert source_client.deleted == [("abc", False)]
    assert service._migration_repo.items[0].status == TaskStorageMigrationStatus.FINALIZED
    assert action_updates == [("completed", service._migration_repo.items[0].action_id)]


@pytest.mark.asyncio
async def test_finalize_failure_rolls_back_moved_download_content(monkeypatch, tmp_path):
    save_path = str(tmp_path / "downloads")
    target_path = tmp_path / "target"
    target_path.mkdir()
    source_file = Path(save_path)
    source_file.write_text("movie", encoding="utf-8")
    task = make_task(save_path)
    repo = FakeRepo(task)
    source_info = DownloadInfo(
        hash="abc",
        name="Movie",
        size=10,
        progress=0.5,
        state="downloading",
        save_path=save_path,
        added_on=datetime.now(),
        content_path=save_path,
    )
    target_info = DownloadInfo(
        hash="abc",
        name="Movie",
        size=10,
        progress=1.0,
        state="pausedUP",
        save_path=str(target_path),
        added_on=datetime.now(),
        content_path=str(target_path / "Movie"),
    )
    source_client = FakeClient(source_info)
    target_client = FakeClient(target_info)
    service = TaskDownloaderChangeService(repo, FakeFactory({"old": source_client, "new": target_client}))
    service._migration_repo = FakeMigrationRepo()
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.settings_service.list_downloaders",
        lambda: [
            QBittorrentConfig(id="old", name="old", type="qbittorrent", url="http://old"),
            QBittorrentConfig(id="new", name="new", type="qbittorrent", url="http://new"),
        ],
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.settings_service.get_directory_by_id",
        lambda directory_id: DirectoryConfig(
            id=directory_id,
            name="Target",
            path=str(tmp_path / "library"),
            download_path=str(target_path),
            downloader_id="new",
        ),
    )

    async def no_library_files(task_id):
        return []

    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.library_service.get_files_by_task",
        no_library_files,
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_side_effects.event_service.emit_media",
        lambda event, meta=None: None,
    )
    action_updates = []
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_side_effects.action_service.create_action",
        lambda **kwargs: SimpleNamespace(id=kwargs["action_id"]),
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_side_effects.action_service.mark_failed",
        lambda action_id, **kwargs: action_updates.append(("failed", action_id, kwargs.get("error"))),
    )

    result = await service.execute(
        "task-1",
        TaskDownloaderChangeRequest(
            target_downloader_id="new",
            target_directory_id="dir-new",
        ),
    )

    moved_file = target_path / "Movie"
    assert result.ok is True
    assert moved_file.exists()
    assert not source_file.exists()

    target_client.info = None
    updated = await service.finalize_active_migrations()

    assert updated == 1
    assert source_file.exists()
    assert not moved_file.exists()
    assert repo.updated.downloader_id == "old"
    assert repo.updated.save_path == save_path
    assert repo.updated.status == TaskStatus.DOWNLOADING
    assert source_client.started == ["abc"]
    assert service._migration_repo.items[0].status == TaskStorageMigrationStatus.FAILED
    assert service._migration_repo.items[0].reason == "target_torrent_missing"
    assert action_updates == [("failed", service._migration_repo.items[0].action_id, "target_torrent_missing")]


@pytest.mark.asyncio
async def test_finalize_target_error_state_fails_migration(monkeypatch, tmp_path):
    save_path = str(tmp_path / "downloads")
    target_path = tmp_path / "target"
    target_path.mkdir()
    source_file = Path(save_path)
    source_file.write_text("movie", encoding="utf-8")
    task = make_task(save_path)
    repo = FakeRepo(task)
    source_info = DownloadInfo(
        hash="abc",
        name="Movie",
        size=10,
        progress=0.5,
        state="downloading",
        save_path=save_path,
        added_on=datetime.now(),
        content_path=save_path,
    )
    target_info = DownloadInfo(
        hash="abc",
        name="Movie",
        size=10,
        progress=0.5,
        state="error",
        save_path=str(target_path),
        added_on=datetime.now(),
        content_path=str(target_path / "Movie"),
    )
    source_client = FakeClient(source_info)
    target_client = FakeClient(target_info)
    service = TaskDownloaderChangeService(repo, FakeFactory({"old": source_client, "new": target_client}))
    service._migration_repo = FakeMigrationRepo()
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.settings_service.list_downloaders",
        lambda: [
            QBittorrentConfig(id="old", name="old", type="qbittorrent", url="http://old"),
            QBittorrentConfig(id="new", name="new", type="qbittorrent", url="http://new"),
        ],
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.settings_service.get_directory_by_id",
        lambda directory_id: DirectoryConfig(
            id=directory_id,
            name="Target",
            path=str(tmp_path / "library"),
            download_path=str(target_path),
            downloader_id="new",
        ),
    )

    async def no_library_files(task_id):
        return []

    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.library_service.get_files_by_task",
        no_library_files,
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_side_effects.event_service.emit_media",
        lambda event, meta=None: None,
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_side_effects.action_service.create_action",
        lambda **kwargs: SimpleNamespace(id=kwargs["action_id"]),
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_side_effects.action_service.mark_failed",
        lambda action_id, **kwargs: None,
    )

    result = await service.execute(
        "task-1",
        TaskDownloaderChangeRequest(
            target_downloader_id="new",
            target_directory_id="dir-new",
        ),
    )
    updated = await service.finalize_active_migrations()

    assert result.ok is True
    assert updated == 1
    assert source_file.exists()
    assert not target_path.joinpath("Movie").exists()
    assert repo.updated.downloader_id == "old"
    assert repo.updated.status == TaskStatus.DOWNLOADING
    assert source_client.started == ["abc"]
    assert service._migration_repo.items[0].status == TaskStorageMigrationStatus.FAILED
    assert service._migration_repo.items[0].reason == "target_recheck_failed"


def test_resolve_content_path_uses_download_root_for_relative_save_path(monkeypatch, tmp_path):
    download_root = tmp_path / "download-root"
    monkeypatch.setattr("app.utils.library_paths.get_download_root", lambda: download_root)

    resolved = resolve_content_path("movie/Movie", None)

    assert resolved == (download_root / "movie" / "Movie").resolve(strict=False)


def test_resolve_target_content_path_uses_download_root_for_relative_save_path(monkeypatch, tmp_path):
    download_root = tmp_path / "download-root"
    source_content = tmp_path / "source" / "Movie"
    monkeypatch.setattr("app.utils.library_paths.get_download_root", lambda: download_root)

    resolved = _resolve_target_content_path("target", source_content, None)

    assert resolved == (download_root / "target" / "Movie").resolve(strict=False)


@pytest.mark.parametrize(
    "previous",
    [
        TaskStatus.COMPLETED,
        TaskStatus.PARTIAL_MISSING,
        TaskStatus.SEEDING_ABSENT,
        TaskStatus.FILE_MISSING,
    ],
)
def test_status_after_finalize_preserves_library_states(previous):
    assert TaskDownloaderChangeService._status_after_finalize(previous, 1.0) == previous


def test_move_content_if_needed_returns_blocker_on_filesystem_error(monkeypatch, tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target" / "Movie"
    source.write_text("movie", encoding="utf-8")

    def fail_move(source_path, target_path):
        raise OSError("permission denied")

    monkeypatch.setattr("app.services.domain.download.downloader_change_file_ops.shutil.move", fail_move)

    assert move_content_if_needed(move_content=True, source_path=str(source), target_path=str(target)) == "content_move_failed"
    assert source.exists()


def test_validate_hardlink_safe_move_checks_target_library_device(monkeypatch, tmp_path):
    download_root = tmp_path / "download"
    current_download = download_root / "old"
    target_download = download_root / "new"
    target_library = tmp_path / "library-new"
    current_library = tmp_path / "library-old" / "Movie.mkv"
    for path in (current_download, target_download, target_library, current_library.parent):
        path.mkdir(parents=True)
    current_library.write_text("movie", encoding="utf-8")
    task = make_task(str(current_download))
    library_file = LibraryFile(
        id="file-1",
        task_id="task-1",
        directory_id="dir-old",
        media_id=MediaID.parse("tmdb:movie:1"),
        path=str(current_library.parent),
        file_name=current_library.name,
        created_at=1.0,
    )
    devices = {
        str(current_download): 1,
        str(target_download): 1,
        str(target_library): 2,
        str(current_library): 1,
    }
    original_stat = Path.stat

    def stat_with_devices(path, *args, **kwargs):
        resolved = str(path)
        if resolved in devices:
            return SimpleNamespace(st_dev=devices[resolved])
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr("app.utils.library_paths.get_download_root", lambda: download_root)
    monkeypatch.setattr(Path, "stat", stat_with_devices)

    assert _validate_hardlink_safe_move(task, [library_file], target_download, target_library) is False


@pytest.mark.asyncio
async def test_preview_requires_hardlink_check_when_only_library_directory_changes(monkeypatch, tmp_path):
    download_root = tmp_path / "download-root"
    download_path = download_root / "same"
    library_path = tmp_path / "library-old"
    target_library_path = tmp_path / "library-new"
    for path in (download_path, library_path, target_library_path):
        path.mkdir(parents=True)
    task = make_task("same")
    library_file = LibraryFile(
        id="file-1",
        task_id=task.id,
        directory_id="dir-old",
        media_id=task.media_id,
        path=str(library_path),
        file_name="Movie.mkv",
        created_at=1.0,
    )
    source_info = DownloadInfo(
        hash="abc",
        name="Movie",
        size=10,
        progress=1.0,
        state="pausedUP",
        save_path=str(download_path),
        added_on=datetime.now(),
        content_path=str(download_path),
    )

    async def library_files(task_id):
        assert task_id == task.id
        return [library_file]

    monkeypatch.setattr("app.services.domain.download.downloader_change_preview.library_service.get_files_by_task", library_files)
    monkeypatch.setattr("app.services.domain.download.downloader_change_preview.library_service.is_primary_file", lambda item: True)
    monkeypatch.setattr("app.utils.library_paths.get_download_root", lambda: download_root)
    monkeypatch.setattr("app.services.domain.download.downloader_change_preview._validate_hardlink_safe_move", lambda *args: False)

    preview = await build_change_preview(
        task=task,
        target_downloader=QBittorrentConfig(id="new", name="new", type="qbittorrent", url="http://new"),
        target_directory=DirectoryConfig(
            id="dir-new",
            name="Target",
            path=str(target_library_path),
            download_path=str(download_path),
            downloader_id="new",
        ),
        source_client=FakeClient(source_info),
        target_client=FakeClient(source_info),
    )

    assert preview.save_path_changed is False
    assert preview.hardlink_check_required is True
    assert preview.hardlink_check_passed is False
    assert "hardlink_cross_device_or_unmatched" in preview.blockers


@pytest.mark.asyncio
async def test_finalize_migration_succeeds_when_source_torrent_cleanup_fails(monkeypatch, tmp_path):
    save_path = str(tmp_path / "downloads")
    target_path = tmp_path / "target"
    target_path.mkdir()
    Path(save_path).write_text("movie", encoding="utf-8")
    library_root = tmp_path / "library"
    source_library_dir = library_root / "old" / "Movie"
    source_library_dir.mkdir(parents=True)
    (library_root / "new").mkdir(parents=True)
    source_library_file = source_library_dir / "Movie.mkv"
    source_library_file.write_text("movie", encoding="utf-8")
    task = make_task(save_path)
    repo = FakeRepo(task)
    source_info = DownloadInfo(
        hash="abc",
        name="Movie",
        size=10,
        progress=0.5,
        state="downloading",
        save_path=save_path,
        added_on=datetime.now(),
        content_path=save_path,
    )
    target_info = DownloadInfo(
        hash="abc",
        name="Movie",
        size=10,
        progress=1.0,
        state="pausedUP",
        save_path=str(target_path),
        added_on=datetime.now(),
        content_path=str(target_path / "Movie"),
    )
    source_client = FakeDeleteFailClient(source_info)
    target_client = FakeClient(target_info)
    service = TaskDownloaderChangeService(repo, FakeFactory({"old": source_client, "new": target_client}))
    service._migration_repo = FakeMigrationRepo()
    source_directory = DirectoryConfig(
        id="dir-old",
        name="Old",
        path=str(library_root / "old"),
        download_path=save_path,
        downloader_id="old",
    )
    target_directory = DirectoryConfig(
        id="dir-new",
        name="New",
        path=str(library_root / "new"),
        download_path=str(target_path),
        downloader_id="new",
    )
    library_file = LibraryFile(
        id="file-1",
        task_id="task-1",
        directory_id="dir-old",
        media_id=MediaID.parse("tmdb:movie:1"),
        path="old/Movie",
        file_name="Movie.mkv",
        created_at=1.0,
    )

    monkeypatch.setattr("app.utils.library_paths.get_library_root", lambda: library_root)
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.settings_service.list_downloaders",
        lambda: [
            QBittorrentConfig(id="old", name="old", type="qbittorrent", url="http://old"),
            QBittorrentConfig(id="new", name="new", type="qbittorrent", url="http://new"),
        ],
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.settings_service.get_directory_by_id",
        lambda directory_id: source_directory if directory_id == "dir-old" else target_directory,
    )

    async def task_library_files(task_id):
        return [library_file]

    library_updates = []

    async def update_file_location(file_id, *, directory_id, path, file_name):
        library_updates.append((file_id, directory_id, path, file_name))
        return True

    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.library_service.get_files_by_task",
        task_library_files,
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.library_service.update_file_location",
        update_file_location,
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_side_effects.event_service.emit_media",
        lambda event, meta=None: None,
    )
    action_updates = []
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_side_effects.action_service.create_action",
        lambda **kwargs: SimpleNamespace(id=kwargs["action_id"]),
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_side_effects.action_service.mark_completed",
        lambda action_id, **kwargs: action_updates.append(("completed", action_id)),
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_side_effects.action_service.mark_failed",
        lambda action_id, **kwargs: action_updates.append(("failed", action_id, kwargs.get("error"))),
    )

    result = await service.execute(
        "task-1",
        TaskDownloaderChangeRequest(
            target_downloader_id="new",
            target_directory_id="dir-new",
        ),
    )
    updated = await service.finalize_active_migrations()

    assert result.ok is True
    assert updated == 1
    assert repo.updated.downloader_id == "new"
    assert repo.updated.context.directory_id == "dir-new"
    assert repo.updated.status == TaskStatus.FINISHED
    assert source_client.deleted == [("abc", False)]
    assert service._migration_repo.items[0].status == TaskStorageMigrationStatus.FINALIZED
    assert action_updates == [("completed", service._migration_repo.items[0].action_id)]
    assert library_updates == [("file-1", "dir-new", "new/Movie", "Movie.mkv")]


@pytest.mark.asyncio
async def test_change_task_downloader_does_not_move_content_when_target_add_fails(monkeypatch, tmp_path):
    save_path = str(tmp_path / "downloads")
    target_path = tmp_path / "target"
    target_path.mkdir()
    source_file = Path(save_path)
    source_file.write_text("movie", encoding="utf-8")
    task = make_task(save_path)
    repo = FakeRepo(task)
    source_info = DownloadInfo(
        hash="abc",
        name="Movie",
        size=10,
        progress=0.5,
        state="downloading",
        save_path=save_path,
        added_on=datetime.now(),
        content_path=save_path,
    )
    source_client = FakeClient(source_info)
    target_client = FakeAddFailClient(None)
    service = TaskDownloaderChangeService(repo, FakeFactory({"old": source_client, "new": target_client}))
    service._migration_repo = FakeMigrationRepo()
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.settings_service.list_downloaders",
        lambda: [
            QBittorrentConfig(id="old", name="old", type="qbittorrent", url="http://old"),
            QBittorrentConfig(id="new", name="new", type="qbittorrent", url="http://new"),
        ],
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.settings_service.get_directory_by_id",
        lambda directory_id: DirectoryConfig(
            id=directory_id,
            name="Target",
            path=str(tmp_path / "library"),
            download_path=str(target_path),
            downloader_id="new",
        ),
    )

    async def no_library_files(task_id):
        return []

    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.library_service.get_files_by_task",
        no_library_files,
    )
    emitted_events = []
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_side_effects.event_service.emit_media",
        lambda event, meta=None: emitted_events.append((event, meta)),
    )

    result = await service.execute(
        "task-1",
        TaskDownloaderChangeRequest(
            target_downloader_id="new",
            target_directory_id="dir-new",
        ),
    )

    assert result.ok is False
    assert "target_add_torrent_failed" in result.blockers
    assert source_file.exists()
    assert not target_path.joinpath(source_file.name).exists()
    assert repo.updated is None
    assert len(service._migration_repo.items) == 1
    assert service._migration_repo.items[0].status == TaskStorageMigrationStatus.FAILED
    assert service._migration_repo.items[0].reason == "target_add_torrent_failed"
    assert service._migration_repo.items[0].source_paused is True
    assert service._migration_repo.items[0].target_added_by_migration is False
    assert service._migration_repo.items[0].content_moved is False
    assert source_client.paused == ["abc"]
    assert source_client.started == ["abc"]
    assert target_client.added
    assert emitted_events[-1][0].type == EventTypes.DOWNLOAD_TASK_STORAGE_CHANGE_FAILED


@pytest.mark.asyncio
async def test_change_task_downloader_cleans_added_target_when_priority_sync_fails(monkeypatch, tmp_path):
    save_path = str(tmp_path / "downloads")
    target_path = tmp_path / "target"
    target_path.mkdir()
    source_file = Path(save_path)
    source_file.write_text("movie", encoding="utf-8")
    task = make_task(save_path)
    repo = FakeRepo(task)
    source_info = DownloadInfo(
        hash="abc",
        name="Movie",
        size=10,
        progress=0.5,
        state="downloading",
        save_path=save_path,
        added_on=datetime.now(),
        content_path=save_path,
    )
    source_client = FakeClient(source_info)
    target_client = FakeAddThenPriorityFailClient(
        DownloadInfo(
            hash="abc",
            name="Movie",
            size=10,
            progress=0.0,
            state="pausedDL",
            save_path=str(target_path),
            added_on=datetime.now(),
            content_path=str(target_path / "Movie"),
        )
    )
    service = TaskDownloaderChangeService(repo, FakeFactory({"old": source_client, "new": target_client}))
    service._migration_repo = FakeMigrationRepo()
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.settings_service.list_downloaders",
        lambda: [
            QBittorrentConfig(id="old", name="old", type="qbittorrent", url="http://old"),
            QBittorrentConfig(id="new", name="new", type="qbittorrent", url="http://new"),
        ],
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.settings_service.get_directory_by_id",
        lambda directory_id: DirectoryConfig(
            id=directory_id,
            name="Target",
            path=str(tmp_path / "library"),
            download_path=str(target_path),
            downloader_id="new",
        ),
    )

    async def no_library_files(task_id):
        return []

    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.library_service.get_files_by_task",
        no_library_files,
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_side_effects.event_service.emit_media",
        lambda event, meta=None: None,
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_side_effects.action_service.create_action",
        lambda **kwargs: SimpleNamespace(id=kwargs["action_id"]),
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_side_effects.action_service.mark_failed",
        lambda action_id, **kwargs: None,
    )

    result = await service.execute(
        "task-1",
        TaskDownloaderChangeRequest(
            target_downloader_id="new",
            target_directory_id="dir-new",
        ),
    )

    assert result.ok is False
    assert "target_file_priority_sync_failed" in result.blockers
    assert source_file.exists()
    assert source_client.started == ["abc"]
    assert target_client.deleted == [("abc", False)]
    assert service._migration_repo.items[0].target_added_by_migration is True
    assert service._migration_repo.items[0].content_moved is False


@pytest.mark.asyncio
async def test_finalize_paused_incomplete_migration_keeps_task_paused(monkeypatch, tmp_path):
    save_path = str(tmp_path / "downloads")
    target_path = tmp_path / "target"
    target_path.mkdir()
    Path(save_path).write_text("movie", encoding="utf-8")
    task = make_task(save_path)
    task.status = TaskStatus.PAUSED
    repo = FakeRepo(task)
    source_info = DownloadInfo(
        hash="abc",
        name="Movie",
        size=10,
        progress=0.5,
        state="pausedDL",
        save_path=save_path,
        added_on=datetime.now(),
        content_path=save_path,
    )
    target_info = DownloadInfo(
        hash="abc",
        name="Movie",
        size=10,
        progress=0.5,
        state="pausedDL",
        save_path=str(target_path),
        added_on=datetime.now(),
        content_path=str(target_path / "Movie"),
    )
    source_client = FakeClient(source_info)
    target_client = FakeClient(target_info)
    service = TaskDownloaderChangeService(repo, FakeFactory({"old": source_client, "new": target_client}))
    service._migration_repo = FakeMigrationRepo()
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.settings_service.list_downloaders",
        lambda: [
            QBittorrentConfig(id="old", name="old", type="qbittorrent", url="http://old"),
            QBittorrentConfig(id="new", name="new", type="qbittorrent", url="http://new"),
        ],
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.settings_service.get_directory_by_id",
        lambda directory_id: DirectoryConfig(
            id=directory_id,
            name="Target",
            path=str(tmp_path / "library"),
            download_path=str(target_path),
            downloader_id="new",
        ),
    )
    async def no_library_files(task_id):
        return []

    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.library_service.get_files_by_task",
        no_library_files,
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_side_effects.event_service.emit_media",
        lambda event, meta=None: None,
    )
    action_updates = []
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_side_effects.action_service.create_action",
        lambda **kwargs: SimpleNamespace(id=kwargs["action_id"]),
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_side_effects.action_service.mark_completed",
        lambda action_id, **kwargs: action_updates.append(("completed", action_id)),
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_side_effects.action_service.mark_failed",
        lambda action_id, **kwargs: action_updates.append(("failed", action_id, kwargs.get("error"))),
    )

    result = await service.execute(
        "task-1",
        TaskDownloaderChangeRequest(
            target_downloader_id="new",
            target_directory_id="dir-new",
        ),
    )
    updated = await service.finalize_active_migrations()

    assert result.ok is True
    assert updated == 1
    assert repo.updated.downloader_id == "new"
    assert repo.updated.status == TaskStatus.PAUSED
    assert repo.updated.progress == 0.5
    assert target_client.started == []
    assert source_client.deleted == [("abc", False)]
    assert service._migration_repo.items[0].status == TaskStorageMigrationStatus.FINALIZED
    assert action_updates == [("completed", service._migration_repo.items[0].action_id)]


@pytest.mark.asyncio
async def test_finalize_completed_migration_waits_for_async_recheck_state(monkeypatch, tmp_path):
    save_path = str(tmp_path / "downloads")
    target_path = tmp_path / "target"
    target_path.mkdir()
    Path(save_path).write_text("movie", encoding="utf-8")
    task = make_task(save_path)
    task.status = TaskStatus.COMPLETED
    task.progress = 1.0
    repo = FakeRepo(task)
    source_info = DownloadInfo(
        hash="abc",
        name="Movie",
        size=10,
        progress=1.0,
        state="pausedUP",
        save_path=save_path,
        added_on=datetime.now(),
        content_path=save_path,
    )
    target_info = DownloadInfo(
        hash="abc",
        name="Movie",
        size=10,
        progress=0.5,
        state="pausedDL",
        save_path=str(target_path),
        added_on=datetime.now(),
        content_path=str(target_path / "Movie"),
    )
    source_client = FakeClient(source_info)
    target_client = FakeClient(target_info)
    service = TaskDownloaderChangeService(repo, FakeFactory({"old": source_client, "new": target_client}))
    service._migration_repo = FakeMigrationRepo()
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.settings_service.list_downloaders",
        lambda: [
            QBittorrentConfig(id="old", name="old", type="qbittorrent", url="http://old"),
            QBittorrentConfig(id="new", name="new", type="qbittorrent", url="http://new"),
        ],
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.settings_service.get_directory_by_id",
        lambda directory_id: DirectoryConfig(
            id=directory_id,
            name="Target",
            path=str(tmp_path / "library"),
            download_path=str(target_path),
            downloader_id="new",
        ),
    )

    async def no_library_files(task_id):
        return []

    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.library_service.get_files_by_task",
        no_library_files,
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_side_effects.event_service.emit_media",
        lambda event, meta=None: None,
    )
    action_updates = []
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_side_effects.action_service.create_action",
        lambda **kwargs: SimpleNamespace(id=kwargs["action_id"]),
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_side_effects.action_service.mark_completed",
        lambda action_id, **kwargs: action_updates.append(("completed", action_id)),
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change_side_effects.action_service.mark_failed",
        lambda action_id, **kwargs: action_updates.append(("failed", action_id, kwargs.get("error"))),
    )

    result = await service.execute(
        "task-1",
        TaskDownloaderChangeRequest(
            target_downloader_id="new",
            target_directory_id="dir-new",
        ),
    )
    updated = await service.finalize_active_migrations()

    assert result.ok is True
    assert updated == 0
    assert repo.updated.status == TaskStatus.MIGRATING
    assert service._migration_repo.items[0].status == TaskStorageMigrationStatus.CHECKING
    assert service._migration_repo.items[0].reason is None
    assert source_client.started == []
    assert action_updates == []


@pytest.mark.asyncio
async def test_change_task_downloader_rejects_media_type_mismatch(monkeypatch, tmp_path):
    save_path = str(tmp_path / "downloads")
    target_path = tmp_path / "target"
    target_path.mkdir()
    Path(save_path).write_text("movie", encoding="utf-8")
    task = make_task(save_path)
    repo = FakeRepo(task)
    source_info = DownloadInfo(
        hash="abc",
        name="Movie",
        size=10,
        progress=1.0,
        state="pausedUP",
        save_path=save_path,
        added_on=datetime.now(),
        content_path=save_path,
    )
    target_client = FakeClient(source_info.model_copy(update={"save_path": str(target_path), "content_path": str(target_path / "Movie")}))
    service = TaskDownloaderChangeService(repo, FakeFactory({"old": FakeClient(source_info), "new": target_client}))
    service._migration_repo = FakeMigrationRepo()
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.settings_service.list_downloaders",
        lambda: [
            QBittorrentConfig(id="old", name="old", type="qbittorrent", url="http://old"),
            QBittorrentConfig(id="new", name="new", type="qbittorrent", url="http://new"),
        ],
    )
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.settings_service.get_directory_by_id",
        lambda directory_id: DirectoryConfig(
            id=directory_id,
            name="Target TV",
            media_type="tv",
            path=str(tmp_path / "library"),
            download_path=str(target_path),
            downloader_id="new",
        ),
    )
    async def no_library_files(task_id):
        return []

    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.library_service.get_files_by_task",
        no_library_files,
    )

    result = await service.preview(
        "task-1",
        TaskDownloaderChangeRequest(
            target_downloader_id="new",
            target_directory_id="dir-tv",
        ),
    )

    assert result.ok is False
    assert "media_type_mismatch" in result.blockers


@pytest.mark.asyncio
async def test_move_task_library_files_updates_directory_when_paths_match(monkeypatch, tmp_path):
    library_root = tmp_path / "library"
    media_dir = library_root / "movie" / "Honey"
    media_dir.mkdir(parents=True)
    media_file = media_dir / "Honey.mkv"
    media_file.write_text("movie", encoding="utf-8")
    source_directory = DirectoryConfig(
        id="dir-old",
        name="Movie",
        path=str(library_root / "movie"),
        download_path=str(tmp_path / "download-old"),
        downloader_id="old",
    )
    target_directory = DirectoryConfig(
        id="dir-new",
        name="Movie New",
        path=str(library_root / "movie"),
        download_path=str(tmp_path / "download-new"),
        downloader_id="new",
    )
    library_file = LibraryFile(
        id="file-1",
        task_id="task-1",
        directory_id="dir-old",
        media_id=MediaID.parse("tmdb:movie:1"),
        path="movie/Honey",
        file_name="Honey.mkv",
        created_at=1.0,
    )
    updates = []

    monkeypatch.setattr("app.utils.library_paths.get_library_root", lambda: library_root)
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.settings_service.get_directory_by_id",
        lambda directory_id: source_directory if directory_id == "dir-old" else target_directory,
    )

    async def update_file_location(file_id, *, directory_id, path, file_name):
        updates.append((file_id, directory_id, path, file_name))
        return True

    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.library_service.update_file_location",
        update_file_location,
    )

    task = make_task(str(tmp_path / "download-old"))

    assert await move_task_library_files(task, [library_file], source_directory, target_directory) is True
    assert media_file.exists()
    assert updates == [("file-1", "dir-new", "movie/Honey", "Honey.mkv")]


@pytest.mark.asyncio
async def test_move_task_library_files_rolls_back_physical_move_when_db_update_fails(monkeypatch, tmp_path):
    library_root = tmp_path / "library"
    source_dir = library_root / "old" / "Honey"
    source_dir.mkdir(parents=True)
    source_file = source_dir / "Honey.mkv"
    source_file.write_text("movie", encoding="utf-8")
    source_directory = DirectoryConfig(
        id="dir-old",
        name="Movie",
        path=str(library_root / "old"),
        download_path=str(tmp_path / "download-old"),
        downloader_id="old",
    )
    target_directory = DirectoryConfig(
        id="dir-new",
        name="Movie New",
        path=str(library_root / "new"),
        download_path=str(tmp_path / "download-new"),
        downloader_id="new",
    )
    library_file = LibraryFile(
        id="file-1",
        task_id="task-1",
        directory_id="dir-old",
        media_id=MediaID.parse("tmdb:movie:1"),
        path="old/Honey",
        file_name="Honey.mkv",
        created_at=1.0,
    )

    monkeypatch.setattr("app.utils.library_paths.get_library_root", lambda: library_root)
    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.settings_service.get_directory_by_id",
        lambda directory_id: source_directory if directory_id == "dir-old" else target_directory,
    )

    async def update_file_location(file_id, *, directory_id, path, file_name):
        return False

    monkeypatch.setattr(
        "app.services.domain.download.downloader_change.library_service.update_file_location",
        update_file_location,
    )

    task = make_task(str(tmp_path / "download-old"))

    assert await move_task_library_files(task, [library_file], source_directory, target_directory) is False
    assert source_file.exists()
    assert not (library_root / "new" / "Honey" / "Honey.mkv").exists()
