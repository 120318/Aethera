import os
import time
from datetime import datetime, timedelta

import pytest

from app.schemas.config import DirectoryConfig
from app.schemas.domain.download import TaskContext, TaskData, TaskStatus
from app.schemas.domain.library import LibraryFile
from app.schemas.domain.media import MediaExecutionSnapshot
from app.schemas.domain.torrent import TorrentFileItem, TorrentMetadata
from app.schemas.domain.torrent_status import TorrentState, TorrentStatus
from app.schemas.media_id import MediaID
from app.schemas.runtime.directory_integrity import (
    DirectoryIntegrityIssueType,
    DirectoryIntegrityPolicy,
    DirectoryIntegrityRepairRequest,
)
from app.services.application.workflows.directory_integrity import service as integrity_module
from app.services.application.workflows.directory_integrity.service import DirectoryIntegrityService


pytestmark = [pytest.mark.health]


class AsyncListRepo:
    def __init__(self, values):
        self.values = values

    async def get_all(self):
        return list(self.values)


class RecordingRemovalRepo:
    def __init__(self):
        self.removed_ids = []

    async def remove_by_file_ids(self, ids):
        self.removed_ids.extend(ids)
        return len(ids)

    async def remove_by_library_file_ids(self, ids):
        self.removed_ids.extend(ids)
        return len(ids)

    async def remove_by_ids(self, ids):
        self.removed_ids.extend(ids)
        return len(ids)


class RecordingLibraryRepo(AsyncListRepo):
    def __init__(self, values):
        super().__init__(values)
        self.removed_ids = []

    async def remove_by_ids(self, ids):
        self.removed_ids.extend(ids)
        return len(ids)


class RecordingDownloadService:
    def __init__(self):
        self.refreshed = []

    async def refresh_completed_task_health(self, task_id):
        self.refreshed.append(task_id)


class RecordingTransferService:
    def __init__(self):
        self.transferred = []

    async def perform_transfer_by_task_id(self, task_id):
        self.transferred.append(task_id)
        return None


class FakeDownloadClient:
    def __init__(self, statuses, trackers=None):
        self.statuses = statuses
        self.trackers = trackers or {}

    async def get_torrents(self, hashes=None):
        selected = {item.lower() for item in hashes or []}
        return [status for status in self.statuses if not selected or status.hash.lower() in selected]

    async def get_torrent_trackers(self, torrent_hash):
        return list(self.trackers.get(torrent_hash.lower(), []))


class FakeClientFactory:
    def __init__(self, clients):
        self.clients = clients

    def get_download_client(self, downloader_id=None):
        return self.clients[downloader_id]


def _media_snapshot() -> MediaExecutionSnapshot:
    return MediaExecutionSnapshot(
        media_id=MediaID.parse("tmdb:movie:1"),
        title="Sample",
        year=2024,
    )


def _task(download_root) -> TaskData:
    completed_at = datetime.now() - timedelta(hours=1)
    return TaskData(
        id="task-1",
        media_id=MediaID.parse("tmdb:movie:1"),
        torrent_hash="hash-1",
        status=TaskStatus.COMPLETED,
        context=TaskContext(
            download_url="https://example.invalid/torrent",
            media=_media_snapshot(),
            directory_id="dir-1",
        ),
        save_path=str(download_root),
        created_at=completed_at,
        updated_at=completed_at,
        metadata=TorrentMetadata(
            hash="hash-1",
            name="Managed",
            size=20,
            files=[
                TorrentFileItem(index=0, filename="Managed/episode.mkv", size=10),
                TorrentFileItem(index=1, filename="Managed/missing.mkv", size=10),
            ],
        ),
    )


def _downloader_task(download_root, task_id: str, torrent_hash: str) -> TaskData:
    task = _task(download_root).model_copy(deep=True)
    task.id = task_id
    task.torrent_hash = torrent_hash
    task.downloader_id = "downloader-1"
    return task


def _single_file_task(download_root) -> TaskData:
    completed_at = datetime.now() - timedelta(hours=1)
    return TaskData(
        id="task-single",
        media_id=MediaID.parse("tmdb:movie:2"),
        torrent_hash="hash-single",
        status=TaskStatus.COMPLETED,
        context=TaskContext(
            download_url="https://example.invalid/single",
            media=MediaExecutionSnapshot(
                media_id=MediaID.parse("tmdb:movie:2"),
                title="Single",
                year=2025,
            ),
            directory_id="dir-1",
        ),
        save_path=str(download_root),
        created_at=completed_at,
        updated_at=completed_at,
        metadata=TorrentMetadata(
            hash="hash-single",
            name="Single.Movie.2025.Group",
            size=20,
            files=[
                TorrentFileItem(index=0, filename="Single.Movie.2025.Group.mkv", size=20),
            ],
        ),
    )


def _library_file(file_id: str, path, file_name: str) -> LibraryFile:
    return LibraryFile(
        id=file_id,
        task_id="task-1",
        directory_id="dir-1",
        media_id=MediaID.parse("tmdb:movie:1"),
        path=str(path),
        file_name=file_name,
        created_at=time.time() - 3600,
    )


def _library_file_for_task(file_id: str, task: TaskData, path, file_name: str) -> LibraryFile:
    return LibraryFile(
        id=file_id,
        task_id=task.id,
        directory_id=task.context.directory_id,
        media_id=task.media_id or MediaID.parse("tmdb:movie:1"),
        path=str(path),
        file_name=file_name,
        created_at=time.time() - 3600,
    )


def _set_file_age(path, seconds: int) -> None:
    timestamp = time.time() - seconds
    os.utime(path, (timestamp, timestamp))


