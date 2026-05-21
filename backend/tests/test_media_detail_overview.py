from unittest.mock import AsyncMock
from datetime import date, timedelta

import pytest

import app.services.application.views.media_detail_overview.service as overview_module
from app.services.application.views.media_detail_overview.service import (
    _DetailOverviewSettingsSnapshot,
    MediaDetailOverviewService,
)
from app.schemas.domain.filter_config import FilterConfig
from app.schemas.domain.media_subscription_state import MediaSubscriptionState, SubscriptionMode
from app.schemas.domain.media_download_config import MediaDownloadConfig
from app.schemas.domain.media import MediaFullInfo, MediaSeasonInfo
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.quality_profile import QualityProfile
from app.schemas.domain.schedule import MediaScheduleSummary, ScheduleAiring, ScheduleEpisode
from app.schemas.domain.subscription_filters import SubscriptionFilters, UpgradePolicy
from app.schemas.media_id import MediaID


service = MediaDetailOverviewService()


def test_detail_overview_uses_selected_filter_profile_when_config_does_not_override():
    media_id = MediaID.parse("tmdb:tv:123")
    selected_filters = SubscriptionFilters()
    selected_profile = QualityProfile(id="qp-selected", name="Selected")
    default_profile = QualityProfile(id="qp-default", name="Default", active_default=True)
    snapshot = _DetailOverviewSettingsSnapshot(
        filters=[
            FilterConfig(
                id="filter-default",
                name="Default Filter",
                is_default=False,
                active_default=True,
                quality_profile_id="qp-default",
                filters=SubscriptionFilters(),
            ),
            FilterConfig(
                id="filter-selected",
                name="Selected Filter",
                is_default=False,
                quality_profile_id="qp-selected",
                filters=selected_filters,
            ),
        ],
        quality_profiles=[default_profile, selected_profile],
        directories=[],
        indexers_enabled=True,
        enabled_downloaders=set(),
        default_downloader_id=None,
        has_default_template=True,
        enabled_directories=[],
        default_directory=None,
        default_filter=FilterConfig(
            id="filter-default",
            name="Default Filter",
            is_default=False,
            active_default=True,
            quality_profile_id="qp-default",
            filters=SubscriptionFilters(),
        ),
    )
    config = MediaDownloadConfig(
        sub_id="sub-1",
        media_id=media_id,
        filter_config_id="filter-selected",
        quality_profile_id=None,
        filters=None,
    )

    effective = service._resolve_effective_config(media_id, config, snapshot)

    assert effective.filter_config_id == "filter-selected"
    assert effective.filters is selected_filters
    assert effective.quality_profile_id == "qp-selected"
    assert effective.quality_profile is selected_profile


@pytest.mark.asyncio
async def test_detail_overview_does_not_fetch_schedule_when_cache_has_no_schedule(monkeypatch):
    media = MediaFullInfo(
        media_id=MediaID.parse("tmdb:tv:273129"),
        title="Sample",
        year=2026,
        media_type=MediaType.tv,
        tmdb_id=273129,
        season_number=1,
    )
    fetch_schedule = AsyncMock()
    monkeypatch.setattr(overview_module.media_service, "build_schedule_summary_for_media", fetch_schedule)

    summary = await service._resolve_schedule_summary(media)

    assert summary.media_type == MediaType.tv
    assert summary.aired_episode_count == 0
    fetch_schedule.assert_not_awaited()


