from unittest.mock import AsyncMock

import pytest

from app.schemas.domain.media import MediaFullInfo, MediaSeasonInfo, MediaSimpleInfo
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
    cached_info = AsyncMock(return_value=full)
    provider_info = AsyncMock(side_effect=AssertionError("execution context must not call provider-backed info"))
    monkeypatch.setattr("app.services.domain.media.media_service.execution_snapshot_service.profile_service.simple_info", AsyncMock(return_value=simple))
    monkeypatch.setattr("app.services.domain.media.media_service.execution_snapshot_service.profile_service.cached_info", cached_info)
    monkeypatch.setattr("app.services.domain.media.media_service.profile_service.info", provider_info)

    snapshot = await media_service.resolve_execution_snapshot(
        media_id,
        season_number=2,
        require_tv_season=True,
        require_episode_count=True,
    )

    cached_info.assert_awaited_once_with(media_id)
    provider_info.assert_not_awaited()
    assert snapshot.season_number == 2
    assert snapshot.episodes_count == 8


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
    monkeypatch.setattr("app.services.domain.media.media_service.execution_snapshot_service.profile_service.cached_info", AsyncMock(return_value=full))

    with pytest.raises(DownloadException, match="Sample"):
        await media_service.resolve_execution_snapshot(
            media_id,
            season_number=2,
            require_tv_season=True,
        )