@pytest.mark.asyncio
async def test_directory_integrity_scan_reports_library_and_download_drift(tmp_path, monkeypatch):
    library_root = tmp_path / "library"
    download_root = tmp_path / "download"
    library_root.mkdir()
    download_root.mkdir()
    (library_root / "managed").mkdir()
    (library_root / "managed" / "movie.mkv").write_text("ok")
    (library_root / "extra.mkv").write_text("extra")
    _set_file_age(library_root / "extra.mkv", 3600)
    (library_root / "extra.srt").write_text("sidecar")
    (download_root / "Managed").mkdir()
    (download_root / "Managed" / "episode.mkv").write_text("ok")
    (download_root / "orphan.mkv").write_text("orphan")
    _set_file_age(download_root / "orphan.mkv", 3600)

    directory = DirectoryConfig(id="dir-1", name="Movies", path=str(library_root), download_path=str(download_root))
    service = DirectoryIntegrityService()
    service.library_repo = AsyncListRepo(
        [
            _library_file("file-1", library_root / "managed", "movie.mkv"),
            _library_file("file-2", library_root / "missing", "gone.mkv"),
        ]
    )
    service.task_repo = AsyncListRepo([_task(download_root)])

    monkeypatch.setattr(integrity_module.settings_service, "list_directories", lambda: [directory])
    monkeypatch.setattr(integrity_module, "LATEST_RESULT_PATH", tmp_path / "latest.json")

    result = await service.scan()

    issue_types = {item.issue_type.value for item in result.items}
    assert issue_types == {
        "unmanaged_library_file",
        "missing_library_file",
        "unmanaged_download_entry",
        "missing_download_file",
    }
    assert all("extra.srt" not in item.path for item in result.items)
    unmanaged = next(item for item in result.items if item.issue_type == DirectoryIntegrityIssueType.unmanaged_library_file)
    assert unmanaged.file_created_at is not None
    unmanaged_download = next(item for item in result.items if item.issue_type == DirectoryIntegrityIssueType.unmanaged_download_entry)
    assert unmanaged_download.file_created_at is not None
    missing_library = next(item for item in result.items if item.issue_type == DirectoryIntegrityIssueType.missing_library_file)
    assert missing_library.library_file_name == "gone.mkv"
    assert missing_library.record_created_at is not None
    assert result.summary.total == 4
    assert result.summary.repairable == 4


@pytest.mark.asyncio
async def test_directory_integrity_scan_can_target_single_directory(tmp_path, monkeypatch):
    library_one = tmp_path / "library-one"
    download_one = tmp_path / "download-one"
    library_two = tmp_path / "library-two"
    download_two = tmp_path / "download-two"
    for path in [library_one, download_one, library_two, download_two]:
        path.mkdir()

    directories = [
        DirectoryConfig(id="dir-1", name="Movies", path=str(library_one), download_path=str(download_one)),
        DirectoryConfig(id="dir-2", name="Shows", path=str(library_two), download_path=str(download_two)),
    ]
    service = DirectoryIntegrityService()
    service.library_repo = AsyncListRepo([])
    service.task_repo = AsyncListRepo([])

    monkeypatch.setattr(integrity_module.settings_service, "list_directories", lambda: directories)
    monkeypatch.setattr(integrity_module, "LATEST_RESULT_PATH", tmp_path / "latest.json")

    result = await service.scan("dir-2")

    assert [item.directory_id for item in result.summary.directories] == ["dir-2"]


@pytest.mark.asyncio
async def test_directory_integrity_single_directory_scan_preserves_other_latest_directories(tmp_path, monkeypatch):
    movie_library = tmp_path / "movie-library"
    movie_download = tmp_path / "movie-download"
    show_library = tmp_path / "show-library"
    show_download = tmp_path / "show-download"
    for path in [movie_library, movie_download, show_library, show_download]:
        path.mkdir()
    (movie_library / "movie-extra.mkv").write_text("movie")
    (show_library / "show-extra.mkv").write_text("show")
    _set_file_age(movie_library / "movie-extra.mkv", 3600)
    _set_file_age(show_library / "show-extra.mkv", 3600)

    directories = [
        DirectoryConfig(id="movie-dir", name="Movies", path=str(movie_library), download_path=str(movie_download)),
        DirectoryConfig(id="show-dir", name="Shows", path=str(show_library), download_path=str(show_download)),
    ]
    service = DirectoryIntegrityService()
    service.library_repo = AsyncListRepo([])
    service.task_repo = AsyncListRepo([])

    monkeypatch.setattr(integrity_module.settings_service, "list_directories", lambda: directories)
    monkeypatch.setattr(integrity_module, "LATEST_RESULT_PATH", tmp_path / "latest.json")

    full_scan = await service.scan()
    (show_library / "show-extra.mkv").unlink()
    show_scan = await service.scan("show-dir")

    assert {item.directory_id for item in full_scan.items} == {"movie-dir", "show-dir"}
    assert {item.directory_id for item in show_scan.items} == {"movie-dir"}
    summaries = {item.directory_id: item for item in show_scan.summary.directories}
    assert summaries["movie-dir"].total == 1
    assert summaries["show-dir"].total == 0
    assert full_scan.summary.logical_size > show_scan.summary.logical_size
    assert show_scan.summary.logical_size == sum(item.logical_size for item in show_scan.summary.directories)
    assert show_scan.summary.physical_size == sum(item.physical_size for item in show_scan.summary.directories)


