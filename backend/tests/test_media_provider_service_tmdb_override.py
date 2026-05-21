from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.schemas.domain.media import MediaSeasonInfo
from app.schemas.media_id import MediaID
from app.services.domain.media.provider.service import MediaProviderService


def _tmdb_details(provider_id: int) -> SimpleNamespace:
    return SimpleNamespace(
        provider_id=provider_id,
        title="Override Movie",
        original_title="Override Movie",
        overview="Plot",
        release_date="2024-01-01",
        first_air_date=None,
        poster_path="/poster.jpg",
        backdrop_path="/backdrop.jpg",
        genres=["Drama"],
        actors=[],
        directors=[],
        studios=[],
        networks=[],
        runtime="120",
        seasons=[],
        seasons_count=None,
        episodes_count=None,
        selected_season_details=None,
        next_episode_to_air=None,
        status="Released",
        original_language="en",
        external_ids=SimpleNamespace(imdb_id="tt9999999", tvdb_id=None),
        rating=SimpleNamespace(value=8.0, count=100),
    )


@pytest.mark.asyncio
async def test_tmdb_provider_info_prefers_cached_mapping_tmdb_id(monkeypatch):
    service = MediaProviderService()
    mid = MediaID.parse("tmdb:movie:19995")

    monkeypatch.setattr(
        service.mapping,
        "get_cached_tmdb_mapping",
        AsyncMock(return_value=(12345, "tt9999999", None, None, None)),
    )
    detail_bundle_mock = AsyncMock(return_value=(_tmdb_details(12345), []))
    monkeypatch.setattr(service.detail, "get_tmdb_detail_bundle", detail_bundle_mock)

    media = await service.info(mid)

    assert media is not None
    assert media.tmdb_id == 12345
    assert media.primary_metadata_source == "tmdb"
    detail_bundle_mock.assert_awaited_once_with(
        12345,
        "movie",
        season_number=None,
        include_default_season_details=False,
        default_season_year=None,
    )


@pytest.mark.asyncio
async def test_tmdb_provider_tv_info_does_not_select_cached_alias_season(monkeypatch):
    service = MediaProviderService()
    mid = MediaID.parse("tmdb:tv:19995")
    details = _tmdb_details(12345)
    details.first_air_date = "2024-01-01"
    details.release_date = None
    details.status = "Returning Series"
    details.seasons = [
        MediaSeasonInfo(season_number=1, episode_count=8, air_date="2023-01-01", name="S1"),
        MediaSeasonInfo(season_number=3, episode_count=10, air_date="2025-01-01", name="S3"),
    ]
    details.episodes_count = 10

    monkeypatch.setattr(
        service.mapping,
        "get_cached_tmdb_mapping",
        AsyncMock(return_value=(12345, "tt9999999", None, 3, None)),
    )
    monkeypatch.setattr(service.detail, "get_tmdb_detail_bundle", AsyncMock(return_value=(details, [])))

    media = await service.info(mid)

    assert media is not None
    assert media.tmdb_id == 12345
    assert media.season_number is None
    assert media.primary_metadata_source == "tmdb"
