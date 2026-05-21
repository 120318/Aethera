import time
from pathlib import Path

import pytest

from app.schemas.config import MediaServerSyncConfig
from app.schemas.domain.library import LibraryFile, LibraryFileArtifactStatus, LibraryMediaLayout, LibraryMediaLayoutEntry
from app.schemas.domain.media import EpisodeInfo, MediaFullInfo, SeasonDetails
from app.schemas.domain.media_context import MediaCapabilities
from app.schemas.domain.media_server_sync import MediaServerSyncState
from app.schemas.domain.media_server_sync import MediaServerSyncTargetFile
from app.schemas.domain.media_types import MediaType
from app.schemas.media_id import MediaID
from app.services.application.workflows.media_server_sync.artifacts import media_server_sync_artifacts
from app.services.application.workflows.media_server_sync.needs import media_server_sync_needs
from app.services.domain.library.sidecar_files import library_sidecar_files
from app.services.integration.tmdb.images import to_tmdb_image_url


def _movie(media_id: MediaID | None = None) -> MediaFullInfo:
    return MediaFullInfo(
        media_id=media_id or MediaID.parse("tmdb:movie:1"),
        media_type=MediaType.movie,
        title="Movie",
        year=2026,
    )


def _tv(media_id: MediaID | None = None) -> MediaFullInfo:
    return MediaFullInfo(
        media_id=media_id or MediaID.parse("tmdb:tv:2"),
        media_type=MediaType.tv,
        title="Show",
        year=2026,
        season_number=1,
        metadata_capabilities=MediaCapabilities(can_generate_enhanced_nfo=True, has_season_episode_detail=True),
    )


def _state(media_id: MediaID, last_success_at: float | None = None) -> MediaServerSyncState:
    return MediaServerSyncState(
        media_server_id="jellyfin-1",
        media_id=media_id,
        last_success_at=last_success_at,
    )


def test_tmdb_image_url_normalizes_relative_paths():
    assert to_tmdb_image_url(None) is None
    assert to_tmdb_image_url("https://example.test/poster.jpg") == "https://example.test/poster.jpg"
    assert to_tmdb_image_url("/poster.jpg") == "https://image.tmdb.org/t/p/original/poster.jpg"
    assert to_tmdb_image_url("/poster.jpg", size="w500") == "https://image.tmdb.org/t/p/w500/poster.jpg"


def test_library_sidecar_files_are_generic_file_operations(tmp_path: Path):
    target = tmp_path / "nested" / "sidecar.txt"

    assert library_sidecar_files.missing_paths([target]) == [str(target)]

    library_sidecar_files.write_text_file(target, "hello")

    assert library_sidecar_files.path_exists(target)
    assert library_sidecar_files.missing_paths([target]) == []
    assert target.read_text(encoding="utf-8") == "hello"


def _movie_nfo_text(title: str = "Movie", plot: str = "") -> str:
    return f"<movie><title>{title}</title><plot>{plot}</plot></movie>"


def _tvshow_nfo_text(title: str = "Show", plot: str = "") -> str:
    return f"<tvshow><title>{title}</title><plot>{plot}</plot></tvshow>"


def _season_nfo_text(title: str = "Season 1") -> str:
    return f"<season><title>{title}</title></season>"


def _episode_nfo_text(title: str = "Pilot", plot: str = "Episode overview") -> str:
    return f"<episodedetails><title>{title}</title><plot>{plot}</plot></episodedetails>"


@pytest.mark.asyncio
async def test_media_server_sync_needs_reports_no_library_entries():
    media = _movie()

    needs = await media_server_sync_needs.detect(
        media,
        _state(media.media_id, last_success_at=time.time()),
        MediaServerSyncConfig(),
        LibraryMediaLayout(media_id=media.media_id, media_type=media.media_type),
    )

    assert not needs.should_run
    assert needs.missing_flags == ["no_lib"]