@pytest.mark.asyncio
async def test_directory_integrity_single_directory_scan_refreshes_other_directory_sizes(tmp_path, monkeypatch):
    movie_library = tmp_path / "movie-library"
    movie_download = tmp_path / "movie-download"
    show_library = tmp_path / "show-library"
    show_download = tmp_path / "show-download"
    for path in [movie_library, movie_download, show_library, show_download]:
        path.mkdir()
    movie_file = movie_library / "movie-extra.mkv"
    show_file = show_library / "show-extra.mkv"
    movie_file.write_text("movie")
    show_file.write_text("show")
    _set_file_age(movie_file, 3600)
    _set_file_age(show_file, 3600)

    directories = [
        DirectoryConfig(id="movie-dir", name="Movies", path=str(movie_library), download_path=str(movie_download)),
        DirectoryConfig(id="show-dir", name="Shows", path=str(show_library), download_path=str(show_download)),
    ]
    service = DirectoryIntegrityService()
    service.library_repo = AsyncListRepo([])
    service.task_repo = AsyncListRepo([])

    monkeypatch.setattr(integrity_module.settings_service, "list_directories", lambda: directories)
    monkeypatch.setattr(integrity_module, "LATEST_RESULT_PATH", tmp_path / "latest.json")

    await service.scan()
    movie_file.write_text("movie-expanded")
    show_scan = await service.scan("show-dir")

    summaries = {item.directory_id: item for item in show_scan.summary.directories}
    assert summaries["movie-dir"].logical_size == len("movie-expanded")
    assert show_scan.summary.logical_size == sum(item.logical_size for item in show_scan.summary.directories)


@pytest.mark.asyncio
async def test_directory_integrity_single_directory_scan_drops_inactive_previous_directories(tmp_path, monkeypatch):
    movie_library = tmp_path / "movie-library"
    movie_download = tmp_path / "movie-download"
    show_library = tmp_path / "show-library"
    show_download = tmp_path / "show-download"
    for path in [movie_library, movie_download, show_library, show_download]:
        path.mkdir()
    (movie_library / "movie-extra.mkv").write_text("movie")
    (show_library / "show-extra.mkv").write_text("show")
    _set_file_age(movie_library / "movie-extra.mkv", 3600)
    _set_file_age(show_library / "show-extra.mkv", 3600)

    movie_directory = DirectoryConfig(id="movie-dir", name="Movies", path=str(movie_library), download_path=str(movie_download))
    show_directory = DirectoryConfig(id="show-dir", name="Shows", path=str(show_library), download_path=str(show_download))
    directories = [movie_directory, show_directory]
    service = DirectoryIntegrityService()
    service.library_repo = AsyncListRepo([])
    service.task_repo = AsyncListRepo([])

    monkeypatch.setattr(integrity_module.settings_service, "list_directories", lambda: directories)
    monkeypatch.setattr(integrity_module, "LATEST_RESULT_PATH", tmp_path / "latest.json")

    full_scan = await service.scan()
    directories = [movie_directory]
    movie_scan = await service.scan("movie-dir")

    assert {item.directory_id for item in full_scan.items} == {"movie-dir", "show-dir"}
    assert {item.directory_id for item in movie_scan.items} == {"movie-dir"}
    assert [item.directory_id for item in movie_scan.summary.directories] == ["movie-dir"]
    assert movie_scan.summary.total == 1


@pytest.mark.asyncio
async def test_directory_integrity_single_directory_scan_preserves_global_hardlink_dedup(tmp_path, monkeypatch):
    movie_library = tmp_path / "movie-library"
    show_library = tmp_path / "show-library"
    movie_download = tmp_path / "movie-download"
    show_download = tmp_path / "show-download"
    for path in [movie_library, show_library, movie_download, show_download]:
        path.mkdir()
    movie_file = movie_library / "shared.mkv"
    show_file = show_library / "shared.mkv"
    movie_file.write_bytes(b"shared-content")
    os.link(movie_file, show_file)
    _set_file_age(movie_file, 3600)
    _set_file_age(show_file, 3600)

    directories = [
        DirectoryConfig(id="movie-dir", name="Movies", path=str(movie_library), download_path=str(movie_download)),
        DirectoryConfig(id="show-dir", name="Shows", path=str(show_library), download_path=str(show_download)),
    ]
    service = DirectoryIntegrityService()
    service.library_repo = AsyncListRepo([])
    service.task_repo = AsyncListRepo([])

    monkeypatch.setattr(integrity_module.settings_service, "list_directories", lambda: directories)
    monkeypatch.setattr(integrity_module, "LATEST_RESULT_PATH", tmp_path / "latest.json")

    full_scan = await service.scan()
    show_scan = await service.scan("show-dir")

    stat = movie_file.stat()
    physical_size = int(stat.st_blocks or 0) * 512
    if not physical_size:
        physical_size = stat.st_size
    assert full_scan.summary.physical_size == physical_size
    assert show_scan.summary.physical_size == full_scan.summary.physical_size
    assert show_scan.summary.physical_size < sum(item.physical_size for item in show_scan.summary.directories)


@pytest.mark.asyncio
async def test_directory_integrity_scan_checks_only_selected_download_files(tmp_path, monkeypatch):
    library_root = tmp_path / "library"
    download_root = tmp_path / "download"
    library_root.mkdir()
    download_root.mkdir()
    (library_root / "movie.mkv").write_text("ok")
    (download_root / "Managed").mkdir()
    (download_root / "Managed" / "episode.mkv").write_text("ok")

    task = _task(download_root)
    task.context.selected_files = [0]
    directory = DirectoryConfig(id="dir-1", name="Movies", path=str(library_root), download_path=str(download_root))
    service = DirectoryIntegrityService()
    service.library_repo = AsyncListRepo([_library_file_for_task("file-1", task, library_root, "movie.mkv")])
    service.task_repo = AsyncListRepo([task])

    monkeypatch.setattr(integrity_module.settings_service, "list_directories", lambda: [directory])
    monkeypatch.setattr(integrity_module, "LATEST_RESULT_PATH", tmp_path / "latest.json")

    result = await service.scan()

    assert result.items == []