@pytest.mark.asyncio
async def test_detail_overview_resolves_schedule_for_selected_cached_season():
    media = MediaFullInfo(
        media_id=MediaID.parse("tmdb:tv:273129"),
        title="Sample",
        year=2026,
        media_type=MediaType.tv,
        tmdb_id=273129,
        season_number=1,
        episodes_count=2,
        seasons=[
            MediaSeasonInfo(season_number=1, episode_count=2, air_date="2000-01-01"),
            MediaSeasonInfo(season_number=2, episode_count=2, air_date="2999-01-01"),
        ],
        schedule=MediaScheduleSummary(
            media_type=MediaType.tv,
            latest_aired_episode=ScheduleEpisode(season_number=2, episode_number=1, air_date="2999-01-01"),
            next_episode_to_air=ScheduleEpisode(season_number=2, episode_number=2, air_date="2999-01-08"),
        ),
        airings=[
            ScheduleAiring(
                date="2000-01-01",
                kind="tv_episode_air",
                season_number=1,
                episode_number=1,
                episode_title="S1E1",
            ),
            ScheduleAiring(
                date="2000-01-08",
                kind="tv_episode_air",
                season_number=1,
                episode_number=2,
                episode_title="S1E2",
            ),
            ScheduleAiring(
                date="2999-01-01",
                kind="tv_episode_air",
                season_number=2,
                episode_number=1,
                episode_title="S2E1",
            ),
            ScheduleAiring(
                date="2999-01-08",
                kind="tv_episode_air",
                season_number=2,
                episode_number=2,
                episode_title="S2E2",
            ),
        ],
    )

    summary = await service._resolve_schedule_summary(media)

    assert summary.first_air_date == "2000-01-01"
    assert summary.aired_episode_count == 2
    assert summary.latest_aired_episode is not None
    assert summary.latest_aired_episode.season_number == 1
    assert summary.latest_aired_episode.episode_number == 2
    assert summary.next_episode_to_air is None
    assert summary.status_label == "Ended"

    season_two_summary = await service._resolve_schedule_summary(
        media.model_copy(update={
            "season_number": 2,
            "episodes_count": 2,
        })
    )

    assert season_two_summary.first_air_date == "2999-01-01"
    assert season_two_summary.aired_episode_count == 0
    assert season_two_summary.latest_aired_episode is None
    assert season_two_summary.next_episode_to_air is not None
    assert season_two_summary.next_episode_to_air.season_number == 2
    assert season_two_summary.next_episode_to_air.episode_number == 1
    assert season_two_summary.status_label == "Airing"


@pytest.mark.asyncio
async def test_detail_overview_counts_cached_airing_today_as_aired():
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    media = MediaFullInfo(
        media_id=MediaID.parse("tmdb:tv:272432"),
        title="Sample",
        year=2026,
        media_type=MediaType.tv,
        tmdb_id=272432,
        season_number=1,
        episodes_count=3,
        seasons=[MediaSeasonInfo(season_number=1, episode_count=3, air_date=yesterday)],
        airings=[
            ScheduleAiring(date=yesterday, kind="tv_episode_air", season_number=1, episode_number=1),
            ScheduleAiring(date=today, kind="tv_episode_air", season_number=1, episode_number=2),
            ScheduleAiring(date=tomorrow, kind="tv_episode_air", season_number=1, episode_number=3),
        ],
    )

    summary = await service._resolve_schedule_summary(media)

    assert summary.aired_episode_count == 2
    assert summary.latest_aired_episode is not None
    assert summary.latest_aired_episode.episode_number == 2
    assert summary.next_episode_to_air is not None
    assert summary.next_episode_to_air.episode_number == 3


def test_detail_overview_filter_summary_prefers_selected_preset_name_over_effective_filters():
    media_id = MediaID.parse("tmdb:tv:321")
    selected_filters = SubscriptionFilters(resolution=["1080p"])
    selected_preset = FilterConfig(
        id="filter-selected",
        name="Selected Filter",
        is_default=False,
        quality_profile_id=None,
        filters=selected_filters,
    )
    snapshot = _DetailOverviewSettingsSnapshot(
        filters=[selected_preset],
        quality_profiles=[],
        directories=[],
        indexers_enabled=True,
        enabled_downloaders=set(),
        default_downloader_id=None,
        has_default_template=True,
        enabled_directories=[],
        default_directory=None,
        default_filter=None,
    )
    config = MediaDownloadConfig(
        sub_id="sub-3",
        media_id=media_id,
        filter_config_id="filter-selected",
        quality_profile_id=None,
        filters=None,
    )

    effective = service._resolve_effective_config(media_id, config, snapshot)
    summary = service._resolve_filter_summary(effective, snapshot)

    assert summary.id == "filter-selected"
    assert summary.name == "Selected Filter"
    assert summary.is_default is False


