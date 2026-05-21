from contextlib import asynccontextmanager
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.clients.qbittorrent import QBittorrentClient
from app.schemas.config import DownloadConfig, QBittorrentConfig, SystemConfig
from app.schemas.domain.download import DownloadTaskCreateInput, TaskContext, TaskData, TaskStatus
from app.schemas.domain.media import MediaExecutionSnapshot
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.resource_attributes import ResourceAttributes
from app.schemas.domain.resource_search import ResourceSearchResult
from app.schemas.domain.torrent import TorrentFileItem, TorrentMetadata, TorrentPayload
from app.schemas.exception import ConfigurationException
from app.schemas.exception.exceptions import DownloadException, DownloadTaskAlreadyExistsException
from app.schemas.integration.common import ClientOperationResult
from app.schemas.media_id import MediaID
from app.services.domain.download.lifecycle import DownloadCreationService


def test_download_config_default_tag_is_aethera_and_trimmed():
    assert DownloadConfig().default_tag == "Aethera"
    assert DownloadConfig(default_tag="  ").default_tag == ""
    assert DownloadConfig(default_tag="  Aethera  ").default_tag == "Aethera"


def test_qbittorrent_add_torrent_file_passes_tags_to_client():
    captured = {}

    class FakeClient:
        def torrents_add(self, **kwargs):
            captured.update(kwargs)
            return "Ok."

    client = QBittorrentClient(QBittorrentConfig(id="qb-1", type="qbittorrent"))

    result = client._qb_add_torrent_file(
        FakeClient(),
        b"torrent-data",
        "/downloads",
        "movies",
        ["Aethera"],
        None,
    )

    assert result == "Ok."
    assert captured["tags"] == ["Aethera"]
    assert captured["use_auto_torrent_management"] is False


@pytest.mark.asyncio
async def test_qbittorrent_add_torrent_file_does_not_sync_priorities_when_add_fails(monkeypatch):
    class FakeClient:
        pass

    client = QBittorrentClient(QBittorrentConfig(id="qb-1", type="qbittorrent"))
    priority_sync = AsyncMock()
    monkeypatch.setattr(client, "authenticate", AsyncMock())
    monkeypatch.setattr(client, "_get_client", AsyncMock(return_value=FakeClient()))
    monkeypatch.setattr(client, "_qb_add_torrent_file", lambda *args: "Fails.")
    monkeypatch.setattr(client, "_apply_file_priorities_after_add", priority_sync)

    result = await client.add_torrent_file(
        torrent_data=b"torrent-data",
        file_priorities=[1, 0],
        torrent_hash="abc",
    )

    assert result.success is False
    assert result.id == "abc"
    priority_sync.assert_not_awaited()


def test_resolve_download_target_wraps_configuration_error_as_i18n_reason(monkeypatch):
    def _raise_configuration(directory_id):
        raise ConfigurationException("backendErrors.config.directoryNotFound", params={"id": directory_id})

    monkeypatch.setattr(
        "app.services.domain.download.lifecycle.directory_service.resolve_download_target",
        _raise_configuration,
    )

    with pytest.raises(DownloadException) as exc_info:
        DownloadCreationService.resolve_download_target("dir-1")

    assert exc_info.value.message_key == "backendErrors.downloadTaskCreateFailed"
    assert exc_info.value.params == {
        "reason_key": "backendErrors.config.directoryNotFound",
        "reason_params": {"id": "dir-1"},
    }