@pytest.mark.asyncio
async def test_directory_integrity_summary_reports_directory_sizes_with_hardlink_dedup(tmp_path, monkeypatch):
    library_root = tmp_path / "library"
    download_root = tmp_path / "download"
    library_root.mkdir()
    download_root.mkdir()
    download_file = download_root / "Single.Movie.2025.Group.mkv"
    download_file.write_bytes(b"sample")
    library_file = library_root / "movie.mkv"
    os.link(download_file, library_file)

    task = _single_file_task(download_root)
    directory = DirectoryConfig(id="dir-1", name="Movies", path=str(library_root), download_path=str(download_root))
    service = DirectoryIntegrityService()
    service.library_repo = AsyncListRepo([_library_file_for_task("file-1", task, library_root, "movie.mkv")])
    service.task_repo = AsyncListRepo([task])

    monkeypatch.setattr(integrity_module.settings_service, "list_directories", lambda: [directory])
    monkeypatch.setattr(integrity_module, "LATEST_RESULT_PATH", tmp_path / "latest.json")

    result = await service.scan()

    stat = download_file.stat()
    physical_size = int(stat.st_blocks or 0) * 512
    if not physical_size:
        physical_size = stat.st_size
    assert result.items == []
    assert result.summary.logical_size == stat.st_size * 2
    assert result.summary.physical_size == physical_size
    assert result.summary.library_logical_size == stat.st_size
    assert result.summary.download_logical_size == stat.st_size
    assert len(result.summary.directories) == 1
    directory_summary = result.summary.directories[0]
    assert directory_summary.directory_id == "dir-1"
    assert directory_summary.logical_size == stat.st_size * 2
    assert directory_summary.physical_size == physical_size
    assert directory_summary.total == 0


@pytest.mark.asyncio
async def test_directory_integrity_scan_applies_directory_policy(tmp_path, monkeypatch):
    library_root = tmp_path / "library"
    download_root = tmp_path / "download"
    library_root.mkdir()
    download_root.mkdir()
    (library_root / "extra.mkv").write_text("extra")
    _set_file_age(library_root / "extra.mkv", 3600)
    (download_root / "orphan.mkv").write_text("orphan")

    directory = DirectoryConfig(id="dir-1", name="Movies", path=str(library_root), download_path=str(download_root))
    service = DirectoryIntegrityService()
    service.library_repo = AsyncListRepo([])
    service.task_repo = AsyncListRepo([])

    monkeypatch.setattr(integrity_module.settings_service, "list_directories", lambda: [directory])
    monkeypatch.setattr(
        integrity_module.settings_service,
        "list_directory_integrity_policies",
        lambda: [
            DirectoryIntegrityPolicy(
                directory_id="dir-1",
                scan_download=False,
                issue_types=[DirectoryIntegrityIssueType.unmanaged_library_file],
            )
        ],
    )
    monkeypatch.setattr(integrity_module, "LATEST_RESULT_PATH", tmp_path / "latest.json")

    result = await service.scan()

    assert [item.issue_type for item in result.items] == [DirectoryIntegrityIssueType.unmanaged_library_file]


def test_directory_integrity_policy_normalization_preserves_new_issue_type_opt_out():
    from app.services.config.settings_service import SettingsService

    legacy_defaults = [
        DirectoryIntegrityIssueType.unmanaged_library_file,
        DirectoryIntegrityIssueType.missing_library_file,
        DirectoryIntegrityIssueType.task_missing_library_file,
        DirectoryIntegrityIssueType.library_file_missing_task,
        DirectoryIntegrityIssueType.unmanaged_download_entry,
        DirectoryIntegrityIssueType.missing_download_file,
        DirectoryIntegrityIssueType.missing_downloader_torrent,
    ]

    normalized = SettingsService._normalize_directory_integrity_policy(DirectoryIntegrityPolicy(directory_id="dir-1", issue_types=legacy_defaults))

    assert DirectoryIntegrityIssueType.unhealthy_downloader_torrent not in set(normalized.issue_types)


def test_directory_integrity_latest_result_path_uses_persistent_config_cache():
    assert str(integrity_module.LATEST_RESULT_PATH) == "/config/cache/directory_integrity_latest.json"


@pytest.mark.asyncio
async def test_directory_integrity_scan_reports_task_without_library_file(tmp_path, monkeypatch):
    library_root = tmp_path / "library"
    download_root = tmp_path / "download"
    library_root.mkdir()
    download_root.mkdir()
    (download_root / "Managed").mkdir()
    (download_root / "Managed" / "episode.mkv").write_text("ok")
    (download_root / "Managed" / "missing.mkv").write_text("ok")

    directory = DirectoryConfig(id="dir-1", name="Movies", path=str(library_root), download_path=str(download_root))
    service = DirectoryIntegrityService()
    service.library_repo = AsyncListRepo([])
    service.task_repo = AsyncListRepo([_task(download_root)])

    monkeypatch.setattr(integrity_module.settings_service, "list_directories", lambda: [directory])
    monkeypatch.setattr(integrity_module, "LATEST_RESULT_PATH", tmp_path / "latest.json")

    result = await service.scan()

    assert [item.issue_type for item in result.items] == [DirectoryIntegrityIssueType.task_missing_library_file]
    assert result.items[0].task_id == "task-1"
    assert result.items[0].media_title == "Sample"
    assert result.items[0].media_year == 2024
    assert result.items[0].task_completed_at is not None
    assert result.items[0].repair_action == "retry_transfer"
    assert result.summary.tasks_missing_library_files == 1


