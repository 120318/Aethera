from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.schemas.config import SubtitlesAddonConfig
from app.schemas.domain.library import LibraryFile
from app.schemas.domain.resource_attributes import ResourceAttributes
from app.schemas.domain.subtitle import SubtitleInstallRequest
from app.schemas.media_id import MediaID
from app.services.application.workflows.subtitles.service import (
    SUBTITLE_ARTIFACT_TYPE,
    SubtitleApplicationService,
)
from app.services.integration.subtitles.opensubtitles import OpenSubtitlesClient


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
    monkeypatch.setattr(service, "_has_subtitle", lambda _: (_ for _ in ()).throw(OSError("unavailable")))

    result = await service.fill_missing(library_file.media_id, season_number=1)

    assert result.processed_count == 1
    assert result.failed_count == 1


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
        lambda: SubtitlesAddonConfig(enabled=True, api_key="key"),
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