@pytest.mark.asyncio
async def test_create_download_passes_configured_default_tag(monkeypatch):
    media = MediaExecutionSnapshot(media_id=MediaID.parse("tmdb:movie:1"), title="Sample", year=2024)
    search_result = ResourceSearchResult(
        id="result-1",
        title="text 2024",
        site="site-a",
        category="movie",
        size="1 GiB",
        seeders=1,
        leechers=0,
        publish_date=datetime.now(),
        download_url="https://example.com/file.torrent",
        result_id="result-1",
    )
    payload = TorrentPayload(
        metadata=TorrentMetadata(hash="abc123", name="text 2024", size=1, files=[]),
        blob=b"torrent-data",
    )
    captured = {}

    class FakeRepo:
        async def find_by_hash_and_downloader(self, torrent_hash, downloader_id):
            return []

        async def insert(self, task):
            return None

        async def update_task(self, task):
            return None

    class FakeClient:
        async def add_torrent_file(self, **kwargs):
            captured.update(kwargs)
            return ClientOperationResult(success=True)

    class FakeClientFactory:
        def get_download_client(self, downloader_id):
            return FakeClient()

    class FakeTaskService:
        async def ensure_live_torrent_download_path_matches_hash(self, client, torrent_hash, download_path):
            return None

    @asynccontextmanager
    async def fake_download_lock(*args, **kwargs):
        yield True

    service = DownloadCreationService(
        FakeRepo(),
        FakeClientFactory(),
        lambda **kwargs: SimpleNamespace(**kwargs),
        FakeTaskService(),
    )

    monkeypatch.setattr(service, "resolve_download_target", lambda directory_id: SimpleNamespace(
        downloader_id="downloader-1",
        download_path="/downloads",
        download_category="movies",
    ))
    monkeypatch.setattr(
        "app.services.domain.download.lifecycle.torrent_service.fetch_blob",
        AsyncMock(return_value=b"torrent-data"),
    )
    monkeypatch.setattr(
        "app.services.domain.download.lifecycle.build_torrent_payload",
        lambda _blob, desc=None: payload,
    )
    monkeypatch.setattr(
        "app.services.domain.download.lifecycle.settings_service.get_base_system_config",
        lambda: SystemConfig(download=DownloadConfig(default_tag="Aethera")),
    )
    monkeypatch.setattr(
        "app.services.domain.download.lifecycle.settings_service.list_downloaders",
        lambda enabled_only=False: [],
    )
    monkeypatch.setattr(
        "app.services.domain.download.lifecycle.domain_lock_service.acquire_download_create",
        fake_download_lock,
    )
    monkeypatch.setattr(
        "app.services.domain.download.lifecycle.event_service.emit_media",
        lambda *args, **kwargs: None,
    )

    await service.create_download(
        DownloadTaskCreateInput(
            media=media,
            directory_id="dir-1",
            result_id="result-1",
        ),
        search_result,
    )

    assert captured["tags"] == ["Aethera"]