@pytest.mark.asyncio
async def test_directory_integrity_scan_ignores_recent_task_without_library_file(tmp_path, monkeypatch):
    library_root = tmp_path / "library"
    download_root = tmp_path / "download"
    library_root.mkdir()
    download_root.mkdir()
    (download_root / "Managed").mkdir()
    (download_root / "Managed" / "episode.mkv").write_text("ok")
    (download_root / "Managed" / "missing.mkv").write_text("ok")

    task = _task(download_root)
    task.updated_at = datetime.now()
    directory = DirectoryConfig(id="dir-1", name="Movies", path=str(library_root), download_path=str(download_root))
    service = DirectoryIntegrityService()
    service.library_repo = AsyncListRepo([])
    service.task_repo = AsyncListRepo([task])

    monkeypatch.setattr(integrity_module.settings_service, "list_directories", lambda: [directory])
    monkeypatch.setattr(
        integrity_module.settings_service,
        "list_directory_integrity_policies",
        lambda: [
            DirectoryIntegrityPolicy(
                directory_id="dir-1",
                scan_download=False,
                issue_types=[DirectoryIntegrityIssueType.task_missing_library_file],
            )
        ],
    )
    monkeypatch.setattr(integrity_module, "LATEST_RESULT_PATH", tmp_path / "latest.json")

    result = await service.scan()

    assert result.items == []


@pytest.mark.asyncio
async def test_directory_integrity_scan_ignores_recent_unmanaged_library_file(tmp_path, monkeypatch):
    library_root = tmp_path / "library"
    download_root = tmp_path / "download"
    library_root.mkdir()
    download_root.mkdir()
    (library_root / "fresh.mkv").write_text("fresh")

    directory = DirectoryConfig(id="dir-1", name="Movies", path=str(library_root), download_path=str(download_root))
    service = DirectoryIntegrityService()
    service.library_repo = AsyncListRepo([])
    service.task_repo = AsyncListRepo([])

    monkeypatch.setattr(integrity_module.settings_service, "list_directories", lambda: [directory])
    monkeypatch.setattr(
        integrity_module.settings_service,
        "list_directory_integrity_policies",
        lambda: [
            DirectoryIntegrityPolicy(
                directory_id="dir-1",
                scan_download=False,
                issue_types=[DirectoryIntegrityIssueType.missing_library_file],
            )
        ],
    )
    monkeypatch.setattr(integrity_module, "LATEST_RESULT_PATH", tmp_path / "latest.json")

    result = await service.scan()

    assert result.items == []


@pytest.mark.asyncio
async def test_directory_integrity_scan_ignores_recent_missing_library_record(tmp_path, monkeypatch):
    library_root = tmp_path / "library"
    download_root = tmp_path / "download"
    library_root.mkdir()
    download_root.mkdir()

    library_file = _library_file("file-1", library_root / "missing", "fresh.mkv")
    library_file.created_at = time.time()
    directory = DirectoryConfig(id="dir-1", name="Movies", path=str(library_root), download_path=str(download_root))
    service = DirectoryIntegrityService()
    service.library_repo = AsyncListRepo([library_file])
    service.task_repo = AsyncListRepo([])

    monkeypatch.setattr(integrity_module.settings_service, "list_directories", lambda: [directory])
    monkeypatch.setattr(
        integrity_module.settings_service,
        "list_directory_integrity_policies",
        lambda: [
            DirectoryIntegrityPolicy(
                directory_id="dir-1",
                scan_download=False,
                issue_types=[DirectoryIntegrityIssueType.missing_library_file],
            )
        ],
    )
    monkeypatch.setattr(integrity_module, "LATEST_RESULT_PATH", tmp_path / "latest.json")

    result = await service.scan()

    assert result.items == []


@pytest.mark.asyncio
async def test_directory_integrity_scan_reports_library_file_without_task(tmp_path, monkeypatch):
    library_root = tmp_path / "library"
    download_root = tmp_path / "download"
    library_root.mkdir()
    download_root.mkdir()
    (library_root / "managed").mkdir()
    (library_root / "managed" / "movie.mkv").write_text("ok")

    directory = DirectoryConfig(id="dir-1", name="Movies", path=str(library_root), download_path=str(download_root))
    service = DirectoryIntegrityService()
    service.library_repo = AsyncListRepo([_library_file("file-1", library_root / "managed", "movie.mkv")])
    service.task_repo = AsyncListRepo([])

    monkeypatch.setattr(integrity_module.settings_service, "list_directories", lambda: [directory])
    monkeypatch.setattr(integrity_module, "LATEST_RESULT_PATH", tmp_path / "latest.json")

    result = await service.scan()

    assert [item.issue_type for item in result.items] == [DirectoryIntegrityIssueType.library_file_missing_task]
    assert result.items[0].library_file_id == "file-1"
    assert result.items[0].task_id == "task-1"
    assert result.summary.library_files_missing_tasks == 1


@pytest.mark.asyncio
async def test_directory_integrity_scan_accepts_single_file_torrent_folder(tmp_path, monkeypatch):
    library_root = tmp_path / "library"
    download_root = tmp_path / "download"
    library_root.mkdir()
    download_root.mkdir()
    (library_root / "movie.mkv").write_text("ok")
    torrent_folder = download_root / "Single.Movie.2025.Group"
    torrent_folder.mkdir()
    (torrent_folder / "Single.Movie.2025.Group.mkv").write_text("ok")

    task = _single_file_task(download_root)
    directory = DirectoryConfig(id="dir-1", name="Movies", path=str(library_root), download_path=str(download_root))
    service = DirectoryIntegrityService()
    service.library_repo = AsyncListRepo([_library_file_for_task("file-1", task, library_root, "movie.mkv")])
    service.task_repo = AsyncListRepo([task])

    monkeypatch.setattr(integrity_module.settings_service, "list_directories", lambda: [directory])
    monkeypatch.setattr(integrity_module, "LATEST_RESULT_PATH", tmp_path / "latest.json")

    result = await service.scan()

    assert result.items == []


