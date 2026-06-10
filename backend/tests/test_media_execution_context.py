from unittest.mock import AsyncMock

import pytest

from app.schemas.domain.media import EpisodeInfo, MediaFullInfo, MediaSeasonInfo, MediaSimpleInfo
from app.schemas.domain.media_types import MediaType
from app.schemas.exception import DownloadException
from app.schemas.media_id import MediaID
from app.services.domain.media import media_service


@pytest.mark.asyncio
async def test_resolve_tv_season_snapshot_uses_full_profile_season_episode_count(monkeypatch):
    media_id = MediaID.parse("tmdb:tv:42")
    simple = MediaSimpleInfo(
        media_id=media_id,
        title="Test Show",
        year=2026,
        media_type=MediaType.tv,
        episodes_count=30,
        seasons_count=3,
    )
    full = MediaFullInfo(
        media_id=media_id,
        title="Test Show",
        year=2026,
        media_type=MediaType.tv,
        episodes_count=30,
        seasons_count=3,
        seasons=[
            MediaSeasonInfo(season_number=1, episode_count=10),
            MediaSeasonInfo(season_number=2, episode_count=8),
        ],
    )
    profile_snapshot = AsyncMock(return_value=full)
    provider_info = AsyncMock(side_effect=AssertionError("execution context must not call provider-backed info"))
    monkeypatch.setattr("app.services.domain.media.media_service.execution_snapshot_service.profile_service.simple_info", AsyncMock(return_value=simple))
    monkeypatch.setattr("app.services.domain.media.media_service.execution_snapshot_service._snapshot_from_profile", profile_snapshot)
    monkeypatch.setattr("app.services.domain.media.media_service.profile_service.info", provider_info)

    snapshot = await media_service.resolve_execution_snapshot(
        media_id,
        season_number=2,
        require_tv_season=True,
        require_episode_count=True,
    )

    profile_snapshot.assert_awaited_once_with(media_id, season_number=None)
    provider_info.assert_not_awaited()
    assert snapshot.season_number == 2
    assert snapshot.episodes_count == 8


@pytest.mark.asyncio
async def test_resolve_tv_season_snapshot_uses_cached_season_douban_id(monkeypatch):
    media_id = MediaID.parse("tmdb:tv:233295")
    full = MediaFullInfo(
        media_id=media_id,
        title="仙剑奇侠传三",
        year=2025,
        media_type=MediaType.tv,
        episodes_count=36,
        seasons_count=1,
        seasons=[
            MediaSeasonInfo(
                season_number=1,
                episode_count=36,
                douban_id="36053703",
            )
        ],
    )
    monkeypatch.setattr("app.services.domain.media.media_service.execution_snapshot_service.profile_service.simple_info", AsyncMock(return_value=None))
    monkeypatch.setattr("app.services.domain.media.media_service.execution_snapshot_service._snapshot_from_profile", AsyncMock(return_value=full))

    snapshot = await media_service.resolve_execution_snapshot(
        media_id,
        season_number=1,
        require_tv_season=True,
    )

    assert snapshot.season_number == 1
    assert snapshot.douban_id == "36053703"


@pytest.mark.asyncio
async def test_resolve_tv_season_snapshot_includes_cached_schedule_scope(monkeypatch):
    media_id = MediaID.parse("tmdb:tv:223911")
    simple = MediaSimpleInfo(
        media_id=media_id,
        title="Test Show",
        year=2026,
        media_type=MediaType.tv,
        episodes_count=200,
        seasons_count=1,
        aired_episode_count=0,
        next_episode_to_air=None,
    )
    full = MediaFullInfo(
        media_id=media_id,
        title="Test Show",
        year=2026,
        media_type=MediaType.tv,
        episodes_count=200,
        seasons_count=1,
        season_number=1,
        seasons=[MediaSeasonInfo(season_number=1, episode_count=200)],
        aired_episode_count=143,
        next_episode_to_air=EpisodeInfo(season_number=1, episode_number=144, air_date="2026-06-07"),
    )
    profile_snapshot = AsyncMock(return_value=full)
    monkeypatch.setattr("app.services.domain.media.media_service.execution_snapshot_service.profile_service.simple_info", AsyncMock(return_value=simple))
    monkeypatch.setattr("app.services.domain.media.media_service.execution_snapshot_service._snapshot_from_profile", profile_snapshot)

    snapshot = await media_service.resolve_execution_snapshot(
        media_id,
        season_number=1,
        require_tv_season=True,
        include_schedule_snapshot=True,
    )

    profile_snapshot.assert_awaited_once_with(media_id, season_number=1)
    assert snapshot.aired_episode_count == 143
    assert snapshot.next_episode_to_air is not None
    assert snapshot.next_episode_to_air.episode_number == 144


@pytest.mark.asyncio
async def test_resolve_tv_season_snapshot_clears_unknown_cached_season_episode_count(monkeypatch):
    media_id = MediaID.parse("tmdb:tv:233295")
    full = MediaFullInfo(
        media_id=media_id,
        title="仙剑奇侠传三",
        year=2025,
        media_type=MediaType.tv,
        episodes_count=36,
        seasons_count=1,
        seasons=[MediaSeasonInfo(season_number=1, episode_count=None, douban_id="36053703")],
    )
    monkeypatch.setattr("app.services.domain.media.media_service.execution_snapshot_service.profile_service.simple_info", AsyncMock(return_value=None))
    monkeypatch.setattr("app.services.domain.media.media_service.execution_snapshot_service._snapshot_from_profile", AsyncMock(return_value=full))

    snapshot = await media_service.resolve_execution_snapshot(
        media_id,
        season_number=1,
        require_tv_season=True,
    )

    assert snapshot.season_number == 1
    assert snapshot.episodes_count is None


@pytest.mark.asyncio
async def test_resolve_tv_season_snapshot_rejects_missing_cached_season_without_using_total_count(monkeypatch):
    media_id = MediaID.parse("tmdb:tv:43")
    full = MediaFullInfo(
        media_id=media_id,
        title="Test Show",
        year=2026,
        media_type=MediaType.tv,
        episodes_count=30,
        seasons_count=3,
        seasons=[MediaSeasonInfo(season_number=1, episode_count=10)],
    )
    monkeypatch.setattr("app.services.domain.media.media_service.execution_snapshot_service.profile_service.simple_info", AsyncMock(return_value=None))
    monkeypatch.setattr("app.services.domain.media.media_service.execution_snapshot_service._snapshot_from_profile", AsyncMock(return_value=full))

    with pytest.raises(DownloadException, match="backendErrors.mediaExecutionSnapshotSeasonMissing"):
        await media_service.resolve_execution_snapshot(
            media_id,
            season_number=2,
            require_tv_season=True,
        )