@pytest.mark.asyncio
async def test_media_server_sync_artifact_success_skips_unavailable_enhanced_tv_nfo(tmp_path: Path, monkeypatch):
    media = _tv().model_copy(update={"metadata_capabilities": MediaCapabilities()})
    video = tmp_path / "Show" / "Season 01" / "Show.S01E01.mkv"
    video.parent.mkdir(parents=True)
    video.write_text("video")
    tvshow_nfo = tmp_path / "Show" / "tvshow.nfo"
    tvshow_nfo.write_text("nfo")
    marked = []

    async def fake_mark_artifact(**kwargs):
        marked.append(kwargs)

    monkeypatch.setattr(
        "app.services.application.workflows.media_server_sync.artifacts.library_service.mark_artifact",
        fake_mark_artifact,
    )

    await media_server_sync_artifacts.mark_nfo_artifacts(
        [
            LibraryFile(
                id="file-1",
                task_id="task-1",
                directory_id="dir-1",
                media_id=media.media_id,
                path=str(video.parent),
                file_name=video.name,
                created_at=1.0,
            )
        ],
        media,
        str(video),
        [MediaServerSyncTargetFile(destination_path=str(video), episode_number=1)],
        str(tmp_path / "Show"),
        LibraryFileArtifactStatus.succeeded,
    )

    assert [item["expected_path"] for item in marked] == [str(tvshow_nfo)]
    assert marked[0]["status"].value == "succeeded"


@pytest.mark.asyncio
async def test_media_server_sync_image_artifact_success_requires_existing_file(tmp_path: Path, monkeypatch):
    media = _movie().model_copy(update={"poster_path": "/poster.jpg", "backdrop_path": "/fanart.jpg"})
    video = tmp_path / "Movie" / "Movie.mkv"
    video.parent.mkdir(parents=True)
    video.write_text("video")
    poster = tmp_path / "Movie" / "poster.jpg"
    poster.write_text("poster")
    marked = []

    async def fake_mark_artifact(**kwargs):
        marked.append(kwargs)

    monkeypatch.setattr(
        "app.services.application.workflows.media_server_sync.artifacts.library_service.mark_artifact",
        fake_mark_artifact,
    )

    await media_server_sync_artifacts.mark_image_artifacts(
        [
            LibraryFile(
                id="file-1",
                task_id="task-1",
                directory_id="dir-1",
                media_id=media.media_id,
                path=str(video.parent),
                file_name=video.name,
                created_at=1.0,
            )
        ],
        media,
        str(video),
        str(tmp_path / "Movie"),
        LibraryFileArtifactStatus.succeeded,
    )

    by_path = {item["expected_path"]: item["status"] for item in marked}
    assert by_path[str(poster)].value == "succeeded"
    assert by_path[str(tmp_path / "Movie" / "fanart.jpg")].value == "pending"


@pytest.mark.asyncio
async def test_media_server_sync_needs_reports_movie_nfo_missing(tmp_path: Path):
    media = _movie()
    video = tmp_path / "Movie" / "Movie.mkv"
    video.parent.mkdir()
    video.write_text("video")
    layout = LibraryMediaLayout(
        media_id=media.media_id,
        media_type=media.media_type,
        entries=[
            LibraryMediaLayoutEntry(
                file_id="file-1",
                absolute_path=str(video),
                is_video=True,
            )
        ],
        primary_anchor_file=str(video),
    )

    needs = await media_server_sync_needs.detect(
        media,
        _state(media.media_id, last_success_at=time.time()),
        MediaServerSyncConfig(),
        layout,
    )

    assert needs.should_run
    assert needs.missing_flags == ["movie_nfo_missing"]

    video.with_suffix(".nfo").write_text(_movie_nfo_text())
    needs = await media_server_sync_needs.detect(
        media,
        _state(media.media_id, last_success_at=time.time()),
        MediaServerSyncConfig(),
        layout,
    )

    assert not needs.should_run


@pytest.mark.asyncio
async def test_media_server_sync_needs_reports_movie_nfo_incomplete(tmp_path: Path):
    media = _movie().model_copy(update={"overview": "Movie overview"})
    video = tmp_path / "Movie" / "Movie.mkv"
    video.parent.mkdir()
    video.write_text("video")
    video.with_suffix(".nfo").write_text(_movie_nfo_text(plot=""))
    layout = LibraryMediaLayout(
        media_id=media.media_id,
        media_type=media.media_type,
        entries=[
            LibraryMediaLayoutEntry(
                file_id="file-1",
                absolute_path=str(video),
                is_video=True,
            )
        ],
        primary_anchor_file=str(video),
    )

    needs = await media_server_sync_needs.detect(
        media,
        _state(media.media_id, last_success_at=time.time()),
        MediaServerSyncConfig(),
        layout,
    )

    assert needs.should_run
    assert needs.missing_flags == ["movie_nfo_incomplete"]