@pytest.mark.asyncio
async def test_directory_integrity_scan_ignores_qb_parts_for_known_downloader_torrent(tmp_path, monkeypatch):
    library_root = tmp_path / "library"
    download_root = tmp_path / "download"
    library_root.mkdir()
    download_root.mkdir()
    (library_root / "movie.mkv").write_text("ok")
    parts_file = download_root / "Single.Movie.2025.Group.mkv.parts"
    parts_file.write_text("parts")
    _set_file_age(parts_file, 3600)

    task = _single_file_task(download_root)
    task.status = TaskStatus.DOWNLOADING
    task.downloader_id = "downloader-1"
    status = TorrentStatus(
        hash=task.torrent_hash,
        name="Single.Movie.2025.Group",
        size=20,
        progress=0.5,
        state=TorrentState.DOWNLOADING,
        downloader_id="downloader-1",
    )
    directory = DirectoryConfig(id="dir-1", name="Movies", path=str(library_root), download_path=str(download_root))
    service = DirectoryIntegrityService()
    service.library_repo = AsyncListRepo([_library_file_for_task("file-1", task, library_root, "movie.mkv")])
    service.task_repo = AsyncListRepo([task])
    service.client_factory = FakeClientFactory({"downloader-1": FakeDownloadClient([status])})

    monkeypatch.setattr(integrity_module.settings_service, "list_directories", lambda: [directory])
    monkeypatch.setattr(integrity_module, "LATEST_RESULT_PATH", tmp_path / "latest.json")

    result = await service.scan()

    assert result.items == []


@pytest.mark.asyncio
async def test_directory_integrity_scan_reports_unrelated_qb_parts_file(tmp_path, monkeypatch):
    library_root = tmp_path / "library"
    download_root = tmp_path / "download"
    library_root.mkdir()
    download_root.mkdir()
    (library_root / "movie.mkv").write_text("ok")
    parts_file = download_root / "orphan.mkv.parts"
    parts_file.write_text("parts")
    _set_file_age(parts_file, 3600)

    task = _single_file_task(download_root)
    task.status = TaskStatus.DOWNLOADING
    task.downloader_id = "downloader-1"
    status = TorrentStatus(
        hash=task.torrent_hash,
        name="Single.Movie.2025.Group",
        size=20,
        progress=0.5,
        state=TorrentState.DOWNLOADING,
        downloader_id="downloader-1",
    )
    directory = DirectoryConfig(id="dir-1", name="Movies", path=str(library_root), download_path=str(download_root))
    service = DirectoryIntegrityService()
    service.library_repo = AsyncListRepo([_library_file_for_task("file-1", task, library_root, "movie.mkv")])
    service.task_repo = AsyncListRepo([task])
    service.client_factory = FakeClientFactory({"downloader-1": FakeDownloadClient([status])})

    monkeypatch.setattr(integrity_module.settings_service, "list_directories", lambda: [directory])
    monkeypatch.setattr(integrity_module, "LATEST_RESULT_PATH", tmp_path / "latest.json")

    result = await service.scan()

    assert [item.issue_type for item in result.items] == [DirectoryIntegrityIssueType.unmanaged_download_entry]
    assert result.items[0].path == str(parts_file.resolve(strict=False))


@pytest.mark.asyncio
async def test_directory_integrity_scan_shares_managed_roots_across_same_download_path(tmp_path, monkeypatch):
    library_root = tmp_path / "library"
    download_root = tmp_path / "download"
    library_root.mkdir()
    download_root.mkdir()
    (library_root / "movie.mkv").write_text("ok")
    torrent_folder = download_root / "Single.Movie.2025.Group"
    torrent_folder.mkdir()
    (torrent_folder / "Single.Movie.2025.Group.mkv").write_text("ok")

    task = _single_file_task(download_root)
    movie_directory = DirectoryConfig(id="dir-1", name="Movies", path=str(library_root), download_path=str(download_root))
    bluray_directory = DirectoryConfig(id="dir-2", name="Movie Discs", path=str(library_root / "bluray"), download_path=str(download_root))
    service = DirectoryIntegrityService()
    service.library_repo = AsyncListRepo([_library_file_for_task("file-1", task, library_root, "movie.mkv")])
    service.task_repo = AsyncListRepo([task])

    monkeypatch.setattr(integrity_module.settings_service, "list_directories", lambda: [movie_directory, bluray_directory])
    monkeypatch.setattr(integrity_module, "LATEST_RESULT_PATH", tmp_path / "latest.json")

    result = await service.scan()

    assert result.items == []
    assert result.summary.logical_size == 4
    assert result.summary.physical_size >= 4
    summaries = {item.directory_id: item for item in result.summary.directories}
    assert summaries["dir-1"].logical_size == 4
    assert summaries["dir-2"].logical_size == 0


@pytest.mark.asyncio
async def test_directory_integrity_scan_ignores_downloads_managed_by_other_directory_on_shared_root(tmp_path, monkeypatch):
    movie_library = tmp_path / "movie-library"
    show_library = tmp_path / "show-library"
    download_root = tmp_path / "download"
    movie_library.mkdir()
    show_library.mkdir()
    download_root.mkdir()
    torrent_folder = download_root / "Single.Movie.2025.Group"
    torrent_folder.mkdir()
    (torrent_folder / "Single.Movie.2025.Group.mkv").write_text("ok")

    task = _single_file_task(download_root)
    movie_directory = DirectoryConfig(id="dir-1", name="Movies", path=str(movie_library), download_path=str(download_root))
    show_directory = DirectoryConfig(id="dir-2", name="Shows", path=str(show_library), download_path=str(download_root))
    service = DirectoryIntegrityService()
    service.library_repo = AsyncListRepo([])
    service.task_repo = AsyncListRepo([task])

    monkeypatch.setattr(integrity_module.settings_service, "list_directories", lambda: [movie_directory, show_directory])
    monkeypatch.setattr(integrity_module, "LATEST_RESULT_PATH", tmp_path / "latest.json")

    result = await service.scan("dir-2")

    assert result.items == []
    assert result.summary.download_logical_size == 0