@pytest.mark.asyncio
async def test_create_download_stops_when_client_add_torrent_fails(monkeypatch):
    media = MediaExecutionSnapshot(media_id=MediaID.parse("tmdb:movie:1"), title="Sample", year=2024)
    search_result = ResourceSearchResult(
        id="result-1",
        title="text 2024",
        site="site-a",
        category="movie",
        size="1 GiB",
        seeders=1,
        leechers=0,
        publish_date=datetime.now(),
        download_url="https://example.com/file.torrent",
        result_id="result-1",
    )
    payload = TorrentPayload(
        metadata=TorrentMetadata(hash="abc123", name="text 2024", size=1, files=[]),
        blob=b"torrent-data",
    )
    inserted = []
    updated = []
    deleted = []

    class FakeRepo:
        async def find_by_hash_and_downloader(self, torrent_hash, downloader_id):
            return []

        async def insert(self, task):
            inserted.append(task)
            return None

        async def update_task(self, task):
            updated.append(task)
            return None

        async def delete_by_id(self, task_id):
            deleted.append(task_id)
            return True

    class FakeClient:
        async def add_torrent_file(self, **kwargs):
            return ClientOperationResult(success=False, message="rpc failed")

    class FakeClientFactory:
        def get_download_client(self, downloader_id):
            return FakeClient()

    class FakeTaskService:
        async def ensure_live_torrent_download_path_matches_hash(self, client, torrent_hash, download_path):
            return None

    @asynccontextmanager
    async def fake_download_lock(*args, **kwargs):
        yield True

    service = DownloadCreationService(
        FakeRepo(),
        FakeClientFactory(),
        lambda **kwargs: SimpleNamespace(**kwargs),
        FakeTaskService(),
    )
    monkeypatch.setattr(service, "resolve_download_target", lambda directory_id: SimpleNamespace(
        downloader_id="downloader-1",
        download_path="/downloads",
        download_category="movies",
    ))
    monkeypatch.setattr("app.services.domain.download.lifecycle.torrent_service.fetch_blob", AsyncMock(return_value=b"torrent-data"))
    monkeypatch.setattr("app.services.domain.download.lifecycle.torrent_service.store_blob", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.services.domain.download.lifecycle.build_torrent_payload", lambda _blob, desc=None: payload)
    monkeypatch.setattr("app.services.domain.download.lifecycle.domain_lock_service.acquire_download_create", fake_download_lock)

    with pytest.raises(DownloadException) as exc_info:
        await service.create_download(
            DownloadTaskCreateInput(
                media=media,
                directory_id="dir-1",
                result_id="result-1",
            ),
            search_result,
        )

    assert exc_info.value.message_key == "backendErrors.downloadTaskCreateFailed"
    assert exc_info.value.params == {"reason": "rpc failed"}
    assert len(inserted) == 1
    assert inserted[0].status == TaskStatus.PENDING
    assert deleted == [inserted[0].id]
    assert updated == []


@pytest.mark.asyncio
async def test_create_download_expands_existing_torrent_selection(monkeypatch):
    media_id = MediaID.parse("tmdb:tv:1")
    media = MediaExecutionSnapshot(
        media_id=media_id,
        title="Test Show",
        year=2024,
        media_type=MediaType.tv,
        season_number=1,
        episodes_count=5,
    )
    search_result = ResourceSearchResult(
        id="result-1",
        title="Test.Show.S01E01-E05",
        site="site-a",
        category="tv",
        size="5 GiB",
        seeders=1,
        leechers=0,
        publish_date=datetime.now(),
        download_url="https://example.com/file.torrent",
        result_id="result-1",
    )
    files = [
        TorrentFileItem(
            index=index,
            filename=f"Test.Show.S01E{episode:02d}.mkv",
            size=1,
            attrs=ResourceAttributes(title="Test Show", seasons=[1], episodes=[episode], sources=["WEB-DL"], resource_form="Video File"),
        )
        for index, episode in enumerate(range(1, 6))
    ]
    metadata = TorrentMetadata(
        hash="abc123",
        name="Test.Show.S01E01-E05",
        size=5,
        files=files,
        attrs=ResourceAttributes(title="Test Show", seasons=[1], episodes=list(range(1, 6)), sources=["WEB-DL"], resource_form="Video File"),
        coverage_kind="exact_episodes",
    )
    payload = TorrentPayload(metadata=metadata, blob=b"torrent-data")
    existing_task = TaskData(
        id="task-1",
        media_id=media_id,
        torrent_hash="abc123",
        status=TaskStatus.COMPLETED,
        context=TaskContext(
            download_url="https://example.com/file.torrent",
            media=media,
            directory_id="dir-1",
            selected_files=[0, 1, 2],
        ),
        downloader_id="downloader-1",
        metadata=metadata,
    )
    updated = {}
    priorities = []

    class FakeRepo:
        async def find_by_hash_and_downloader(self, torrent_hash, downloader_id):
            return [existing_task]

        async def insert(self, task):
            raise AssertionError("existing task should be reused")

        async def update_task(self, task):
            updated["task"] = task
            return True

    class FakeClient:
        async def add_torrent_file(self, **kwargs):
            raise AssertionError("existing torrent should not be added again")

        async def set_file_priority(self, torrent_hash, file_ids, priority):
            priorities.append((torrent_hash, list(file_ids), priority))
            return True

    class FakeClientFactory:
        def get_download_client(self, downloader_id):
            return FakeClient()

    class FakeTaskService:
        async def ensure_live_torrent_download_path_matches_hash(self, client, torrent_hash, download_path):
            raise AssertionError("existing task merge should not validate add path")

    @asynccontextmanager
    async def fake_download_lock(*args, **kwargs):
        yield True

    service = DownloadCreationService(
        FakeRepo(),
        FakeClientFactory(),
        lambda **kwargs: SimpleNamespace(**kwargs),
        FakeTaskService(),
    )

    monkeypatch.setattr(service, "resolve_download_target", lambda directory_id: SimpleNamespace(
        downloader_id="downloader-1",
        download_path="/downloads",
        download_category="tv",
    ))
    monkeypatch.setattr(
        "app.services.domain.download.lifecycle.torrent_service.fetch_blob",
        AsyncMock(return_value=b"torrent-data"),
    )
    monkeypatch.setattr(
        "app.services.domain.download.lifecycle.build_torrent_payload",
        lambda _blob, desc=None: payload,
    )
    monkeypatch.setattr(
        "app.services.domain.download.lifecycle.settings_service.list_downloaders",
        lambda enabled_only=False: [],
    )
    monkeypatch.setattr(
        "app.services.domain.download.lifecycle.domain_lock_service.acquire_download_create",
        fake_download_lock,
    )
    monkeypatch.setattr(
        "app.services.domain.download.lifecycle.event_service.emit_media",
        lambda *args, **kwargs: None,
    )

    task = await service.create_download(
        DownloadTaskCreateInput(
            media=media,
            directory_id="dir-1",
            result_id="result-1",
            selected_files=[3, 4],
        ),
        search_result,
    )

    assert task.id == "task-1"
    assert updated["task"].context.selected_files == [0, 1, 2, 3, 4]
    assert updated["task"].status == TaskStatus.DOWNLOADING
    assert priorities == [("abc123", [0, 1, 2, 3, 4], 1)]


@pytest.mark.asyncio
async def test_create_download_attaches_new_season_to_existing_torrent(monkeypatch):
    media_id = MediaID.parse("tmdb:tv:1")
    season_one_media = MediaExecutionSnapshot(
        media_id=media_id,
        title="Test Show",
        year=2024,
        media_type=MediaType.tv,
        season_number=1,
        episodes_count=5,
    )
    season_two_media = season_one_media.model_copy(update={"season_number": 2})
    search_result = ResourceSearchResult(
        id="result-1",
        title="Test.Show.S02E04-E05",
        site="site-a",
        category="tv",
        size="2 GiB",
        seeders=1,
        leechers=0,
        publish_date=datetime.now(),
        download_url="https://example.com/file.torrent",
        result_id="result-1",
    )
    files = [
        TorrentFileItem(
            index=index,
            filename=f"Test.Show.S02E{episode:02d}.mkv",
            size=1,
            attrs=ResourceAttributes(title="Test Show", seasons=[2], episodes=[episode], sources=["WEB-DL"], resource_form="Video File"),
        )
        for index, episode in enumerate(range(1, 6))
    ]
    metadata = TorrentMetadata(
        hash="abc123",
        name="Test.Show.S02E01-E05",
        size=5,
        files=files,
        attrs=ResourceAttributes(title="Test Show", seasons=[2], episodes=list(range(1, 6)), sources=["WEB-DL"], resource_form="Video File"),
        coverage_kind="exact_episodes",
    )
    existing_task = TaskData(
        id="task-1",
        media_id=media_id,
        torrent_hash="abc123",
        status=TaskStatus.DOWNLOADING,
        context=TaskContext(
            download_url="https://example.com/file.torrent",
            media=season_one_media,
            directory_id="dir-1",
            selected_files=[0, 1, 2],
        ),
        downloader_id="downloader-1",
        save_path="/downloads",
        metadata=metadata,
    )
    inserted = {}
    priorities = []

    class FakeRepo:
        async def find_by_hash_and_downloader(self, torrent_hash, downloader_id):
            return [existing_task]

        async def insert(self, task):
            inserted["task"] = task
            return task.id

        async def update_task(self, task):
            raise AssertionError("different season should create a separate task")

    class FakeClient:
        async def add_torrent_file(self, **kwargs):
            raise AssertionError("existing torrent should not be added again")

        async def set_file_priority(self, torrent_hash, file_ids, priority):
            priorities.append((torrent_hash, list(file_ids), priority))
            return True

    class FakeClientFactory:
        def get_download_client(self, downloader_id):
            return FakeClient()

    class FakeTaskService:
        async def ensure_live_torrent_download_path_matches_hash(self, client, torrent_hash, download_path):
            raise AssertionError("existing torrent should not validate add path")

    @asynccontextmanager
    async def fake_download_lock(*args, **kwargs):
        yield True

    service = DownloadCreationService(
        FakeRepo(),
        FakeClientFactory(),
        lambda **kwargs: SimpleNamespace(**kwargs),
        FakeTaskService(),
    )

    monkeypatch.setattr(service, "resolve_download_target", lambda directory_id: SimpleNamespace(
        downloader_id="downloader-1",
        download_path="/downloads",
        download_category="tv",
    ))
    monkeypatch.setattr(
        "app.services.domain.download.lifecycle.torrent_service.fetch_blob",
        AsyncMock(return_value=b"torrent-data"),
    )
    monkeypatch.setattr(
        "app.services.domain.download.lifecycle.build_torrent_payload",
        lambda _blob, desc=None: TorrentPayload(metadata=metadata, blob=b"torrent-data"),
    )
    monkeypatch.setattr(
        "app.services.domain.download.lifecycle.domain_lock_service.acquire_download_create",
        fake_download_lock,
    )
    monkeypatch.setattr(
        "app.services.domain.download.lifecycle.settings_service.list_downloaders",
        lambda enabled_only=False: [],
    )
    monkeypatch.setattr(
        "app.services.domain.download.lifecycle.event_service.emit_media",
        lambda *args, **kwargs: None,
    )

    task = await service.create_download(
        DownloadTaskCreateInput(
            media=season_two_media,
            directory_id="dir-1",
            result_id="result-1",
            selected_files=[3, 4],
        ),
        search_result,
    )

    assert task.id == inserted["task"].id
    assert task.context.media.season_number == 2
    assert task.context.selected_files == [3, 4]
    assert priorities == [("abc123", [0, 1, 2, 3, 4], 1)]


def test_resolve_download_tags_returns_none_for_empty_tag(monkeypatch):
    monkeypatch.setattr(
        "app.services.domain.download.lifecycle.settings_service.get_base_system_config",
        lambda: SystemConfig(download=DownloadConfig(default_tag="")),
    )

    assert DownloadCreationService.resolve_download_tags() is None