@pytest.mark.asyncio
async def test_media_server_sync_needs_reports_tvshow_and_episode_nfo_missing(tmp_path: Path):
    media = _tv()
    video = tmp_path / "Show" / "Season 01" / "Show.S01E01.mkv"
    video.parent.mkdir(parents=True)
    video.write_text("video")
    layout = LibraryMediaLayout(
        media_id=media.media_id,
        media_type=media.media_type,
        entries=[
            LibraryMediaLayoutEntry(
                file_id="file-1",
                absolute_path=str(video),
                is_video=True,
                episode_numbers=[1],
            )
        ],
        primary_anchor_file=str(video),
    )

    needs = await media_server_sync_needs.detect(
        media,
        _state(media.media_id, last_success_at=time.time()),
        MediaServerSyncConfig(),
        layout,
    )

    assert needs.should_run
    assert set(needs.missing_flags) == {"tvshow_nfo_missing", "season_nfo_missing", "episode_nfo_missing"}


@pytest.mark.asyncio
async def test_media_server_sync_needs_reports_episode_nfo_incomplete(tmp_path: Path, monkeypatch):
    media = _tv()
    video = tmp_path / "Show" / "Season 01" / "Show.S01E01.mkv"
    video.parent.mkdir(parents=True)
    video.write_text("video")
    (tmp_path / "Show" / "tvshow.nfo").write_text(_tvshow_nfo_text())
    (tmp_path / "Show" / "Season 01" / "season.nfo").write_text(_season_nfo_text())
    video.with_suffix(".nfo").write_text(_episode_nfo_text(title="", plot=""))
    layout = LibraryMediaLayout(
        media_id=media.media_id,
        media_type=media.media_type,
        entries=[
            LibraryMediaLayoutEntry(
                file_id="file-1",
                absolute_path=str(video),
                is_video=True,
                episode_numbers=[1],
            )
        ],
        primary_anchor_file=str(video),
    )

    async def fake_episode_info(media, season_number, episode_number):
        return EpisodeInfo(
            season_number=season_number,
            episode_number=episode_number,
            title="Pilot",
            overview="Episode overview",
        )

    async def fake_season_details(media, season_number):
        return SeasonDetails(season_number=season_number)

    monkeypatch.setattr("app.services.application.workflows.media_server_sync.nfo_plan.media_service.get_episode_info_for_media", fake_episode_info)
    monkeypatch.setattr("app.services.application.workflows.media_server_sync.nfo_plan.media_service.get_season_details_for_media", fake_season_details)

    needs = await media_server_sync_needs.detect(
        media,
        _state(media.media_id, last_success_at=time.time()),
        MediaServerSyncConfig(),
        layout,
    )

    assert needs.should_run
    assert needs.missing_flags == ["episode_nfo_incomplete"]


@pytest.mark.asyncio
async def test_media_server_sync_needs_targets_only_incomplete_episode_nfo(tmp_path: Path, monkeypatch):
    media = _tv()
    season_dir = tmp_path / "Show" / "Season 01"
    video_one = season_dir / "Show.S01E01.mkv"
    video_two = season_dir / "Show.S01E02.mkv"
    season_dir.mkdir(parents=True)
    video_one.write_text("video")
    video_two.write_text("video")
    (tmp_path / "Show" / "tvshow.nfo").write_text(_tvshow_nfo_text())
    (season_dir / "season.nfo").write_text(_season_nfo_text())
    video_one.with_suffix(".nfo").write_text(_episode_nfo_text(title="Pilot", plot="Episode overview"))
    video_two.with_suffix(".nfo").write_text(_episode_nfo_text(title="", plot=""))
    layout = LibraryMediaLayout(
        media_id=media.media_id,
        media_type=media.media_type,
        entries=[
            LibraryMediaLayoutEntry(
                file_id="file-1",
                absolute_path=str(video_one),
                is_video=True,
                episode_numbers=[1],
            ),
            LibraryMediaLayoutEntry(
                file_id="file-2",
                absolute_path=str(video_two),
                is_video=True,
                episode_numbers=[2],
            ),
        ],
        primary_anchor_file=str(video_one),
    )

    async def fake_episode_info(media, season_number, episode_number):
        return EpisodeInfo(
            season_number=season_number,
            episode_number=episode_number,
            title=f"Episode {episode_number}",
            overview=f"Overview {episode_number}",
        )

    async def fake_season_details(media, season_number):
        return SeasonDetails(season_number=season_number)

    monkeypatch.setattr("app.services.application.workflows.media_server_sync.nfo_plan.media_service.get_episode_info_for_media", fake_episode_info)
    monkeypatch.setattr("app.services.application.workflows.media_server_sync.nfo_plan.media_service.get_season_details_for_media", fake_season_details)

    needs = await media_server_sync_needs.detect(
        media,
        _state(media.media_id, last_success_at=time.time()),
        MediaServerSyncConfig(),
        layout,
    )

    assert needs.should_run
    assert needs.missing_flags == ["episode_nfo_incomplete"]
    assert [item.destination_path for item in needs.transfer_results] == [str(video_two)]