@pytest.mark.asyncio
async def test_directory_integrity_scan_reports_db_task_missing_downloader_torrent(tmp_path, monkeypatch):
    library_root = tmp_path / "library"
    download_root = tmp_path / "download"
    library_root.mkdir()
    download_root.mkdir()
    (download_root / "Managed").mkdir()
    (download_root / "Managed" / "episode.mkv").write_text("ok")
    (download_root / "Managed" / "missing.mkv").write_text("ok")

    directory = DirectoryConfig(id="dir-1", name="Movies", path=str(library_root), download_path=str(download_root))
    task = _downloader_task(download_root, "task-missing-torrent", "missing-hash")
    (library_root / "movie.mkv").write_text("ok")
    service = DirectoryIntegrityService()
    service.library_repo = AsyncListRepo([_library_file_for_task("file-1", task, library_root, "movie.mkv")])
    service.task_repo = AsyncListRepo([task])
    service.client_factory = FakeClientFactory({"downloader-1": FakeDownloadClient([])})

    monkeypatch.setattr(integrity_module.settings_service, "list_directories", lambda: [directory])
    monkeypatch.setattr(integrity_module, "LATEST_RESULT_PATH", tmp_path / "latest.json")

    result = await service.scan()

    assert [item.issue_type.value for item in result.items] == ["missing_downloader_torrent"]
    assert result.items[0].task_id == "task-missing-torrent"
    assert result.summary.missing_downloader_torrents == 1


@pytest.mark.asyncio
async def test_directory_integrity_scan_ignores_downloader_torrents_without_db_tasks(tmp_path, monkeypatch):
    library_root = tmp_path / "library"
    download_root = tmp_path / "download"
    library_root.mkdir()
    download_root.mkdir()
    (download_root / "Managed").mkdir()
    (download_root / "Managed" / "episode.mkv").write_text("ok")
    (download_root / "Managed" / "missing.mkv").write_text("ok")

    directory = DirectoryConfig(id="dir-1", name="Movies", path=str(library_root), download_path=str(download_root))
    torrent = TorrentStatus(
        hash="hash-1",
        name="Managed",
        size=10,
        progress=1.0,
        state=TorrentState.SEEDING,
        downloader_id="downloader-1",
        save_path=str(download_root),
    )
    task = _downloader_task(download_root, "task-present-torrent", "hash-1")
    (library_root / "movie.mkv").write_text("ok")
    service = DirectoryIntegrityService()
    service.library_repo = AsyncListRepo([_library_file_for_task("file-1", task, library_root, "movie.mkv")])
    service.task_repo = AsyncListRepo([task])
    service.client_factory = FakeClientFactory(
        {
            "downloader-1": FakeDownloadClient(
                [
                    torrent,
                    torrent.model_copy(update={"hash": "extra-hash"}),
                ]
            )
        }
    )

    monkeypatch.setattr(integrity_module.settings_service, "list_directories", lambda: [directory])
    monkeypatch.setattr(integrity_module, "LATEST_RESULT_PATH", tmp_path / "latest.json")

    result = await service.scan()

    assert result.items == []
    assert result.summary.missing_downloader_torrents == 0
    assert result.summary.unhealthy_downloader_torrents == 0


@pytest.mark.asyncio
async def test_directory_integrity_scan_reports_seeding_torrent_with_tracker_error(tmp_path, monkeypatch):
    library_root = tmp_path / "library"
    download_root = tmp_path / "download"
    library_root.mkdir()
    download_root.mkdir()
    (download_root / "Managed").mkdir()
    (download_root / "Managed" / "episode.mkv").write_text("ok")
    (download_root / "Managed" / "missing.mkv").write_text("ok")

    directory = DirectoryConfig(id="dir-1", name="Movies", path=str(library_root), download_path=str(download_root))
    torrent = TorrentStatus(
        hash="hash-1",
        name="Managed",
        size=10,
        progress=1.0,
        state=TorrentState.SEEDING,
        downloader_id="downloader-1",
        save_path=str(download_root),
    )
    task = _downloader_task(download_root, "task-tracker-error", "hash-1")
    task.status = TaskStatus.FINISHED
    (library_root / "movie.mkv").write_text("ok")
    service = DirectoryIntegrityService()
    service.library_repo = AsyncListRepo([_library_file_for_task("file-1", task, library_root, "movie.mkv")])
    service.task_repo = AsyncListRepo([task])
    service.client_factory = FakeClientFactory(
        {
            "downloader-1": FakeDownloadClient(
                [torrent],
                trackers={
                    "hash-1": [
                        {"msg": "This torrent is private"},
                        {"msg": "<none>"},
                        {"msg": "Torrent not registered with this tracker"},
                    ]
                },
            ),
        }
    )

    monkeypatch.setattr(integrity_module.settings_service, "list_directories", lambda: [directory])
    monkeypatch.setattr(integrity_module, "LATEST_RESULT_PATH", tmp_path / "latest.json")

    result = await service.scan()

    assert [item.issue_type.value for item in result.items] == ["unhealthy_downloader_torrent"]
    item = result.items[0]
    assert item.task_id == "task-tracker-error"
    assert item.downloader_state == "seeding"
    assert item.tracker_messages == ["Torrent not registered with this tracker"]
    assert item.reason == "downloader_torrent_tracker_unhealthy"
    assert result.summary.unhealthy_downloader_torrents == 1


