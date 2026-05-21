from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.schemas.media_id import MediaID
from app.schemas.domain.media_source import MediaSourceLookup
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.media import MediaSeasonInfo
from app.schemas.integration.media.provider import ProviderRating
from app.services.domain.media.provider.service import MediaProviderService


def _tmdb_details(*, provider_id: int, media_type: str):
    return SimpleNamespace(
        provider_id=provider_id,
        title="Avatar" if media_type == "movie" else "Breaking Bad",
        original_title="Avatar" if media_type == "movie" else "Breaking Bad",
        overview="Plot",
        release_date="2009-12-18" if media_type == "movie" else None,
        theatrical_release_date="2009-12-18" if media_type == "movie" else None,
        digital_release_date=None,
        first_air_date=None if media_type == "movie" else "2008-01-20",
        poster_path="/poster.jpg",
        backdrop_path="/backdrop.jpg",
        genres=["Drama"],
        actors=[],
        directors=[],
        studios=[],
        networks=[],
        runtime="162" if media_type == "movie" else "47",
        seasons=[MediaSeasonInfo(season_number=1, episode_count=62)] if media_type == "tv" else [],
        seasons_count=1 if media_type == "tv" else None,
        episodes_count=62 if media_type == "tv" else None,
        selected_season_details=None,
        next_episode_to_air=None,
        status="Released" if media_type == "movie" else "Ended",
        original_language="en",
        external_ids=SimpleNamespace(imdb_id="tt0499549", tvdb_id="121361" if media_type == "tv" else None),
        rating=SimpleNamespace(value=8.8, count=1234),
    )


@pytest.mark.asyncio
async def test_tmdb_movie_info_is_marked_as_tmdb_primary_source(monkeypatch):
    service = MediaProviderService()
    monkeypatch.setattr(
        service.detail,
        "get_tmdb_detail_bundle",
        AsyncMock(return_value=(_tmdb_details(provider_id=19995, media_type="movie"), [])),
    )
    monkeypatch.setattr(
        service.mapping,
        "get_cached_tmdb_mapping",
        AsyncMock(return_value=(None, None, None, None, None)),
    )

    media = await service.info(MediaID.parse("tmdb:movie:19995"))

    assert media is not None
    assert media.primary_metadata_source == "tmdb"
    assert media.metadata_capabilities.has_enhanced_detail is True
    assert media.metadata_capabilities.has_movie_release_window is True


@pytest.mark.asyncio
async def test_tmdb_movie_info_uses_douban_rating_when_douban_id_is_cached(monkeypatch):
    service = MediaProviderService()
    monkeypatch.setattr(
        service.detail,
        "get_tmdb_detail_bundle",
        AsyncMock(return_value=(_tmdb_details(provider_id=19995, media_type="movie"), [])),
    )
    monkeypatch.setattr(
        service.mapping,
        "get_cached_tmdb_mapping",
        AsyncMock(return_value=(None, None, "1292052", None, None)),
    )
    monkeypatch.setattr(
        "app.services.domain.media.provider.detail.get_source_vendors",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        service.detail,
        "resolve_douban_rating",
        AsyncMock(return_value=ProviderRating(value=9.2, count=4567)),
    )

    media = await service.info(MediaID.parse("tmdb:movie:19995"))

    assert media is not None
    assert media.douban_id == "1292052"
    assert media.vote_average == 9.2
    assert media.rating_count == 4567
    assert media.vote_count == 4567
    assert media.rating_source == "douban"


@pytest.mark.asyncio
async def test_tmdb_tv_info_shows_empty_douban_rating_when_douban_detail_rating_is_empty(monkeypatch):
    service = MediaProviderService()
    details = _tmdb_details(provider_id=285838, media_type="tv")
    details.rating = SimpleNamespace(value=6.4, count=88)
    monkeypatch.setattr(
        service.detail,
        "get_tmdb_detail_bundle",
        AsyncMock(return_value=(details, [])),
    )
    monkeypatch.setattr(
        service.mapping,
        "get_cached_tmdb_mapping",
        AsyncMock(return_value=(None, None, "37125831", None, None)),
    )
    monkeypatch.setattr(
        "app.services.domain.media.provider.detail.get_source_vendors",
        AsyncMock(return_value=[]),
    )

    douban_client = SimpleNamespace(
        get_subject_detail=AsyncMock(return_value=SimpleNamespace(
            title="Sample",
            rating=ProviderRating(value=0.0, count=0),
            vendors=[],
            episodes_count=None,
        )),
        search_movie=AsyncMock(),
    )
    monkeypatch.setattr(service.clients, "get_douban_client", lambda: douban_client)

    media = await service.info(MediaID.parse("tmdb:tv:285838"))

    assert media is not None
    assert media.douban_id == "37125831"
    assert media.vote_average is None
    assert media.rating_count is None
    assert media.vote_count is None
    assert media.rating_source == "douban"
    douban_client.search_movie.assert_not_awaited()


