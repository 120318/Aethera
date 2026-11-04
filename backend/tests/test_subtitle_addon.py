from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from app.schemas.config import SubtitlesAddonConfig
from app.schemas.domain.library import LibraryFile
from app.schemas.domain.resource_attributes import ResourceAttributes
from app.schemas.domain.subtitle import SubtitleCandidate, SubtitleInstallRequest
from app.schemas.media_id import MediaID
from app.schemas.exception import InvalidRequestException, SubtitleFileException
from app.services.application.workflows.subtitles.service import (
    SUBTITLE_ARTIFACT_TYPE,
    SubtitleApplicationService,
)
from app.services.integration.subtitles.opensubtitles import OpenSubtitlesClient


def _subtitle_config() -> SubtitlesAddonConfig:
    return SubtitlesAddonConfig(
        enabled=True,
        api_key="key",
        username="user",
        password="password",
    )


def _library_file(video_path: Path) -> LibraryFile:
    return LibraryFile(
        id="file-1",
        task_id="task-1",
        directory_id="directory-1",
        media_id=MediaID.parse("tmdb:tv:1"),
        path=str(video_path.parent),
        file_name=video_path.name,
        file_size=video_path.stat().st_size,
        created_at=1,
        resource_attributes=ResourceAttributes(seasons=[1], episodes=[1]),
    )


def test_opensubtitles_hash_uses_file_size_and_edge_chunks(tmp_path: Path):
    video_path = tmp_path / "episode.mkv"
    video_path.write_bytes(bytes(131072))

    movie_hash, movie_size = SubtitleApplicationService._opensubtitles_hash(video_path)

    assert movie_size == 131072
    assert movie_hash == "0000000000020000"


def test_danmu_sidecar_does_not_satisfy_dialogue_subtitle_check(tmp_path: Path):
    video_path = tmp_path / "episode.mkv"
    video_path.write_bytes(b"video")
    video_path.with_name("episode.danmu.ass").write_text("danmu")

    assert SubtitleApplicationService._has_subtitle(video_path) is False

    video_path.with_name("episode.zh-cn.srt").write_text("subtitle")

    assert SubtitleApplicationService._has_subtitle(video_path) is True


@pytest.mark.asyncio
async def test_fill_missing_isolates_subtitle_scan_os_error_per_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    video_path = tmp_path / "episode.mkv"
    video_path.write_bytes(b"video")
    library_file = _library_file(video_path)
    service = SubtitleApplicationService()
    monkeypatch.setattr(
        "app.services.application.workflows.subtitles.service.library_service.get_files_by_media",
        AsyncMock(return_value=[library_file]),
    )
    monkeypatch.setattr(
        service,
        "_ready_config",
        _subtitle_config,
    )
    monkeypatch.setattr(service, "_has_subtitle", lambda _: (_ for _ in ()).throw(OSError("unavailable")))

    result = await service.fill_missing(library_file.media_id, season_number=1)

    assert result.processed_count == 1
    assert result.failed_count == 1


@pytest.mark.asyncio
async def test_fill_missing_continues_after_recoverable_subtitle_file_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    first_path = tmp_path / "episode-1.mkv"
    second_path = tmp_path / "episode-2.mkv"
    first_path.write_bytes(b"video")
    second_path.write_bytes(b"video")
    first_file = _library_file(first_path)
    second_file = _library_file(second_path).model_copy(update={"id": "file-2"})
    service = SubtitleApplicationService()
    monkeypatch.setattr(
        "app.services.application.workflows.subtitles.service.library_service.get_files_by_media",
        AsyncMock(return_value=[first_file, second_file]),
    )
    monkeypatch.setattr(
        service,
        "_ready_config",
        _subtitle_config,
    )
    monkeypatch.setattr(service, "_has_subtitle", lambda _: False)
    monkeypatch.setattr(
        service,
        "search_for_file",
        AsyncMock(side_effect=[SubtitleFileException("backendErrors.subtitleVideoTooSmall"), []]),
    )

    result = await service.fill_missing(first_file.media_id, season_number=1)

    assert result.processed_count == 2
    assert result.failed_count == 1
    assert result.skipped_count == 1