def test_detail_overview_filter_summary_prefers_custom_filters_over_stale_preset_id():
    media_id = MediaID.parse("tmdb:tv:654")
    selected_preset = FilterConfig(
        id="filter-selected",
        name="Selected Filter",
        is_default=False,
        quality_profile_id=None,
        filters=SubscriptionFilters(resolution=["2160p"]),
    )
    snapshot = _DetailOverviewSettingsSnapshot(
        filters=[selected_preset],
        quality_profiles=[],
        directories=[],
        indexers_enabled=True,
        enabled_downloaders=set(),
        default_downloader_id=None,
        has_default_template=True,
        enabled_directories=[],
        default_directory=None,
        default_filter=None,
    )
    config = MediaDownloadConfig(
        sub_id="sub-4",
        media_id=media_id,
        filter_config_id="filter-selected",
        quality_profile_id=None,
        filters=SubscriptionFilters(resolution=["1080p"]),
    )

    effective = service._resolve_effective_config(media_id, config, snapshot)
    summary = service._resolve_filter_summary(effective, snapshot)

    assert summary.id is None
    assert summary.name_key == "mediaDetail.customValue"


def test_detail_overview_with_custom_filters_and_no_preset_uses_global_default_profile():
    media_id = MediaID.parse("tmdb:tv:456")
    custom_filters = SubscriptionFilters()
    global_default_profile = QualityProfile(id="qp-global-default", name="Global Default", active_default=True)
    snapshot = _DetailOverviewSettingsSnapshot(
        filters=[
            FilterConfig(
                id="filter-default",
                name="Default Filter",
                is_default=False,
                active_default=True,
                quality_profile_id="qp-from-default-filter",
                filters=SubscriptionFilters(),
            ),
        ],
        quality_profiles=[
            QualityProfile(id="qp-from-default-filter", name="From Default Filter"),
            global_default_profile,
        ],
        directories=[],
        indexers_enabled=True,
        enabled_downloaders=set(),
        default_downloader_id=None,
        has_default_template=True,
        enabled_directories=[],
        default_directory=None,
        default_filter=FilterConfig(
            id="filter-default",
            name="Default Filter",
            is_default=False,
            active_default=True,
            quality_profile_id="qp-from-default-filter",
            filters=SubscriptionFilters(),
        ),
    )
    config = MediaDownloadConfig(
        sub_id="sub-2",
        media_id=media_id,
        filter_config_id=None,
        quality_profile_id=None,
        filters=custom_filters,
    )

    effective = service._resolve_effective_config(media_id, config, snapshot)

    assert effective.filter_config_id is None
    assert effective.filters is custom_filters
    assert effective.quality_profile_id == "qp-global-default"
    assert effective.quality_profile is global_default_profile


def test_detail_overview_falls_back_to_first_quality_profile_when_none_marked_default():
    media_id = MediaID.parse("tmdb:tv:789")
    fallback_profile = QualityProfile(id="qp-first", name="First", active_default=False)
    snapshot = _DetailOverviewSettingsSnapshot(
        filters=[],
        quality_profiles=[fallback_profile],
        directories=[],
        indexers_enabled=True,
        enabled_downloaders=set(),
        default_downloader_id=None,
        has_default_template=True,
        enabled_directories=[],
        default_directory=None,
        default_filter=None,
    )

    effective = service._resolve_effective_config(media_id, None, snapshot)

    assert effective.quality_profile_id == "qp-first"
    assert effective.quality_profile is fallback_profile


def test_detail_overview_movie_subscription_mode_label_uses_first_release_by_default():
    state = MediaSubscriptionState(
        sub_id="sub-movie-0",
        media_id=MediaID.parse("tmdb:movie:1"),
        active=True,
        followed=False,
        upgrade_policy=None,
    )

    assert service._resolve_subscription_mode_label(state, MediaType.movie) == SubscriptionMode.FIRST_RELEASE


def test_detail_overview_movie_subscription_mode_label_is_upgrade_when_enabled():
    state = MediaSubscriptionState(
        sub_id="sub-movie-1",
        media_id=MediaID.parse("tmdb:movie:1"),
        active=True,
        followed=False,
        upgrade_policy=UpgradePolicy(
            enabled=True,
            strategy="consistent_skip_low",
            min_upgrade_score_delta=5,
            lock_mode="first_download",
        ),
    )

    assert service._resolve_subscription_mode_label(state, MediaType.movie) == SubscriptionMode.UPGRADE_CONTINUOUS