@pytest.mark.asyncio
async def test_tmdb_tv_info_is_marked_as_tmdb_primary_source(monkeypatch):
    service = MediaProviderService()
    monkeypatch.setattr(
        service.detail,
        "get_tmdb_detail_bundle",
        AsyncMock(return_value=(_tmdb_details(provider_id=1396, media_type="tv"), [])),
    )
    monkeypatch.setattr(
        service.mapping,
        "get_cached_tmdb_mapping",
        AsyncMock(return_value=(None, None, None, None, None)),
    )

    media = await service.info(MediaID.parse("tmdb:tv:1396"))

    assert media is not None
    assert media.primary_metadata_source == "tmdb"
    assert media.metadata_capabilities.has_enhanced_detail is True
    assert media.metadata_capabilities.has_schedule is True
    assert media.metadata_capabilities.has_season_episode_detail is True


@pytest.mark.asyncio
async def test_attach_source_tmdb_mapping_keeps_episode_count_override_season_scoped(monkeypatch):
    service = MediaProviderService()
    details = _tmdb_details(provider_id=1396, media_type="tv")
    details.seasons = [
        MediaSeasonInfo(season_number=1, episode_count=10, air_date="2024-01-01"),
        MediaSeasonInfo(season_number=2, episode_count=12, air_date="2025-01-01"),
    ]
    douban_client = SimpleNamespace(
        get_subject_detail=AsyncMock(return_value=SimpleNamespace(title="Breaking Bad Season 2", year=2025)),
    )
    set_cached = AsyncMock()
    monkeypatch.setattr(service.clients, "get_douban_client", lambda: douban_client)
    monkeypatch.setattr(service.detail, "get_tmdb_detail_bundle", AsyncMock(return_value=(details, [])))
    monkeypatch.setattr(service.mapping, "set_cached_tmdb_mapping", set_cached)

    media_id = await service.attach_source_tmdb_mapping(
        MediaSourceLookup(source="douban", source_id="36666666", media_type=MediaType.tv),
        tmdb_id=1396,
        season_number=2,
        episode_count_override=8,
    )

    assert str(media_id) == "tmdb:tv:1396"
    assert set_cached.await_args_list[0].args[4:6] == (2, 8)
    assert set_cached.await_args_list[1].args[4:6] == (2, 8)


@pytest.mark.asyncio
async def test_attach_source_tmdb_mapping_uses_default_tmdb_season(monkeypatch):
    service = MediaProviderService()
    details = _tmdb_details(provider_id=1396, media_type="tv")
    details.seasons = [MediaSeasonInfo(season_number=1, episode_count=10)]
    douban_client = SimpleNamespace(
        get_subject_detail=AsyncMock(return_value=SimpleNamespace(title="Breaking Bad", year=None)),
    )
    set_cached = AsyncMock()
    monkeypatch.setattr(service.clients, "get_douban_client", lambda: douban_client)
    monkeypatch.setattr(service.detail, "get_tmdb_detail_bundle", AsyncMock(return_value=(details, [])))
    monkeypatch.setattr(service.mapping, "set_cached_tmdb_mapping", set_cached)

    media_id = await service.attach_source_tmdb_mapping(
        MediaSourceLookup(source="douban", source_id="36666666", media_type=MediaType.tv),
        tmdb_id=1396,
    )

    assert str(media_id) == "tmdb:tv:1396"
    assert set_cached.await_args_list[0].args[4] == 1
    assert set_cached.await_args_list[1].args[4] == 1