@pytest.mark.asyncio
async def test_directory_integrity_scan_reports_finished_paused_downloader_torrent(tmp_path, monkeypatch):
    library_root = tmp_path / "library"
    download_root = tmp_path / "download"
    library_root.mkdir()
    download_root.mkdir()
    (download_root / "Managed").mkdir()
    (download_root / "Managed" / "episode.mkv").write_text("ok")
    (download_root / "Managed" / "missing.mkv").write_text("ok")

    directory = DirectoryConfig(id="dir-1", name="Movies", path=str(library_root), download_path=str(download_root))
    torrent = TorrentStatus(
        hash="hash-1",
        name="Managed",
        size=10,
        progress=1.0,
        state=TorrentState.PAUSED,
        downloader_id="downloader-1",
        save_path=str(download_root),
    )
    task = _downloader_task(download_root, "task-unhealthy-torrent", "hash-1")
    task.status = TaskStatus.FINISHED
    (library_root / "movie.mkv").write_text("ok")
    service = DirectoryIntegrityService()
    service.library_repo = AsyncListRepo([_library_file_for_task("file-1", task, library_root, "movie.mkv")])
    service.task_repo = AsyncListRepo([task])
    service.client_factory = FakeClientFactory(
        {
            "downloader-1": FakeDownloadClient(
                [torrent],
                trackers={
                    "hash-1": [
                        {"msg": "This torrent is private"},
                        {"msg": "这是私有 torrent"},
                        {"msg": "torrent not registered"},
                    ]
                },
            ),
        }
    )

    monkeypatch.setattr(integrity_module.settings_service, "list_directories", lambda: [directory])
    monkeypatch.setattr(integrity_module, "LATEST_RESULT_PATH", tmp_path / "latest.json")

    result = await service.scan()

    assert [item.issue_type.value for item in result.items] == ["unhealthy_downloader_torrent"]
    item = result.items[0]
    assert item.task_id == "task-unhealthy-torrent"
    assert item.repairable is False
    assert item.downloader_state == "paused"
    assert item.downloader_status_message == "paused"
    assert item.tracker_messages == ["torrent not registered"]
    assert result.summary.unhealthy_downloader_torrents == 1


@pytest.mark.asyncio
async def test_directory_integrity_repair_deletes_unmanaged_paths_and_refreshes_missing_downloads(tmp_path, monkeypatch):
    library_root = tmp_path / "library"
    download_root = tmp_path / "download"
    library_root.mkdir()
    download_root.mkdir()
    unmanaged_library = library_root / "extra.mkv"
    unmanaged_download = download_root / "orphan.mkv"
    unmanaged_library.write_text("extra")
    _set_file_age(unmanaged_library, 3600)
    unmanaged_download.write_text("orphan")
    (download_root / "Managed").mkdir()
    (download_root / "Managed" / "episode.mkv").write_text("ok")

    directory = DirectoryConfig(id="dir-1", name="Movies", path=str(library_root), download_path=str(download_root))
    library_repo = RecordingLibraryRepo([_library_file("file-2", library_root / "missing", "gone.mkv")])
    episode_repo = RecordingRemovalRepo()
    artifact_repo = RecordingRemovalRepo()
    download_service = RecordingDownloadService()

    service = DirectoryIntegrityService()
    service.library_repo = library_repo
    service.task_repo = AsyncListRepo([_task(download_root)])
    service.episode_repo = episode_repo
    service.artifact_repo = artifact_repo

    monkeypatch.setattr(integrity_module.settings_service, "list_directories", lambda: [directory])
    monkeypatch.setattr(integrity_module, "LATEST_RESULT_PATH", tmp_path / "latest.json")
    monkeypatch.setattr(integrity_module, "download_service", download_service)

    scan = await service.scan()
    result = await service.repair(DirectoryIntegrityRepairRequest(scan_id=scan.scan_id))

    assert result.repaired_count == 4
    assert result.failed_count == 0
    assert not unmanaged_library.exists()
    assert not unmanaged_download.exists()
    assert episode_repo.removed_ids == ["file-2"]
    assert artifact_repo.removed_ids == ["file-2"]
    assert library_repo.removed_ids == ["file-2"]
    assert download_service.refreshed == ["task-1"]


@pytest.mark.asyncio
async def test_directory_integrity_repair_retries_transfer_for_task_without_library_file(tmp_path, monkeypatch):
    library_root = tmp_path / "library"
    download_root = tmp_path / "download"
    library_root.mkdir()
    download_root.mkdir()
    (download_root / "Managed").mkdir()
    (download_root / "Managed" / "episode.mkv").write_text("ok")
    (download_root / "Managed" / "missing.mkv").write_text("ok")

    directory = DirectoryConfig(id="dir-1", name="Movies", path=str(library_root), download_path=str(download_root))
    download_service = RecordingDownloadService()
    transfer_service = RecordingTransferService()

    service = DirectoryIntegrityService()
    service.library_repo = AsyncListRepo([])
    service.task_repo = AsyncListRepo([_task(download_root)])

    monkeypatch.setattr(integrity_module.settings_service, "list_directories", lambda: [directory])
    monkeypatch.setattr(integrity_module, "LATEST_RESULT_PATH", tmp_path / "latest.json")
    monkeypatch.setattr(integrity_module, "download_service", download_service)
    monkeypatch.setattr(integrity_module, "transfer_service", transfer_service)

    scan = await service.scan()
    result = await service.repair(DirectoryIntegrityRepairRequest(scan_id=scan.scan_id))

    assert result.repaired_count == 1
    assert result.failed_count == 0
    assert transfer_service.transferred == ["task-1"]
    assert download_service.refreshed == []