@pytest.mark.asyncio
async def test_media_server_sync_needs_targets_only_missing_episode_nfo(tmp_path: Path):
    media = _tv()
    season_dir = tmp_path / "Show" / "Season 01"
    video_one = season_dir / "Show.S01E01.mkv"
    video_two = season_dir / "Show.S01E02.mkv"
    season_dir.mkdir(parents=True)
    video_one.write_text("video")
    video_two.write_text("video")
    (tmp_path / "Show" / "tvshow.nfo").write_text(_tvshow_nfo_text())
    (season_dir / "season.nfo").write_text(_season_nfo_text())
    video_one.with_suffix(".nfo").write_text(_episode_nfo_text(title="Pilot", plot="Episode overview"))
    layout = LibraryMediaLayout(
        media_id=media.media_id,
        media_type=media.media_type,
        entries=[
            LibraryMediaLayoutEntry(
                file_id="file-1",
                absolute_path=str(video_one),
                is_video=True,
                episode_numbers=[1],
            ),
            LibraryMediaLayoutEntry(
                file_id="file-2",
                absolute_path=str(video_two),
                is_video=True,
                episode_numbers=[2],
            ),
        ],
        primary_anchor_file=str(video_one),
    )

    needs = await media_server_sync_needs.detect(
        media,
        _state(media.media_id, last_success_at=time.time()),
        MediaServerSyncConfig(),
        layout,
    )

    assert needs.should_run
    assert needs.missing_flags == ["episode_nfo_missing"]
    assert [item.destination_path for item in needs.transfer_results] == [str(video_two)]


@pytest.mark.asyncio
async def test_media_server_sync_needs_stale_tv_uses_season_metadata_target_only(tmp_path: Path):
    media = _tv()
    season_dir = tmp_path / "Show" / "Season 01"
    video_one = season_dir / "Show.S01E01.mkv"
    video_two = season_dir / "Show.S01E02.mkv"
    season_dir.mkdir(parents=True)
    video_one.write_text("video")
    video_two.write_text("video")
    (tmp_path / "Show" / "tvshow.nfo").write_text(_tvshow_nfo_text())
    (season_dir / "season.nfo").write_text(_season_nfo_text())
    video_one.with_suffix(".nfo").write_text(_episode_nfo_text(title="Pilot", plot="Episode overview"))
    video_two.with_suffix(".nfo").write_text(_episode_nfo_text(title="Second", plot="Second overview"))
    layout = LibraryMediaLayout(
        media_id=media.media_id,
        media_type=media.media_type,
        entries=[
            LibraryMediaLayoutEntry(
                file_id="file-1",
                absolute_path=str(video_one),
                is_video=True,
                episode_numbers=[1],
            ),
            LibraryMediaLayoutEntry(
                file_id="file-2",
                absolute_path=str(video_two),
                is_video=True,
                episode_numbers=[2],
            ),
        ],
        primary_anchor_file=str(video_one),
    )

    needs = await media_server_sync_needs.detect(
        media,
        _state(media.media_id, last_success_at=time.time() - 8 * 86400),
        MediaServerSyncConfig(),
        layout,
    )

    assert needs.should_run
    assert needs.missing_flags == ["stale"]
    assert [(item.destination_path, item.episode_number) for item in needs.transfer_results] == [(str(video_one), None)]


