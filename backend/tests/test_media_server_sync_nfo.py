import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from app.schemas.domain.media import EpisodeInfo, MediaFullInfo, SeasonDetails
from app.schemas.domain.media_context import MediaCapabilities
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.media_server_sync import MediaServerSyncTargetFile
from app.schemas.media_id import MediaID
from app.services.application.workflows.media_server_sync import nfo_plan
from app.services.application.workflows.media_server_sync import pipeline
from app.services.integration.media_server import nfo
from app.services.application.workflows.media_server_sync.pipeline import MediaServerSyncPipeline


def _movie() -> MediaFullInfo:
    return MediaFullInfo(
        media_id=MediaID.parse("tmdb:movie:1"),
        title="Movie",
        year=2026,
        media_type=MediaType.movie,
        tmdb_id=1,
        imdb_id="tt0000001",
        overview='a & b < c > d "e"',
        release_date="2026-01-02",
        duration="118",
        genres=["Drama"],
        studios=["Studio"],
    )


def _tv() -> MediaFullInfo:
    return MediaFullInfo(
        media_id=MediaID.parse("tmdb:tv:2"),
        title="Show",
        year=2026,
        media_type=MediaType.tv,
        tmdb_id=2,
        season_number=1,
        duration="45",
        metadata_capabilities=MediaCapabilities(can_generate_enhanced_nfo=True, has_season_episode_detail=True),
    )


def test_write_nfo_escapes_xml_special_characters(tmp_path: Path):
    parsed = ET.fromstring(nfo.build_movie_nfo(_movie(), tmdb_id=1))
    assert parsed.findtext("plot") == 'a & b < c > d "e"'
    assert parsed.findtext("runtime") == "118"
    assert parsed.findtext("releasedate") == "2026-01-02"
    assert parsed.find("uniqueid[@type='tmdb']").text == "1"
    assert parsed.find("uniqueid[@type='imdb']").text == "tt0000001"


def test_common_nfo_writes_douban_public_rating_when_available():
    media = _movie()
    media.douban_id = "1292052"
    media.vote_average = 9.7
    media.rating_source = "douban"
    root = ET.fromstring(nfo.build_movie_nfo(media, tmdb_id=1))

    assert root.findtext("rating") == "9.7"


def test_common_nfo_skips_rating_when_douban_id_has_no_douban_rating():
    media = _movie()
    media.douban_id = "1292052"
    media.vote_average = 7.2
    media.rating_source = "tmdb"
    root = ET.fromstring(nfo.build_movie_nfo(media, tmdb_id=1))

    assert root.find("rating") is None


def test_common_nfo_writes_tmdb_public_rating_without_douban_id():
    media = _movie()
    media.douban_id = None
    media.vote_average = 7.2
    media.rating_source = "tmdb"
    root = ET.fromstring(nfo.build_movie_nfo(media, tmdb_id=1))

    assert root.findtext("rating") == "7.2"


def test_common_nfo_skips_empty_public_rating():
    media = _movie()
    media.douban_id = None
    media.vote_average = 0
    media.rating_source = "tmdb"
    root = ET.fromstring(nfo.build_movie_nfo(media, tmdb_id=1))

    assert root.find("rating") is None


@pytest.mark.asyncio
async def test_generate_movie_nfo_writes_root_and_anchor_files(tmp_path: Path):
    movie_dir = tmp_path / "Movie"
    movie_dir.mkdir()
    anchor = movie_dir / "Movie.2026.mkv"
    anchor.write_bytes(b"")

    await nfo_plan.media_server_sync_nfo_plan.write_nfo_files(
        _movie(),
        str(anchor),
        media_root_dir=str(movie_dir),
    )

    assert (movie_dir / "movie.nfo").exists()
    assert (movie_dir / "Movie.2026.nfo").exists()


@pytest.mark.asyncio
async def test_tmdb_enrichment_does_not_fallback_networks_to_studios(monkeypatch):
    media = _movie()
    media.primary_metadata_source = "tmdb"
    media.studios = []

    enriched = _movie()
    enriched.studios = []

    async def fake_info(media_id, season_number=None):
        return enriched

    monkeypatch.setattr(pipeline.media_service, "info", fake_info)

    await MediaServerSyncPipeline()._enrich_media_by_primary_source(media)

    assert media.studios == []


