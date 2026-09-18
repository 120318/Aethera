from unittest.mock import AsyncMock

import pytest

from app.api.v1.media.episode_count_override import (
    UpdateEpisodeCountOverrideRequest,
    update_episode_count_override,
)
from app.schemas.media_id import MediaID


@pytest.mark.asyncio
async def test_update_episode_count_override_route_does_not_require_tmdb(monkeypatch):
    media_id = MediaID.parse("tmdb:tv:19995")
    update_mock = AsyncMock()
    monkeypatch.setattr(
        "app.api.v1.media.episode_count_override.media_service.update_episode_count_override",
        update_mock,
    )

    response = await update_episode_count_override(
        UpdateEpisodeCountOverrideRequest(season_number=4, episode_count_override=13),
        mid=media_id,
    )

    assert response.media_id == media_id
    assert response.season_number == 4
    assert response.episode_count_override == 13
    update_mock.assert_awaited_once_with(
        media_id,
        season_number=4,
        episode_count_override=13,
    )