@pytest.mark.asyncio
async def test_fill_missing_does_not_swallow_batch_configuration_error(monkeypatch: pytest.MonkeyPatch):
    service = SubtitleApplicationService()
    monkeypatch.setattr(
        service,
        "_ready_config",
        Mock(side_effect=InvalidRequestException("backendErrors.subtitleProviderNotConfigured")),
    )

    with pytest.raises(InvalidRequestException, match="backendErrors.subtitleProviderNotConfigured"):
        await service.fill_missing(MediaID.parse("tmdb:tv:1"))


@pytest.mark.asyncio
async def test_fill_missing_skips_ambiguous_multi_file_release(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    video_path = tmp_path / "episode.mkv"
    video_path.write_bytes(bytes(131072))
    library_file = _library_file(video_path)
    service = SubtitleApplicationService()
    monkeypatch.setattr(
        "app.services.application.workflows.subtitles.service.library_service.get_files_by_media",
        AsyncMock(return_value=[library_file]),
    )
    monkeypatch.setattr(service, "_ready_config", _subtitle_config)
    monkeypatch.setattr(service, "_has_subtitle", lambda _: False)
    monkeypatch.setattr(
        service,
        "search_for_file",
        AsyncMock(
            return_value=[
                SubtitleCandidate(
                    id="subtitle-1:123",
                    file_id=123,
                    provider="opensubtitles",
                    language="zh-cn",
                    format="srt",
                    release_file_count=2,
                    cd_number=1,
                )
            ]
        ),
    )
    install_mock = AsyncMock()
    monkeypatch.setattr(service, "install", install_mock)

    result = await service.fill_missing(library_file.media_id, season_number=1)

    assert result.processed_count == 1
    assert result.skipped_count == 1
    install_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_install_writes_jellyfin_language_sidecar_and_records_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    video_path = tmp_path / "Fullmetal.Alchemist.Brotherhood.S01E01.mkv"
    video_path.write_bytes(bytes(131072))
    library_file = _library_file(video_path)
    service = SubtitleApplicationService()
    mark_artifact = AsyncMock()
    refresh_library_file = AsyncMock()

    monkeypatch.setattr(service, "_resolve_video", AsyncMock(return_value=(library_file, video_path)))
    monkeypatch.setattr(
        service,
        "_ready_config",
        _subtitle_config,
    )
    monkeypatch.setattr(OpenSubtitlesClient, "download", AsyncMock(return_value=b"subtitle"))
    monkeypatch.setattr(
        "app.services.application.workflows.subtitles.service.library_service.mark_artifact",
        mark_artifact,
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subtitles.service.refresh_library_file",
        refresh_library_file,
    )

    result = await service.install(
        SubtitleInstallRequest(
            file_id=library_file.id,
            candidate_file_id=123,
            language="zh_CN",
            format="srt",
        )
    )

    expected_path = video_path.with_suffix(".zh-cn.srt")
    assert expected_path.read_bytes() == b"subtitle"
    assert result.path == str(expected_path)
    assert result.artifact_type == SUBTITLE_ARTIFACT_TYPE
    mark_artifact.assert_awaited_once()
    refresh_library_file.assert_awaited_once_with(library_file, str(video_path))
    assert mark_artifact.await_args.kwargs["artifact_type"] == SUBTITLE_ARTIFACT_TYPE


def test_opensubtitles_client_rejects_missing_api_key():
    with pytest.raises(ValueError, match="API key"):
        OpenSubtitlesClient("")._headers()


@pytest.mark.parametrize(
    ("config", "message_key"),
    [
        (SubtitlesAddonConfig(enabled=False), "backendErrors.addonDisabled"),
        (
            SubtitlesAddonConfig(enabled=True, provider="opensubtitles", api_key=""),
            "backendErrors.subtitleProviderNotConfigured",
        ),
        (
            SubtitlesAddonConfig(enabled=True, provider="opensubtitles", api_key="key"),
            "backendErrors.subtitleProviderNotConfigured",
        ),
    ],
)
def test_subtitle_readiness_uses_domain_errors(monkeypatch, config, message_key):
    service = SubtitleApplicationService()
    monkeypatch.setattr(service, "config", lambda: config)

    with pytest.raises(InvalidRequestException) as exc_info:
        service._ready_config()

    assert exc_info.value.message_key == message_key


@pytest.mark.asyncio
async def test_opensubtitles_search_preserves_moviehash_match(monkeypatch):
    response = Mock()
    response.raise_for_status = Mock()
    response.json.return_value = {
        "data": [
            {
                "id": "subtitle-1",
                "attributes": {
                    "language": "zh-cn",
                    "moviehash_match": True,
                    "files": [{"file_id": 123, "file_name": "episode.srt"}],
                },
            }
        ]
    }
    client = AsyncMock()
    client.get.return_value = response
    context = AsyncMock()
    context.__aenter__.return_value = client
    client_factory = Mock(return_value=context)
    monkeypatch.setattr(
        "app.services.integration.subtitles.opensubtitles.httpx.AsyncClient",
        client_factory,
    )

    candidates = await OpenSubtitlesClient("key").search(
        movie_hash="hash",
        movie_size=131072,
        languages=["zh-cn"],
        season_number=1,
        episode_number=1,
    )

    assert candidates[0].hash_matched is True
    assert candidates[0].match_confidence == 1.0
    assert candidates[0].id == "subtitle-1:123"
    client_factory.assert_called_once_with(timeout=30.0, follow_redirects=True)


@pytest.mark.asyncio
async def test_opensubtitles_search_preserves_every_release_file(monkeypatch):
    response = Mock()
    response.raise_for_status = Mock()
    response.json.return_value = {
        "data": [
            {
                "id": "subtitle-1",
                "attributes": {
                    "language": "zh-cn",
                    "files": [
                        {"file_id": 124, "file_name": "episode.cd2.srt", "cd_number": 2},
                        {"file_id": 123, "file_name": "episode.cd1.srt", "cd_number": 1},
                    ],
                },
            }
        ]
    }
    client = AsyncMock()
    client.get.return_value = response
    context = AsyncMock()
    context.__aenter__.return_value = client
    monkeypatch.setattr(
        "app.services.integration.subtitles.opensubtitles.httpx.AsyncClient",
        Mock(return_value=context),
    )

    candidates = await OpenSubtitlesClient("key").search(
        movie_hash="hash",
        movie_size=131072,
        languages=["zh-cn"],
        season_number=1,
        episode_number=1,
    )

    assert [(item.file_id, item.cd_number) for item in candidates] == [(124, 2), (123, 1)]
    assert [item.release_file_count for item in candidates] == [2, 2]
    assert len({item.id for item in candidates}) == 2


@pytest.mark.asyncio
async def test_opensubtitles_download_follows_redirected_file_link(monkeypatch):
    login_response = Mock()
    login_response.raise_for_status = Mock()
    login_response.json.return_value = {
        "token": "user-token",
        "base_url": "api.opensubtitles.com",
    }
    download_response = Mock()
    download_response.raise_for_status = Mock()
    download_response.json.return_value = {"link": "https://download.opensubtitles.com/subtitle.srt"}
    subtitle_response = Mock()
    subtitle_response.raise_for_status = Mock()
    subtitle_response.content = b"subtitle"
    client = AsyncMock()
    client.post.side_effect = [login_response, download_response]
    client.get.return_value = subtitle_response
    context = AsyncMock()
    context.__aenter__.return_value = client
    client_factory = Mock(return_value=context)
    monkeypatch.setattr(
        "app.services.integration.subtitles.opensubtitles.httpx.AsyncClient",
        client_factory,
    )

    content = await OpenSubtitlesClient("key", "user", "password").download(123)

    assert content == b"subtitle"
    client_factory.assert_called_once_with(timeout=30.0, follow_redirects=True)
    assert client.post.await_args_list[0].kwargs["json"] == {"username": "user", "password": "password"}
    assert client.post.await_args_list[1].kwargs["headers"]["Authorization"] == "Bearer user-token"
    client.get.assert_awaited_once_with("https://download.opensubtitles.com/subtitle.srt")