@pytest.mark.asyncio
async def test_generate_tv_nfo_uses_season_fallback_for_episode_details(tmp_path: Path, monkeypatch):
    show_dir = tmp_path / "Show"
    season_dir = show_dir / "Season 01"
    season_dir.mkdir(parents=True)
    episode_file = season_dir / "Show.S01E01.mkv"
    episode_file.write_bytes(b"")

    async def fake_episode_info(media, season_number, episode_number):
        return EpisodeInfo(
            id=11,
            season_number=season_number,
            episode_number=episode_number,
            title="",
            overview="",
            runtime=None,
        )

    async def fake_season_details(media, season_number):
        return SeasonDetails(
            id=101,
            season_number=season_number,
            name="Season 1",
            overview="Season overview",
            air_date="2026-01-01",
            episodes=[
                EpisodeInfo(
                    id=11,
                    season_number=season_number,
                    episode_number=1,
                    title="Pilot",
                    overview="Episode overview",
                    air_date="2026-01-03",
                    runtime=44,
                )
            ],
        )

    monkeypatch.setattr(nfo_plan.media_service, "get_episode_info_for_media", fake_episode_info)
    monkeypatch.setattr(nfo_plan.media_service, "get_season_details_for_media", fake_season_details)

    await nfo_plan.media_server_sync_nfo_plan.write_nfo_files(
        _tv(),
        str(episode_file),
        transfer_results=[MediaServerSyncTargetFile(destination_path=str(episode_file), episode_number=1)],
        media_root_dir=str(show_dir),
    )

    episode_nfo = ET.parse(episode_file.with_suffix(".nfo")).getroot()
    assert (show_dir / "tvshow.nfo").exists()
    assert (season_dir / "season.nfo").exists()
    assert episode_nfo.findtext("title") == "Pilot"
    assert episode_nfo.findtext("plot") == "Episode overview"
    assert episode_nfo.findtext("runtime") == "44"


@pytest.mark.asyncio
async def test_generate_tv_nfo_keeps_multi_episode_file_metadata_complete(tmp_path: Path, monkeypatch):
    show_dir = tmp_path / "Show"
    season_dir = show_dir / "Season 10"
    season_dir.mkdir(parents=True)
    episode_file = season_dir / "Show.S10E17E18.mkv"
    episode_file.write_bytes(b"")

    episode_infos = {
        17: EpisodeInfo(
            id=17,
            season_number=10,
            episode_number=17,
            title="The Last One",
            overview="Part one overview",
            runtime=44,
        ),
        18: EpisodeInfo(
            id=18,
            season_number=10,
            episode_number=18,
            title="",
            overview="",
            runtime=None,
        ),
    }

    async def fake_episode_info(media, season_number, episode_number):
        return episode_infos[episode_number]

    async def fake_season_details(media, season_number):
        return SeasonDetails(
            id=101,
            season_number=season_number,
            name="Season 10",
            episodes=list(episode_infos.values()),
        )

    monkeypatch.setattr(nfo_plan.media_service, "get_episode_info_for_media", fake_episode_info)
    monkeypatch.setattr(nfo_plan.media_service, "get_season_details_for_media", fake_season_details)

    await nfo_plan.media_server_sync_nfo_plan.write_nfo_files(
        _tv(),
        str(episode_file),
        transfer_results=[
            MediaServerSyncTargetFile(destination_path=str(episode_file), episode_number=17),
            MediaServerSyncTargetFile(destination_path=str(episode_file), episode_number=18),
        ],
        media_root_dir=str(show_dir),
    )

    episode_nfo = ET.parse(episode_file.with_suffix(".nfo")).getroot()
    assert episode_nfo.findtext("episode") == "17"
    assert episode_nfo.findtext("title") == "The Last One"
    assert episode_nfo.findtext("plot") == "Part one overview"
