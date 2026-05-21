from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.v1.calendar.airings import list_airings
from app.schemas.domain.managed_media_profile import ManagedMediaProfile
from app.schemas.domain.schedule import ScheduleAiring
from app.schemas.media_id import MediaID


def _profile(media_id: MediaID, *, airings: list[ScheduleAiring], detail_ready: bool = True) -> ManagedMediaProfile:
    return ManagedMediaProfile(
        media_id=media_id,
        media_type=media_id.media_type,
        title="Sample",
        year=2026,
        poster_path="/poster.jpg",
        primary_metadata_source="tmdb",
        airings=airings,
        detail_ready=detail_ready,
        last_seen_at=1,
        created_at=1,
        updated_at=1,
    )


@pytest.mark.asyncio
async def test_calendar_airings_reads_profile_snapshots_and_keeps_seasons_separate(monkeypatch):
    media_id = MediaID.parse("tmdb:tv:1")
    subscriptions = [
        SimpleNamespace(media_id=media_id, season_number=1, active=True, followed=True),
        SimpleNamespace(media_id=media_id, season_number=2, active=True, followed=True),
    ]

    async def fake_list():
        return subscriptions

    profile = _profile(
        media_id,
        airings=[
            ScheduleAiring(date="2026-01-01", kind="tv_episode_air", season_number=1, episode_number=1, episode_title="S1E1"),
            ScheduleAiring(date="2026-01-02", kind="tv_episode_air", season_number=2, episode_number=1, episode_title="S2E1"),
        ],
    )

    monkeypatch.setattr("app.services.application.views.calendar.service.subscription_query_service.list_states", fake_list)
    monkeypatch.setattr("app.services.application.views.calendar.service.media_service.list_profiles_by_media_targets", AsyncMock(return_value={"tmdb:tv:1:1": profile, "tmdb:tv:1:2": profile}))
    refresh_mock = AsyncMock()
    monkeypatch.setattr("app.services.application.views.calendar.service.media_service.refresh_schedule_snapshot", refresh_mock)

    response = await list_airings(from_date="2026-01-01", to_date="2026-01-31", scope="all")

    refresh_mock.assert_not_awaited()
    assert [item.season_number for item in response.data] == [1, 2]


@pytest.mark.asyncio
async def test_calendar_airings_does_not_refresh_empty_snapshot(monkeypatch):
    media_id = MediaID.parse("tmdb:tv:1")
    subscriptions = [SimpleNamespace(media_id=media_id, season_number=1, active=True, followed=True)]
    empty_profile = _profile(media_id, airings=[])

    async def fake_list():
        return subscriptions

    monkeypatch.setattr("app.services.application.views.calendar.service.subscription_query_service.list_states", fake_list)
    monkeypatch.setattr("app.services.application.views.calendar.service.media_service.list_profiles_by_media_targets", AsyncMock(return_value={"tmdb:tv:1:1": empty_profile}))
    refresh_mock = AsyncMock()
    monkeypatch.setattr("app.services.application.views.calendar.service.media_service.refresh_schedule_snapshot", refresh_mock)

    response = await list_airings(from_date="2026-01-01", to_date="2026-01-31", scope="all")

    refresh_mock.assert_not_awaited()
    assert response.count == 0
    assert response.data == []


@pytest.mark.asyncio
async def test_calendar_airings_does_not_refresh_when_target_season_missing(monkeypatch):
    media_id = MediaID.parse("tmdb:tv:1")
    subscriptions = [SimpleNamespace(media_id=media_id, season_number=2, active=True, followed=True)]
    stale_profile = _profile(
        media_id,
        airings=[
            ScheduleAiring(date="2026-01-01", kind="tv_episode_air", season_number=1, episode_number=1, episode_title="S1E1"),
        ],
    )

    async def fake_list():
        return subscriptions

    monkeypatch.setattr("app.services.application.views.calendar.service.subscription_query_service.list_states", fake_list)
    monkeypatch.setattr("app.services.application.views.calendar.service.media_service.list_profiles_by_media_targets", AsyncMock(return_value={"tmdb:tv:1:2": stale_profile}))
    refresh_mock = AsyncMock()
    monkeypatch.setattr("app.services.application.views.calendar.service.media_service.refresh_schedule_snapshot", refresh_mock)

    response = await list_airings(from_date="2026-01-01", to_date="2026-01-31", scope="all")

    refresh_mock.assert_not_awaited()
    assert response.count == 0
    assert response.data == []


@pytest.mark.asyncio
async def test_calendar_airings_does_not_refresh_placeholder_profile(monkeypatch):
    media_id = MediaID.parse("tmdb:movie:1")
    subscriptions = [SimpleNamespace(media_id=media_id, season_number=None, active=False, followed=True)]
    placeholder_profile = _profile(media_id, airings=[], detail_ready=False)

    async def fake_list():
        return subscriptions

    monkeypatch.setattr("app.services.application.views.calendar.service.subscription_query_service.list_states", fake_list)
    monkeypatch.setattr("app.services.application.views.calendar.service.media_service.list_profiles_by_media_targets", AsyncMock(return_value={"tmdb:movie:1:": placeholder_profile}))
    refresh_mock = AsyncMock()
    monkeypatch.setattr("app.services.application.views.calendar.service.media_service.refresh_schedule_snapshot", refresh_mock)

    response = await list_airings(from_date="2026-01-01", to_date="2026-01-31", scope="all")

    refresh_mock.assert_not_awaited()
    assert response.count == 0
    assert response.data == []


@pytest.mark.asyncio
async def test_calendar_airings_ignores_refresh_failures_because_it_does_not_refresh(monkeypatch):
    media_id = MediaID.parse("tmdb:tv:1")
    subscriptions = [SimpleNamespace(media_id=media_id, season_number=1, active=True, followed=True)]
    empty_profile = _profile(media_id, airings=[])

    async def fake_list():
        return subscriptions

    monkeypatch.setattr("app.services.application.views.calendar.service.subscription_query_service.list_states", fake_list)
    monkeypatch.setattr("app.services.application.views.calendar.service.media_service.list_profiles_by_media_targets", AsyncMock(return_value={"tmdb:tv:1:1": empty_profile}))
    monkeypatch.setattr("app.services.application.views.calendar.service.media_service.refresh_schedule_snapshot", AsyncMock(side_effect=RuntimeError("tmdb down")))

    response = await list_airings(from_date="2026-01-01", to_date="2026-01-31", scope="all")

    assert response.count == 0
    assert response.data == []


@pytest.mark.asyncio
async def test_calendar_airings_does_not_refresh_tv_without_season(monkeypatch):
    media_id = MediaID.parse("tmdb:tv:1")
    subscriptions = [SimpleNamespace(media_id=media_id, season_number=None, active=True, followed=True)]
    empty_profile = _profile(media_id, airings=[])

    async def fake_list():
        return subscriptions

    monkeypatch.setattr("app.services.application.views.calendar.service.subscription_query_service.list_states", fake_list)
    monkeypatch.setattr("app.services.application.views.calendar.service.media_service.list_profiles_by_media_targets", AsyncMock(return_value={"tmdb:tv:1:1": empty_profile}))
    refresh_mock = AsyncMock()
    monkeypatch.setattr("app.services.application.views.calendar.service.media_service.refresh_schedule_snapshot", refresh_mock)

    response = await list_airings(from_date="2026-01-01", to_date="2026-01-31", scope="all")

    refresh_mock.assert_not_awaited()
    assert response.count == 0
    assert response.data == []