@pytest.mark.asyncio
async def test_media_server_sync_needs_stale_tv_only_adds_incomplete_episode_targets(tmp_path: Path, monkeypatch):
    media = _tv()
    season_dir = tmp_path / "Show" / "Season 01"
    video_one = season_dir / "Show.S01E01.mkv"
    video_two = season_dir / "Show.S01E02.mkv"
    season_dir.mkdir(parents=True)
    video_one.write_text("video")
    video_two.write_text("video")
    (tmp_path / "Show" / "tvshow.nfo").write_text(_tvshow_nfo_text())
    (season_dir / "season.nfo").write_text(_season_nfo_text())
    video_one.with_suffix(".nfo").write_text(_episode_nfo_text(title="Pilot", plot="Episode overview"))
    video_two.with_suffix(".nfo").write_text(_episode_nfo_text(title="", plot=""))
    layout = LibraryMediaLayout(
        media_id=media.media_id,
        media_type=media.media_type,
        entries=[
            LibraryMediaLayoutEntry(
                file_id="file-1",
                absolute_path=str(video_one),
                is_video=True,
                episode_numbers=[1],
            ),
            LibraryMediaLayoutEntry(
                file_id="file-2",
                absolute_path=str(video_two),
                is_video=True,
                episode_numbers=[2],
            ),
        ],
        primary_anchor_file=str(video_one),
    )

    async def fake_episode_info(media, season_number, episode_number):
        return EpisodeInfo(
            season_number=season_number,
            episode_number=episode_number,
            title=f"Episode {episode_number}",
            overview=f"Overview {episode_number}",
        )

    async def fake_season_details(media, season_number):
        return SeasonDetails(season_number=season_number)

    monkeypatch.setattr("app.services.application.workflows.media_server_sync.nfo_plan.media_service.get_episode_info_for_media", fake_episode_info)
    monkeypatch.setattr("app.services.application.workflows.media_server_sync.nfo_plan.media_service.get_season_details_for_media", fake_season_details)

    needs = await media_server_sync_needs.detect(
        media,
        _state(media.media_id, last_success_at=time.time() - 8 * 86400),
        MediaServerSyncConfig(),
        layout,
    )

    assert needs.should_run
    assert needs.missing_flags == ["episode_nfo_incomplete", "stale"]
    assert [(item.destination_path, item.episode_number) for item in needs.transfer_results] == [
        (str(video_one), None),
        (str(video_two), 2),
    ]


@pytest.mark.asyncio
async def test_media_server_sync_needs_does_not_require_unavailable_episode_plot(tmp_path: Path, monkeypatch):
    media = _tv()
    video = tmp_path / "Show" / "Season 01" / "Show.S01E01.mkv"
    video.parent.mkdir(parents=True)
    video.write_text("video")
    (tmp_path / "Show" / "tvshow.nfo").write_text(_tvshow_nfo_text())
    (tmp_path / "Show" / "Season 01" / "season.nfo").write_text(_season_nfo_text())
    video.with_suffix(".nfo").write_text(_episode_nfo_text(title="Pilot", plot=""))
    layout = LibraryMediaLayout(
        media_id=media.media_id,
        media_type=media.media_type,
        entries=[
            LibraryMediaLayoutEntry(
                file_id="file-1",
                absolute_path=str(video),
                is_video=True,
                episode_numbers=[1],
            )
        ],
        primary_anchor_file=str(video),
    )

    async def fake_episode_info(media, season_number, episode_number):
        return EpisodeInfo(season_number=season_number, episode_number=episode_number, title="Pilot", overview="")

    async def fake_season_details(media, season_number):
        return SeasonDetails(season_number=season_number)

    monkeypatch.setattr("app.services.application.workflows.media_server_sync.nfo_plan.media_service.get_episode_info_for_media", fake_episode_info)
    monkeypatch.setattr("app.services.application.workflows.media_server_sync.nfo_plan.media_service.get_season_details_for_media", fake_season_details)

    needs = await media_server_sync_needs.detect(
        media,
        _state(media.media_id, last_success_at=time.time()),
        MediaServerSyncConfig(),
        layout,
    )

    assert not needs.should_run


@pytest.mark.asyncio
async def test_media_server_sync_needs_does_not_require_enhanced_tv_nfo_without_capability(tmp_path: Path):
    media = _tv().model_copy(update={"metadata_capabilities": MediaCapabilities()})
    video = tmp_path / "Show" / "Season 01" / "Show.S01E01.mkv"
    video.parent.mkdir(parents=True)
    video.write_text("video")
    (tmp_path / "Show" / "tvshow.nfo").write_text(_tvshow_nfo_text())
    layout = LibraryMediaLayout(
        media_id=media.media_id,
        media_type=media.media_type,
        entries=[
            LibraryMediaLayoutEntry(
                file_id="file-1",
                absolute_path=str(video),
                is_video=True,
                episode_numbers=[1],
            )
        ],
        primary_anchor_file=str(video),
    )

    needs = await media_server_sync_needs.detect(
        media,
        _state(media.media_id, last_success_at=time.time()),
        MediaServerSyncConfig(),
        layout,
    )

    assert not needs.should_run


