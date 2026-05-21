from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.schemas.domain.media import MediaFullInfo, SeasonDetails
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.media_server_sync import MediaServerSyncTargetFile
from app.services.application.workflows.media_server_sync.nfo_plan import media_server_sync_nfo_plan
from app.services.application.workflows.media_server_sync.target import media_server_sync_target


@pytest.mark.asyncio
async def test_movie_disc_nfo_stays_at_movie_root(monkeypatch, tmp_path: Path):
    movie_dir = tmp_path / "Movies" / "Test Movie (2024)"
    index_file = movie_dir / "BDMV" / "index.bdmv"
    index_file.parent.mkdir(parents=True)
    index_file.write_text("x", encoding="utf-8")
    await media_server_sync_nfo_plan.write_nfo_files(
        MediaFullInfo(media_id="tmdb:movie:1", title="Test Movie", media_type=MediaType.movie, year=2024),
        str(index_file),
        [MediaServerSyncTargetFile(destination_path=str(index_file))],
    )

    assert (movie_dir / "movie.nfo").exists()
    assert not (index_file.with_suffix(".nfo")).exists()


def test_movie_disc_root_inference_keeps_chinese_movie_parent(tmp_path: Path):
    movie_dir = tmp_path / "Movies" / "流浪地球 (2019)"
    index_file = movie_dir / "BDMV" / "index.bdmv"
    index_file.parent.mkdir(parents=True)
    index_file.write_text("x", encoding="utf-8")

    result = media_server_sync_target.resolve_media_root_dir(
        MediaFullInfo(media_id="tmdb:movie:1", title="流浪地球", media_type=MediaType.movie, year=2019),
        str(index_file),
        [MediaServerSyncTargetFile(destination_path=str(index_file))],
    )

    assert result == movie_dir


@pytest.mark.asyncio
async def test_tv_disc_nfo_stays_at_show_and_season_root(monkeypatch, tmp_path: Path):
    show_dir = tmp_path / "TV" / "Test Show (2024)"
    season_dir = show_dir / "Season 01"
    index_file = season_dir / "Disc 01" / "BDMV" / "index.bdmv"
    index_file.parent.mkdir(parents=True)
    index_file.write_text("x", encoding="utf-8")
    monkeypatch.setattr(
        "app.services.application.workflows.media_server_sync.nfo_plan.media_service.get_season_details_for_media",
        AsyncMock(return_value=SeasonDetails(id=10, season_number=1, name="Season 1")),
    )

    await media_server_sync_nfo_plan.write_nfo_files(
        MediaFullInfo(media_id="tmdb:tv:1", title="Test Show", media_type=MediaType.tv, year=2024, season_number=1, tmdb_id=1),
        str(index_file),
        [MediaServerSyncTargetFile(destination_path=str(index_file))],
    )

    assert (show_dir / "tvshow.nfo").exists()
    assert (season_dir / "season.nfo").exists()
    assert not (index_file.with_suffix(".nfo")).exists()