@pytest.mark.asyncio
async def test_media_server_sync_needs_reports_stale_without_missing_nfo(tmp_path: Path):
    media = _movie()
    video = tmp_path / "Movie" / "Movie.mkv"
    video.parent.mkdir()
    video.write_text("video")
    video.with_suffix(".nfo").write_text(_movie_nfo_text())
    layout = LibraryMediaLayout(
        media_id=media.media_id,
        media_type=media.media_type,
        entries=[
            LibraryMediaLayoutEntry(
                file_id="file-1",
                absolute_path=str(video),
                is_video=True,
            )
        ],
        primary_anchor_file=str(video),
    )

    needs = await media_server_sync_needs.detect(
        media,
        _state(media.media_id, last_success_at=time.time() - 31 * 86400),
        MediaServerSyncConfig(stale_after_days_movie=30),
        layout,
    )

    assert needs.should_run
    assert needs.missing_flags == ["stale"]


@pytest.mark.asyncio
async def test_media_server_sync_needs_respects_configured_cold_movie_stale_days(tmp_path: Path):
    media = _movie()
    video = tmp_path / "Movie" / "Movie.mkv"
    video.parent.mkdir()
    video.write_text("video")
    video.with_suffix(".nfo").write_text(_movie_nfo_text())
    layout = LibraryMediaLayout(
        media_id=media.media_id,
        media_type=media.media_type,
        entries=[
            LibraryMediaLayoutEntry(
                file_id="file-1",
                absolute_path=str(video),
                is_video=True,
            )
        ],
        primary_anchor_file=str(video),
    )

    needs = await media_server_sync_needs.detect(
        media,
        _state(media.media_id, last_success_at=time.time() - 8 * 86400),
        MediaServerSyncConfig(stale_after_days_movie=30),
        layout,
    )

    assert not needs.should_run


@pytest.mark.asyncio
async def test_media_server_sync_needs_uses_profile_refresh_tiers_for_stale(tmp_path: Path):
    movie = _movie()
    movie_video = tmp_path / "Movie" / "Movie.mkv"
    movie_video.parent.mkdir()
    movie_video.write_text("video")
    movie_video.with_suffix(".nfo").write_text(_movie_nfo_text())
    movie_layout = LibraryMediaLayout(
        media_id=movie.media_id,
        media_type=movie.media_type,
        entries=[LibraryMediaLayoutEntry(file_id="file-1", absolute_path=str(movie_video), is_video=True)],
        primary_anchor_file=str(movie_video),
    )

    cold_needs = await media_server_sync_needs.detect(
        movie,
        _state(movie.media_id, last_success_at=time.time() - 6 * 3600),
        MediaServerSyncConfig(),
        movie_layout,
    )

    show = _tv().model_copy(
        update={
            "next_episode_to_air": EpisodeInfo(season_number=1, episode_number=2, air_date="2026-05-11", title="Next"),
        }
    )
    show_video = tmp_path / "Show" / "Season 01" / "Show.S01E01.mkv"
    show_video.parent.mkdir(parents=True)
    show_video.write_text("video")
    (tmp_path / "Show" / "tvshow.nfo").write_text(_tvshow_nfo_text())
    (tmp_path / "Show" / "Season 01" / "season.nfo").write_text(_season_nfo_text())
    show_video.with_suffix(".nfo").write_text(_episode_nfo_text())
    show_layout = LibraryMediaLayout(
        media_id=show.media_id,
        media_type=show.media_type,
        entries=[
            LibraryMediaLayoutEntry(
                file_id="file-2",
                absolute_path=str(show_video),
                is_video=True,
                episode_numbers=[1],
            )
        ],
        primary_anchor_file=str(show_video),
    )

    hot_needs = await media_server_sync_needs.detect(
        show,
        _state(show.media_id, last_success_at=time.time() - 2 * 3600),
        MediaServerSyncConfig(),
        show_layout,
    )

    assert not cold_needs.should_run
    assert hot_needs.should_run
    assert hot_needs.missing_flags == ["stale"]
