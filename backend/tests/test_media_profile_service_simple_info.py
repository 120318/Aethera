import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.schemas.domain.media import EpisodeInfo, MediaFullInfo, MediaSeasonInfo, PersonInfo
from app.schemas.domain.media_context import MediaCapabilities
from app.schemas.domain.media_profile_scope import MediaProfileScope, MediaProfileScopeAiring
from app.schemas.domain.media_source import MediaSourceLookup, MediaSourceName
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.schedule import MediaScheduleSummary, ScheduleAiring, ScheduleEpisode, SchedulePlatform
from app.schemas.exception import MediaNotFoundException, SearchMissingSeasonInfoException
from app.schemas.media_id import MediaID
from app.schemas.persistence.media_external_mapping import MediaExternalMappingRecord
from app.services.domain.media.profile.builders import build_profile_from_media
from app.services.domain.media.profile.scope_projection import build_scopes_from_media
from app.services.domain.media.profile.service import MediaProfileService
from app.services.domain.media.schedule.service import MediaScheduleService


def _ready_profile(
    media_id: MediaID,
    *,
    douban_id: str | None = None,
    detail_updated_at: float | None = None,
    next_episode_to_air: ScheduleEpisode | None = None,
):
    profile = SimpleNamespace(
        media_id=media_id,
        detail_ready=True,
        year=2026,
        title="Sample",
        original_title=None,
        media_type=media_id.media_type,
        imdb_id="tt123",
        douban_id=douban_id,
        tmdb_id=int(media_id.id),
        primary_metadata_source="tmdb",
        metadata_capabilities=MediaCapabilities(has_schedule=media_id.media_type == MediaType.tv),
        tvdb_id=None,
        overview=None,
        genres=[],
        poster_path=None,
        backdrop_path=None,
        logo_path=None,
        actors=[],
        directors=[],
        studios=[],
        duration=None,
        vendors=[],
        rating_count=None,
        vote_average=None,
        vote_count=None,
        rating_source=None,
        douban_vote_average=None,
        douban_rating_count=None,
        tmdb_vote_average=None,
        tmdb_rating_count=None,
        release_date=None,
        first_air_date="2026-01-01" if media_id.media_type == MediaType.tv else None,
        episodes_count=12 if media_id.media_type == MediaType.tv else None,
        seasons_count=1 if media_id.media_type == MediaType.tv else None,
        seasons=[],
        status_label=None,
        aired_episode_count=0,
        latest_aired_episode=None,
        next_episode_to_air=next_episode_to_air,
        theatrical_release_date=None,
        digital_release_date=None,
        networks=[],
        online_platforms=[],
        airings=[],
        is_active=True,
        inactive_since=None,
        status=None,
        original_language=None,
        schedule_updated_at=None,
        created_at=detail_updated_at or time.time(),
        updated_at=detail_updated_at or time.time(),
        detail_updated_at=detail_updated_at,
    )
    profile.model_copy = lambda update: SimpleNamespace(**{**profile.__dict__, **update})
    return profile


def _scope(
    media_id: MediaID,
    season_number: int,
    *,
    episode_count: int | None = None,
    episode_count_override: int | None = None,
    douban_id: str | None = None,
    douban_vote_average: float | None = None,
    douban_rating_count: int | None = None,
    status_label: str | None = None,
    aired_episode_count: int = 0,
    latest_aired_episode: ScheduleEpisode | None = None,
    next_episode_to_air: ScheduleEpisode | None = None,
    airings: list | None = None,
) -> MediaProfileScope:
    return MediaProfileScope(
        media_id=media_id,
        season_number=season_number,
        media_type=media_id.media_type,
        episode_count=episode_count,
        episode_count_override=episode_count_override,
        douban_id=douban_id,
        douban_vote_average=douban_vote_average,
        douban_rating_count=douban_rating_count,
        status_label=status_label,
        aired_episode_count=aired_episode_count,
        latest_aired_episode=latest_aired_episode,
        next_episode_to_air=next_episode_to_air,
        airings=airings or [],
        updated_at=time.time(),
    )


def test_build_profile_from_media_persists_first_detail_schedule_snapshot():
    media_id = MediaID.parse("tmdb:tv:273129")
    media = MediaFullInfo(
        media_id=media_id,
        title="Sample",
        year=2026,
        media_type=MediaType.tv,
        tmdb_id=273129,
        season_number=1,
        episodes_count=15,
        aired_episode_count=10,
        latest_aired_episode=EpisodeInfo(season_number=1, episode_number=10, air_date="2026-05-01"),
        next_episode_to_air=EpisodeInfo(season_number=1, episode_number=11, air_date="2026-05-02"),
        schedule=MediaScheduleSummary(
            media_type=MediaType.tv,
            status_label="Returning Series",
            first_air_date="2026-04-28",
            aired_episode_count=10,
            latest_aired_episode=ScheduleEpisode(season_number=1, episode_number=10, air_date="2026-05-01"),
            next_episode_to_air=ScheduleEpisode(season_number=1, episode_number=11, air_date="2026-05-02"),
        ),
        primary_metadata_source="tmdb",
    )

    profile = build_profile_from_media(
        media,
        existing=None,
        is_active=False,
        episodes_count=15,
    )

    assert profile.aired_episode_count == 10
    assert profile.latest_aired_episode == ScheduleEpisode(season_number=1, episode_number=10, air_date="2026-05-01")
    assert profile.next_episode_to_air == ScheduleEpisode(season_number=1, episode_number=11, air_date="2026-05-02")
    assert profile.schedule_updated_at is not None


def test_profile_read_model_keeps_scope_douban_rating_source_without_score():
    service = MediaProfileService(provider_service=None, schedule_service=MediaScheduleService())
    media_id = MediaID.parse("tmdb:tv:233295")
    profile = _ready_profile(media_id)
    profile.tmdb_vote_average = 7.5
    profile.tmdb_rating_count = 100
    selected_scope = _scope(media_id, 1, douban_id="36053703")

    media = service.read_model.to_full(media_id, profile, selected_scope=selected_scope)

    assert media.douban_id == "36053703"
    assert media.rating_source == "douban"
    assert media.vote_average is None
    assert media.rating_count is None


def test_build_profile_from_media_stores_only_current_tv_season_airings():
    media_id = MediaID.parse("tmdb:tv:273129")
    existing = _ready_profile(media_id)
    existing.networks = []
    existing.airings = [
        ScheduleAiring(
            date="2026-07-01",
            kind="tv_episode_air",
            season_number=3,
            episode_number=1,
        )
    ]
    media = MediaFullInfo(
        media_id=media_id,
        title="Sample",
        year=2026,
        media_type=MediaType.tv,
        tmdb_id=273129,
        season_number=1,
        airings=[
            ScheduleAiring(
                date="2026-04-01",
                kind="tv_episode_air",
                season_number=1,
                episode_number=1,
            )
        ],
        primary_metadata_source="tmdb",
    )

    profile = build_profile_from_media(
        media,
        existing=existing,
        is_active=True,
        episodes_count=15,
    )

    assert {(item.season_number, item.episode_number) for item in profile.airings} == {(1, 1)}


def test_build_profile_from_media_preserves_existing_localized_detail():
    media_id = MediaID.parse("tmdb:movie:1546855")
    existing = _ready_profile(media_id, douban_id="37332784")
    existing.title = "我，许可"
    existing.original_title = "我，许可"
    existing.overview = "中文简介"
    existing.genres = ["剧情", "喜剧"]
    existing.actors = [PersonInfo(name="文淇", character="许可")]
    existing.directors = [PersonInfo(name="杨荔钠")]
    existing.studios = ["横店影业"]

    media = MediaFullInfo(
        media_id=media_id,
        title="It's OK",
        original_title="It's OK",
        year=2026,
        media_type=MediaType.movie,
        tmdb_id=1546855,
        douban_id="37332784",
        overview="English plot",
        genres=["Drama", "Comedy"],
        actors=[PersonInfo(name="Wen Qi", character="Xu Ke")],
        directors=[PersonInfo(name="Yang Lina")],
        studios=["Zhejiang Hengdian Film Production"],
        primary_metadata_source="tmdb",
    )

    profile = build_profile_from_media(
        media,
        existing=existing,
        is_active=True,
        episodes_count=None,
    )

    assert profile.title == "我，许可"
    assert profile.original_title == "我，许可"
    assert profile.overview == "中文简介"
    assert profile.genres == ["剧情", "喜剧"]
    assert [actor.name for actor in profile.actors] == ["文淇"]
    assert [director.name for director in profile.directors] == ["杨荔钠"]
    assert profile.studios == ["横店影业"]


@pytest.mark.asyncio
async def test_upsert_profile_reactivates_existing_inactive_managed_media(monkeypatch):
    service = MediaProfileService(provider_service=None, schedule_service=MediaScheduleService())
    media_id = MediaID.parse("tmdb:tv:273129")
    existing = _ready_profile(media_id)
    existing.is_active = False
    existing.inactive_since = 123
    media = MediaFullInfo(
        media_id=media_id,
        title="Sample",
        year=2026,
        media_type=MediaType.tv,
        tmdb_id=273129,
        season_number=1,
        episodes_count=12,
        seasons=[MediaSeasonInfo(season_number=1, episode_count=12)],
        primary_metadata_source="tmdb",
    )

    managed_check = AsyncMock(return_value=True)
    monkeypatch.setattr(service.lifecycle, "is_managed_media", managed_check)
    monkeypatch.setattr(service.profile_repo, "upsert_profile", AsyncMock(return_value=True))

    profile = await service._upsert_profile_from_media(media, existing=existing)

    managed_check.assert_awaited_once_with(media_id)
    assert profile.is_active is True
    assert profile.inactive_since is None


@pytest.mark.asyncio
async def test_is_managed_media_only_reads_active_profile(monkeypatch):
    service = MediaProfileService(provider_service=None, schedule_service=MediaScheduleService())
    media_id = MediaID.parse("tmdb:movie:1")
    profile = _ready_profile(media_id)
    profile.is_active = True

    monkeypatch.setattr(service.profile_repo, "find_by_media_id", AsyncMock(return_value=profile))
    monkeypatch.setattr(service.lifecycle.task_repo, "find_by_media_id", AsyncMock(side_effect=AssertionError("task lookup should not run")))
    monkeypatch.setattr(service.lifecycle.episode_repo, "find_by_media_id", AsyncMock(side_effect=AssertionError("episode lookup should not run")))
    monkeypatch.setattr(service.lifecycle.meta_repo, "find_by_media_id", AsyncMock(side_effect=AssertionError("meta lookup should not run")))

    assert await service.is_managed_media(media_id) is True


@pytest.mark.asyncio
async def test_mark_profile_inactive_checks_references_without_subscription_state(monkeypatch):
    service = MediaProfileService(provider_service=None, schedule_service=MediaScheduleService())
    media_id = MediaID.parse("tmdb:movie:1")
    profile = _ready_profile(media_id)

    monkeypatch.setattr(service.profile_repo, "find_by_media_id", AsyncMock(return_value=profile))
    monkeypatch.setattr(service.profile_repo, "upsert_profile", AsyncMock(return_value=True))
    monkeypatch.setattr(service.lifecycle.task_repo, "find_by_media_id", AsyncMock(return_value=None))
    monkeypatch.setattr(service.lifecycle.episode_repo, "find_by_media_id", AsyncMock(return_value=None))
    monkeypatch.setattr(service.lifecycle.meta_repo, "find_by_media_id", AsyncMock(return_value=None))

    assert await service.mark_profile_inactive_if_unmanaged(media_id) is True
    service.profile_repo.upsert_profile.assert_awaited_once()


@pytest.mark.asyncio
async def test_simple_info_does_not_refresh_placeholder_profile(monkeypatch):
    service = MediaProfileService(provider_service=None, schedule_service=MediaScheduleService())
    media_id = MediaID.parse("tmdb:tv:1")
    refresh = AsyncMock()

    monkeypatch.setattr(
        service.profile_repo,
        "find_by_media_id",
        AsyncMock(return_value=type("PlaceholderProfile", (), {"detail_ready": False})()),
    )
    monkeypatch.setattr(service, "info", refresh)

    simple = await service.simple_info(media_id)

    assert simple is None
    refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_detail_info_refreshes_cached_tv_profile_without_season_airings(monkeypatch):
    provider = SimpleNamespace()
    service = MediaProfileService(provider_service=provider, schedule_service=MediaScheduleService())
    media_id = MediaID.parse("tmdb:tv:283805")
    profile = _ready_profile(media_id)
    profile.seasons = [MediaSeasonInfo(season_number=1, episode_count=16, air_date="2026-04-01")]
    refreshed_media = MediaFullInfo(
        media_id=media_id,
        title="Sample",
        year=2026,
        media_type=MediaType.tv,
        tmdb_id=283805,
        season_number=1,
        seasons=profile.seasons,
        episodes_count=16,
        primary_metadata_source="tmdb",
        schedule=MediaScheduleSummary(media_type=MediaType.tv, first_air_date="2026-04-01"),
        airings=[
            ScheduleAiring(
                date="2026-04-01",
                kind="tv_episode_air",
                season_number=1,
                episode_number=1,
            )
        ],
    )
    provider.info = AsyncMock(return_value=refreshed_media)

    monkeypatch.setattr(service.profile_repo, "find_by_media_id", AsyncMock(return_value=profile))
    monkeypatch.setattr(service.profile_repo, "upsert_profile", AsyncMock(return_value=True))

    media, cache_mode = await service.info_with_cache_status(
        media_id,
        include_default_season_details=True,
    )

    assert cache_mode == "miss"
    assert media is not None
    provider.info.assert_awaited_once_with(
        media_id,
        season_number=None,
        include_default_season_details=True,
        default_season_year=None,
    )
    service.profile_repo.upsert_profile.assert_awaited_once()


def test_build_scopes_from_media_rejects_unscoped_tv_media():
    media_id = MediaID.parse("tmdb:tv:312823")
    media = MediaFullInfo(
        media_id=media_id,
        title="Sample",
        year=2026,
        media_type=MediaType.tv,
        tmdb_id=312823,
        seasons=[MediaSeasonInfo(season_number=1, episode_count=52)],
    )

    with pytest.raises(SearchMissingSeasonInfoException):
        build_scopes_from_media(media, [])


def test_build_scopes_from_media_uses_selected_tv_season_douban_id():
    media_id = MediaID.parse("tmdb:tv:312823")
    media = MediaFullInfo(
        media_id=media_id,
        title="Sample",
        year=2026,
        media_type=MediaType.tv,
        tmdb_id=312823,
        douban_id="wrong-work-id",
        season_number=3,
        seasons=[
            MediaSeasonInfo(season_number=1, episode_count=52, douban_id="30425739"),
            MediaSeasonInfo(season_number=3, episode_count=59, douban_id="36055705"),
        ],
    )

    scopes = build_scopes_from_media(media, [])

    assert len(scopes) == 1
    assert scopes[0].season_number == 3
    assert scopes[0].douban_id == "36055705"


def test_build_scopes_from_media_preserves_existing_tv_scope_douban_id():
    media_id = MediaID.parse("tmdb:tv:312823")
    media = MediaFullInfo(
        media_id=media_id,
        title="Sample",
        year=2026,
        media_type=MediaType.tv,
        tmdb_id=312823,
        douban_id=None,
        season_number=3,
        seasons=[MediaSeasonInfo(season_number=3, episode_count=59)],
    )

    scopes = build_scopes_from_media(media, [_scope(media_id, 3, douban_id="36055705")])

    assert len(scopes) == 1
    assert scopes[0].douban_id == "36055705"


def test_build_scopes_from_media_uses_movie_douban_id():
    media_id = MediaID.parse("tmdb:movie:100")
    media = MediaFullInfo(
        media_id=media_id,
        title="Sample",
        year=2026,
        media_type=MediaType.movie,
        tmdb_id=100,
        douban_id="35633767",
        douban_vote_average=8.8,
        douban_rating_count=1200,
    )

    scopes = build_scopes_from_media(media, [])

    assert len(scopes) == 1
    assert scopes[0].season_number == 0
    assert scopes[0].douban_id == "35633767"
    assert scopes[0].douban_vote_average == 8.8
    assert scopes[0].douban_rating_count == 1200


@pytest.mark.asyncio
async def test_detail_info_rejects_unscoped_tv_media_without_source_resolution(monkeypatch):
    media_id = MediaID.parse("tmdb:tv:312823")
    service = MediaProfileService(
        provider_service=SimpleNamespace(info=AsyncMock()),
        schedule_service=MediaScheduleService(),
    )

    monkeypatch.setattr(service.profile_repo, "find_by_media_id", AsyncMock())

    with pytest.raises(SearchMissingSeasonInfoException):
        await service.info_with_cache_status(media_id)

    service.profile_repo.find_by_media_id.assert_not_awaited()
    service.provider_service.info.assert_not_awaited()


@pytest.mark.asyncio
async def test_detail_info_applies_default_season_external_mapping_on_cache_miss(monkeypatch):
    media_id = MediaID.parse("tmdb:tv:312823")
    season = MediaSeasonInfo(season_number=1, episode_count=52)
    media = MediaFullInfo(
        media_id=media_id,
        title="Sample",
        year=2026,
        media_type=MediaType.tv,
        tmdb_id=312823,
        douban_id=None,
        season_number=1,
        seasons=[season],
        episodes_count=52,
        primary_metadata_source="tmdb",
        schedule=MediaScheduleSummary(media_type=MediaType.tv, first_air_date="2026-01-01"),
    )
    mapping = MediaExternalMappingRecord(
        source="douban",
        source_id="30425739",
        media_type="tv",
        media_id=media_id,
        tmdb_id=312823,
        douban_id="30425739",
        season_number=1,
    )
    service = MediaProfileService(
        provider_service=SimpleNamespace(info=AsyncMock(return_value=media)),
        schedule_service=MediaScheduleService(),
    )

    monkeypatch.setattr(service.profile_repo, "find_by_media_id", AsyncMock(return_value=None))
    monkeypatch.setattr(service.profile_repo, "upsert_profile", AsyncMock(return_value=True))
    monkeypatch.setattr(service.lifecycle, "is_managed_media", AsyncMock(return_value=True))
    monkeypatch.setattr(
        service.mapping_repo,
        "find_by_media_id_and_season",
        Mock(return_value=mapping),
    )

    result, cache_mode = await service.info_with_cache_status(
        media_id,
        include_default_season_details=True,
    )

    assert cache_mode == "miss"
    assert result is not None
    assert result.douban_id == "30425739"
    assert [item.douban_id for item in result.seasons] == ["30425739"]


@pytest.mark.asyncio
async def test_detail_info_applies_episode_count_override_on_cached_profile(monkeypatch):
    media_id = MediaID.parse("tmdb:tv:83463")
    profile = _ready_profile(media_id)
    profile.episodes_count = 184
    service = MediaProfileService(provider_service=None, schedule_service=MediaScheduleService())

    monkeypatch.setattr(service.profile_repo, "find_by_media_id", AsyncMock(return_value=profile))
    monkeypatch.setattr(
        service.scope_repo,
        "find_by_media_id",
        AsyncMock(return_value=[_scope(media_id, 7, episode_count=13, episode_count_override=12)]),
    )

    result, cache_mode = await service.info_with_cache_status(media_id, season_number=7)

    assert cache_mode == "hit"
    assert result is not None
    assert result.episodes_count == 12
    assert result.episode_count_override == 12
    assert result.seasons[0].episode_count == 12


@pytest.mark.asyncio
async def test_apply_source_mapping_snapshot_updates_existing_scope(monkeypatch):
    service = MediaProfileService(provider_service=None, schedule_service=MediaScheduleService())
    media_id = MediaID.parse("tmdb:tv:312823")
    profile = _ready_profile(media_id)
    existing_scope = _scope(media_id, 2, episode_count=54, douban_id="36055705")
    saved = []

    async def fake_upsert_scope(next_scope):
        saved.append(next_scope)

    monkeypatch.setattr(service.profile_repo, "find_by_media_id", AsyncMock(return_value=profile))
    monkeypatch.setattr(service.scope_repo, "find_by_media_id_and_season", AsyncMock(return_value=existing_scope))
    monkeypatch.setattr(service.scope_repo, "upsert_scope", fake_upsert_scope)

    await service.apply_source_mapping_snapshot(
        media_id,
        season_number=2,
        douban_id=None,
        episode_count_override=24,
    )

    assert saved
    assert saved[-1].douban_id == "36055705"
    assert saved[-1].episode_count_override == 24


@pytest.mark.asyncio
async def test_detail_info_ignores_unscoped_episode_count_override_on_cached_profile(monkeypatch):
    media_id = MediaID.parse("tmdb:tv:83463")
    profile = _ready_profile(media_id)
    profile.episodes_count = 184
    service = MediaProfileService(provider_service=None, schedule_service=MediaScheduleService())

    monkeypatch.setattr(service.profile_repo, "find_by_media_id", AsyncMock(return_value=profile))
    monkeypatch.setattr(
        service.scope_repo,
        "find_by_media_id",
        AsyncMock(return_value=[_scope(media_id, 1, episode_count=54), _scope(media_id, 7, episode_count=12)]),
    )

    result, cache_mode = await service.info_with_cache_status(media_id, season_number=7)

    assert cache_mode == "hit"
    assert result is not None
    assert result.episodes_count == 184
    assert result.episode_count_override is None
    assert [season.episode_count for season in result.seasons] == [54, 12]


@pytest.mark.asyncio
async def test_detail_info_clears_douban_rating_when_cached_season_has_no_douban_mapping(monkeypatch):
    service = MediaProfileService(provider_service=None, schedule_service=MediaScheduleService())
    media_id = MediaID.parse("tmdb:tv:83463")
    profile = _ready_profile(media_id, douban_id="36406476")
    profile.douban_vote_average = 8.8
    profile.douban_rating_count = 1200
    profile.tmdb_vote_average = 7.2
    profile.tmdb_rating_count = 300

    monkeypatch.setattr(service.profile_repo, "find_by_media_id", AsyncMock(return_value=profile))
    monkeypatch.setattr(service.mapping_repo, "find_by_media_id", Mock(return_value=None))
    monkeypatch.setattr(service.mapping_repo, "find_by_media_id_and_season", Mock(return_value=None))
    monkeypatch.setattr(
        service.scope_repo,
        "find_by_media_id",
        AsyncMock(return_value=[_scope(media_id, 7, episode_count=12)]),
    )

    result, cache_mode = await service.info_with_cache_status(media_id, season_number=7)

    assert cache_mode == "hit"
    assert result is not None
    assert result.douban_id is None
    assert result.vote_average == 7.2
    assert result.rating_count == 300
    assert result.vote_count == 300
    assert result.rating_source == "tmdb"


@pytest.mark.asyncio
async def test_info_from_douban_source_updates_canonical_external_mapping_without_refresh(monkeypatch):
    service = MediaProfileService(provider_service=None, schedule_service=MediaScheduleService())
    media_id = MediaID.parse("tmdb:tv:278894")
    mapping = MediaExternalMappingRecord(
        source="douban",
        source_id="36809858",
        media_type="tv",
        media_id=media_id,
        tmdb_id=278894,
        imdb_id="tt34903771",
        douban_id=None,
        season_number=1,
    )
    profile = _ready_profile(media_id)
    profile.imdb_id = "tt34903771"
    upsert = Mock()
    refresh_profile = AsyncMock(return_value=None)
    monkeypatch.setattr(service.mapping_repo, "find_by_douban_id", Mock(return_value=mapping))
    monkeypatch.setattr(service.mapping_repo, "upsert", upsert)
    monkeypatch.setattr(service.profile_repo, "find_by_media_id", AsyncMock(return_value=profile))
    monkeypatch.setattr(service.scope_repo, "find_by_media_id", AsyncMock(return_value=[_scope(media_id, 1, episode_count=24)]))
    monkeypatch.setattr(service, "refresh_profile", refresh_profile)

    media = await service.info_from_source(
        MediaSourceLookup(source=MediaSourceName.douban, source_id="36809858", media_type=MediaType.tv)
    )

    assert media is not None
    assert media.douban_id == "36809858"
    refresh_profile.assert_not_awaited()
    upsert.assert_called_once_with(
        media_id=media_id,
        tmdb_id=278894,
        imdb_id="tt34903771",
        douban_id="36809858",
        season_number=1,
        episode_count_override=None,
    )


@pytest.mark.asyncio
async def test_info_from_source_provider_miss_returns_scoped_profile(monkeypatch):
    provider_service = SimpleNamespace(info_from_source=AsyncMock())
    service = MediaProfileService(provider_service=provider_service, schedule_service=MediaScheduleService())
    media_id = MediaID.parse("tmdb:tv:278894")
    provider_media = MediaFullInfo(
        media_id=media_id,
        title="Sample",
        year=2026,
        media_type=MediaType.tv,
        tmdb_id=278894,
        douban_id="36809858",
        season_number=2,
        episodes_count=10,
        seasons=[MediaSeasonInfo(season_number=2, episode_count=10)],
        schedule=MediaScheduleSummary(
            media_type=MediaType.tv,
            aired_episode_count=4,
            latest_aired_episode=ScheduleEpisode(season_number=2, episode_number=4, air_date="2026-05-01"),
        ),
        airings=[
            ScheduleAiring(
                date="2026-05-01",
                kind="tv_episode_air",
                season_number=2,
                episode_number=4,
            )
        ],
    )
    saved_scopes = []

    async def fake_upsert_scopes(scopes):
        saved_scopes[:] = scopes
        return True

    async def fake_find_scopes(_media_id):
        return list(saved_scopes)

    provider_service.info_from_source.return_value = provider_media
    saved_mapping = {}

    def fake_upsert_mapping(**kwargs):
        saved_mapping.update(kwargs)

    def fake_find_mapping(_media_id, season_number):
        if not saved_mapping or int(saved_mapping["season_number"]) != int(season_number):
            return None
        return MediaExternalMappingRecord(
            source="douban",
            source_id=saved_mapping["douban_id"],
            media_type="tv",
            media_id=saved_mapping["media_id"],
            tmdb_id=saved_mapping["tmdb_id"],
            imdb_id=saved_mapping["imdb_id"],
            douban_id=saved_mapping["douban_id"],
            season_number=saved_mapping["season_number"],
            episode_count_override=saved_mapping["episode_count_override"],
        )

    monkeypatch.setattr(service.mapping_repo, "find_by_douban_id", Mock(return_value=None))
    monkeypatch.setattr(service.mapping_repo, "find_by_media_id_and_season", fake_find_mapping)
    monkeypatch.setattr(service.mapping_repo, "upsert", fake_upsert_mapping)
    monkeypatch.setattr(service.profile_repo, "find_by_media_id", AsyncMock(return_value=None))
    monkeypatch.setattr(service.profile_repo, "upsert_profile", AsyncMock(return_value=True))
    monkeypatch.setattr(service.scope_repo, "find_by_media_id", fake_find_scopes)
    monkeypatch.setattr(service.scope_repo, "upsert_scopes", fake_upsert_scopes)

    media = await service.info_from_source(
        MediaSourceLookup(source=MediaSourceName.douban, source_id="36809858", media_type=MediaType.tv)
    )

    assert media is not None
    assert media.seasons[0].douban_id == "36809858"
    assert media.seasons[0].episode_count == 10
    assert media.aired_episode_count == 4
    assert media.latest_aired_episode == EpisodeInfo(season_number=2, episode_number=4, air_date="2026-05-01")
    assert [(item.season_number, item.episode_number) for item in media.airings] == [(2, 4)]


@pytest.mark.asyncio
async def test_profile_to_simple_does_not_expose_stale_profile_schedule_count():
    service = MediaProfileService(provider_service=None, schedule_service=MediaScheduleService())
    media_id = MediaID.parse("tmdb:tv:1")
    profile = SimpleNamespace(
        year=2024,
        title="Sample",
        media_type=MediaType.tv,
        imdb_id="tt123",
        douban_id="1",
        tmdb_id=1,
        primary_metadata_source="tmdb",
        metadata_capabilities=MediaCapabilities(),
        seasons_count=1,
        episodes_count=12,
        aired_episode_count=4,
        seasons=[],
        next_episode_to_air=None,
        latest_aired_episode=None,
    )

    simple = service.profile_to_simple(media_id, profile)

    assert simple.aired_episode_count == 0


@pytest.mark.asyncio
async def test_info_from_douban_source_uses_fresh_profile_without_refresh(monkeypatch):
    provider_service = SimpleNamespace(info_from_source=AsyncMock(), info=AsyncMock())
    service = MediaProfileService(provider_service=provider_service, schedule_service=MediaScheduleService())
    media_id = MediaID.parse("tmdb:tv:278894")
    mapping = SimpleNamespace(
        media_id=media_id,
        tmdb_id=278894,
        imdb_id="tt123",
        douban_id="36809858",
        season_number=1,
        episode_count_override=6,
    )
    profile = _ready_profile(media_id, douban_id="36809858", detail_updated_at=time.time())
    refresh_profile = AsyncMock(return_value=None)
    upsert = Mock()

    monkeypatch.setattr(service.mapping_repo, "find_by_douban_id", Mock(return_value=mapping))
    monkeypatch.setattr(service.mapping_repo, "upsert", upsert)
    monkeypatch.setattr(service.profile_repo, "find_by_media_id", AsyncMock(return_value=profile))
    monkeypatch.setattr(service.scope_repo, "find_by_media_id", AsyncMock(return_value=[_scope(media_id, 1, episode_count=8)]))
    monkeypatch.setattr(service, "refresh_profile", refresh_profile)

    media = await service.info_from_source(
        MediaSourceLookup(source=MediaSourceName.douban, source_id="36809858", media_type=MediaType.tv)
    )

    assert media is not None
    assert media.douban_id == "36809858"
    assert media.season_number == 1
    assert media.episodes_count == 6
    assert media.episode_count_override == 6
    assert media.seasons[0].episode_count_override == 6
    refresh_profile.assert_not_awaited()
    provider_service.info_from_source.assert_not_awaited()


@pytest.mark.asyncio
async def test_info_from_douban_source_uses_stale_profile_without_refresh(monkeypatch):
    service = MediaProfileService(provider_service=None, schedule_service=MediaScheduleService())
    media_id = MediaID.parse("tmdb:movie:100")
    mapping = SimpleNamespace(
        media_id=media_id,
        tmdb_id=100,
        imdb_id="tt100",
        douban_id="35633767",
        season_number=None,
        episode_count_override=None,
    )
    stale_profile = _ready_profile(media_id, douban_id="35633767", detail_updated_at=time.time() - 31 * 86400)
    refreshed_profile = _ready_profile(media_id, douban_id="35633767", detail_updated_at=time.time())
    refresh_profile = AsyncMock(return_value=refreshed_profile)

    monkeypatch.setattr(service.mapping_repo, "find_by_douban_id", Mock(return_value=mapping))
    monkeypatch.setattr(service.mapping_repo, "upsert", Mock())
    monkeypatch.setattr(service.profile_repo, "find_by_media_id", AsyncMock(return_value=stale_profile))
    monkeypatch.setattr(service.scope_repo, "find_by_media_id", AsyncMock(return_value=[_scope(media_id, 0, douban_id="35633767")]))
    monkeypatch.setattr(service, "refresh_profile", refresh_profile)

    media = await service.info_from_source(
        MediaSourceLookup(source=MediaSourceName.douban, source_id="35633767", media_type=MediaType.movie)
    )

    assert media is not None
    refresh_profile.assert_not_awaited()


@pytest.mark.asyncio
async def test_info_uses_fresh_profile_without_provider_refresh(monkeypatch):
    provider_service = SimpleNamespace(info=AsyncMock(), info_from_source=AsyncMock())
    service = MediaProfileService(provider_service=provider_service, schedule_service=MediaScheduleService())
    media_id = MediaID.parse("tmdb:movie:100")
    profile = _ready_profile(media_id, douban_id="35633767", detail_updated_at=time.time())
    refresh_profile = AsyncMock(return_value=None)

    monkeypatch.setattr(service.profile_repo, "find_by_media_id", AsyncMock(return_value=profile))
    monkeypatch.setattr(service.scope_repo, "find_by_media_id", AsyncMock(return_value=[_scope(media_id, 0, douban_id="35633767")]))
    monkeypatch.setattr(service, "refresh_profile", refresh_profile)

    media = await service.info(media_id)

    assert media is not None
    assert media.douban_id == "35633767"
    refresh_profile.assert_not_awaited()
    provider_service.info.assert_not_awaited()


@pytest.mark.asyncio
async def test_info_uses_stale_profile_without_provider_refresh(monkeypatch):
    media_id = MediaID.parse("tmdb:movie:100")
    stale_profile = _ready_profile(media_id, douban_id="35633767", detail_updated_at=time.time() - 31 * 86400)
    refreshed_media = MediaFullInfo(
        media_id=media_id,
        title="Sample",
        year=2026,
        media_type=MediaType.movie,
        tmdb_id=100,
        douban_id="35633767",
        primary_metadata_source="tmdb",
    )
    provider_service = SimpleNamespace(info=AsyncMock(), info_from_source=AsyncMock(return_value=refreshed_media))
    schedule_service = SimpleNamespace(build_schedule_bundle=AsyncMock(return_value=(MediaScheduleSummary(media_type=MediaType.movie), [])))
    service = MediaProfileService(provider_service=provider_service, schedule_service=schedule_service)

    monkeypatch.setattr(service, "is_managed_media", AsyncMock(return_value=False))
    monkeypatch.setattr(service.profile_repo, "find_by_media_id", AsyncMock(return_value=stale_profile))
    monkeypatch.setattr(service.scope_repo, "find_by_media_id", AsyncMock(return_value=[_scope(media_id, 0, douban_id="35633767")]))
    monkeypatch.setattr(service.profile_repo, "upsert_profile", AsyncMock(return_value=True))

    media = await service.info(media_id)

    assert media is not None
    assert media.douban_id == "35633767"
    provider_service.info_from_source.assert_not_awaited()
    provider_service.info.assert_not_awaited()


@pytest.mark.asyncio
async def test_refresh_profile_falls_back_to_tmdb_when_douban_refresh_fails(monkeypatch):
    media_id = MediaID.parse("tmdb:movie:100")
    existing = _ready_profile(media_id, douban_id="35633767", detail_updated_at=time.time() - 31 * 86400)
    fallback_media = MediaFullInfo(
        media_id=media_id,
        title="Sample",
        year=2026,
        media_type=MediaType.movie,
        tmdb_id=100,
        douban_id="35633767",
        primary_metadata_source="tmdb",
    )
    provider_service = SimpleNamespace(
        info=AsyncMock(return_value=fallback_media),
        info_from_source=AsyncMock(side_effect=MediaNotFoundException()),
    )
    schedule_service = SimpleNamespace(build_schedule_bundle=AsyncMock(return_value=(MediaScheduleSummary(media_type=MediaType.movie), [])))
    service = MediaProfileService(provider_service=provider_service, schedule_service=schedule_service)
    scope = _scope(media_id, 0, douban_id="35633767")
    saved_scopes = []

    monkeypatch.setattr(service, "is_managed_media", AsyncMock(return_value=False))
    monkeypatch.setattr(service.scope_repo, "find_by_media_id", AsyncMock(return_value=[scope]))
    monkeypatch.setattr(service.scope_repo, "find_by_media_id_and_season", AsyncMock(return_value=scope))
    monkeypatch.setattr(service.scope_repo, "upsert_scope", AsyncMock(side_effect=lambda next_scope: saved_scopes.append(next_scope) or True))
    monkeypatch.setattr(service.profile_repo, "upsert_profile", AsyncMock(return_value=True))

    profile = await service.refresh_profile(media_id, existing=existing)

    assert profile is not None
    assert saved_scopes[-1].douban_id == "35633767"
    provider_service.info_from_source.assert_awaited_once_with(
        MediaSourceLookup(source=MediaSourceName.douban, source_id="35633767", media_type=MediaType.movie)
    )
    provider_service.info.assert_awaited_once_with(media_id)


def test_profile_to_full_exposes_cached_movie_schedule_fields():
    service = MediaProfileService(provider_service=None, schedule_service=MediaScheduleService())
    media_id = MediaID.parse("tmdb:movie:1")
    airings = [ScheduleAiring(date="2026-01-10", kind="movie_digital_release")]
    profile = SimpleNamespace(
        year=2026,
        title="Sample",
        original_title=None,
        media_type=MediaType.movie,
        imdb_id="tt123",
        douban_id=None,
        tmdb_id=1,
        primary_metadata_source="tmdb",
        metadata_capabilities=MediaCapabilities(has_movie_release_window=True, has_watch_providers=True),
        tvdb_id=None,
        overview=None,
        genres=[],
        poster_path=None,
        backdrop_path=None,
        logo_path=None,
        actors=[],
        directors=[],
        studios=[],
        duration=None,
        vendors=[],
        rating_count=None,
        vote_average=None,
        vote_count=None,
        rating_source=None,
        douban_vote_average=None,
        douban_rating_count=None,
        tmdb_vote_average=None,
        tmdb_rating_count=None,
        release_date="2026-01-01",
        first_air_date=None,
        episodes_count=None,
        seasons_count=None,
        seasons=[],
        status_label=None,
        aired_episode_count=0,
        latest_aired_episode=None,
        next_episode_to_air=None,
        theatrical_release_date="2026-01-01",
        digital_release_date="2026-01-10",
        networks=[],
        online_platforms=[],
        airings=airings,
        status=None,
        original_language=None,
    )

    media = service.profile_to_full(media_id, profile)

    assert media.theatrical_release_date == "2026-01-01"
    assert media.digital_release_date == "2026-01-10"
    assert media.airings == airings


def test_profile_to_full_converts_cached_schedule_episodes_to_episode_info():
    service = MediaProfileService(provider_service=None, schedule_service=MediaScheduleService())
    media_id = MediaID.parse("tmdb:tv:1")
    profile = SimpleNamespace(
        year=2026,
        title="Sample",
        original_title=None,
        media_type=MediaType.tv,
        imdb_id=None,
        douban_id="1",
        tmdb_id=1,
        primary_metadata_source="tmdb",
        metadata_capabilities=MediaCapabilities(has_schedule=True),
        tvdb_id=None,
        overview=None,
        genres=[],
        poster_path=None,
        backdrop_path=None,
        logo_path=None,
        actors=[],
        directors=[],
        studios=[],
        duration=None,
        vendors=[],
        rating_count=None,
        vote_average=None,
        vote_count=None,
        rating_source=None,
        douban_vote_average=None,
        douban_rating_count=None,
        tmdb_vote_average=None,
        tmdb_rating_count=None,
        release_date=None,
        first_air_date="2026-01-01",
        episodes_count=12,
        seasons_count=1,
        seasons=[],
        status_label="Sample",
        aired_episode_count=4,
        latest_aired_episode=ScheduleEpisode(season_number=1, episode_number=4, air_date="2026-01-22", title="text 4 text"),
        next_episode_to_air=ScheduleEpisode(season_number=1, episode_number=5, air_date="2026-01-29", title="text 5 text"),
        theatrical_release_date=None,
        digital_release_date=None,
        networks=[],
        online_platforms=[],
        airings=[],
        status=None,
        original_language=None,
    )

    media = service.profile_to_full(media_id, profile)

    assert media.latest_aired_episode is not None
    assert media.latest_aired_episode.episode_number == 4
    assert media.next_episode_to_air is not None
    assert media.next_episode_to_air.episode_number == 5


@pytest.mark.asyncio
async def test_profile_upsert_does_not_build_or_store_season_schedule(monkeypatch):
    schedule_service = SimpleNamespace(build_schedule_bundle=AsyncMock())
    service = MediaProfileService(provider_service=None, schedule_service=schedule_service)
    media_id = MediaID.parse("tmdb:tv:1")
    media = MediaFullInfo(
        media_id=media_id,
        title="Sample",
        year=2024,
        media_type=MediaType.tv,
        tmdb_id=1,
        season_number=1,
        episodes_count=8,
        seasons=[],
        aired_episode_count=4,
        primary_metadata_source="tmdb",
    )
    saved = {}

    async def fake_upsert_profile(profile):
        saved["profile"] = profile
        return True

    monkeypatch.setattr(service, "is_managed_media", AsyncMock(return_value=False))
    monkeypatch.setattr(service.profile_repo, "upsert_profile", fake_upsert_profile)

    profile = await service._upsert_profile_from_media(media)

    schedule_service.build_schedule_bundle.assert_not_awaited()
    assert profile.aired_episode_count == 0
    assert profile.latest_aired_episode is None
    assert profile.next_episode_to_air is None
    assert profile.airings == []
    assert saved["profile"] == profile


@pytest.mark.asyncio
async def test_refresh_profile_stores_schedule_snapshot(monkeypatch):
    media_id = MediaID.parse("tmdb:tv:1")
    media = MediaFullInfo(
        media_id=media_id,
        title="Sample",
        year=2024,
        media_type=MediaType.tv,
        tmdb_id=1,
        episodes_count=8,
        primary_metadata_source="tmdb",
    )
    summary = MediaScheduleSummary(
        media_type=MediaType.tv,
        status_label="Sample",
        aired_episode_count=1,
        next_episode_to_air=ScheduleEpisode(season_number=1, episode_number=2, air_date="2026-01-02"),
    )
    airings = [
        ScheduleAiring(date="2026-01-01", kind="tv_episode_air", season_number=1, episode_number=1),
    ]
    schedule_service = SimpleNamespace(build_schedule_bundle=AsyncMock(return_value=(summary, airings)))
    provider_service = SimpleNamespace(info=AsyncMock(return_value=media))
    service = MediaProfileService(provider_service=provider_service, schedule_service=schedule_service)
    saved = []

    async def fake_upsert_profile(profile):
        saved.append(profile)
        return True

    monkeypatch.setattr(service, "is_managed_media", AsyncMock(return_value=True))
    monkeypatch.setattr(service.profile_repo, "find_by_media_id", AsyncMock(return_value=None))
    monkeypatch.setattr(service.profile_repo, "upsert_profile", fake_upsert_profile)

    profile = await service.refresh_profile(media_id, season_number=1)

    assert profile is not None
    assert profile.status_label == "Sample"
    assert profile.aired_episode_count == 1
    assert profile.next_episode_to_air == summary.next_episode_to_air
    assert profile.airings == airings
    assert profile.schedule_updated_at is not None
    assert saved[-1].schedule_updated_at == profile.schedule_updated_at


@pytest.mark.asyncio
async def test_info_uses_season_scoped_douban_mapping(monkeypatch):
    media_id = MediaID.parse("tmdb:tv:312823")
    profile = _ready_profile(media_id, douban_id="30425739")
    service = MediaProfileService(
        provider_service=SimpleNamespace(info=AsyncMock(return_value=None)),
        schedule_service=MediaScheduleService(),
    )

    mappings = {
        1: MediaExternalMappingRecord(
            source="douban",
            source_id="30425739",
            media_type="tv",
            media_id=media_id,
            tmdb_id=312823,
            douban_id="30425739",
            season_number=1,
        ),
        3: MediaExternalMappingRecord(
            source="douban",
            source_id="36055705",
            media_type="tv",
            media_id=media_id,
            tmdb_id=312823,
            douban_id="36055705",
            season_number=3,
        ),
    }

    monkeypatch.setattr(service.profile_repo, "find_by_media_id", AsyncMock(return_value=profile))
    monkeypatch.setattr(
        service.mapping_repo,
        "find_by_media_id_and_season",
        lambda _media_id, season_number=None: mappings.get(season_number),
    )
    monkeypatch.setattr(
        service.scope_repo,
        "find_by_media_id",
        AsyncMock(return_value=[
            _scope(media_id, 1, episode_count=52, douban_id="30425739"),
            _scope(media_id, 2, episode_count=54),
            _scope(media_id, 3, episode_count=59),
        ]),
    )

    season_three = await service.info(media_id, season_number=3)
    season_two = await service.info(media_id, season_number=2)

    assert season_three is not None
    assert season_three.douban_id == "36055705"
    assert [season.douban_id for season in season_three.seasons] == ["30425739", None, "36055705"]
    assert season_two is not None
    assert season_two.douban_id is None


@pytest.mark.asyncio
async def test_refresh_profile_without_season_returns_none(monkeypatch):
    media_id = MediaID.parse("tmdb:tv:272476")
    media = MediaFullInfo(
        media_id=media_id,
        title="Sample",
        year=2026,
        media_type=MediaType.tv,
        tmdb_id=272476,
        episodes_count=28,
        seasons=[
            MediaSeasonInfo(season_number=1, episode_count=22),
            MediaSeasonInfo(season_number=2, episode_count=6),
        ],
        primary_metadata_source="tmdb",
    )
    schedule_calls = []

    async def fake_build_schedule_bundle(requested_media, **kwargs):
        schedule_calls.append(requested_media.season_number)
        if requested_media.season_number == 1:
            summary = MediaScheduleSummary(
                media_type=MediaType.tv,
                status_label="Sample",
                first_air_date="2026-04-14",
                aired_episode_count=22,
                latest_aired_episode=ScheduleEpisode(season_number=1, episode_number=22, air_date="2026-05-05"),
            )
        else:
            summary = MediaScheduleSummary(
                media_type=MediaType.tv,
                status_label="Sample",
                first_air_date="2026-06-01",
                aired_episode_count=1,
                latest_aired_episode=ScheduleEpisode(season_number=2, episode_number=1, air_date="2026-06-01"),
                next_episode_to_air=ScheduleEpisode(season_number=2, episode_number=2, air_date="2026-06-08"),
            )
        return (
            summary,
            [
                ScheduleAiring(
                    date=summary.first_air_date or "2026-04-14",
                    kind="tv_episode_air",
                    season_number=requested_media.season_number,
                    episode_number=1,
                )
            ] if requested_media.season_number else [],
        )

    schedule_service = SimpleNamespace(build_schedule_bundle=fake_build_schedule_bundle)
    provider_service = SimpleNamespace(info=AsyncMock(return_value=media))
    service = MediaProfileService(provider_service=provider_service, schedule_service=schedule_service)

    monkeypatch.setattr(service, "is_managed_media", AsyncMock(return_value=True))
    monkeypatch.setattr(service.profile_repo, "find_by_media_id", AsyncMock(return_value=None))
    monkeypatch.setattr(service.profile_repo, "upsert_profile", AsyncMock(return_value=True))

    profile = await service.refresh_profile(media_id)

    assert schedule_calls == []
    assert profile is None
    provider_service.info.assert_not_awaited()


@pytest.mark.asyncio
async def test_refresh_profile_keeps_single_season_status_summary(monkeypatch):
    media_id = MediaID.parse("tmdb:tv:272476")
    media = MediaFullInfo(
        media_id=media_id,
        title="Sample",
        year=2026,
        media_type=MediaType.tv,
        tmdb_id=272476,
        episodes_count=22,
        seasons=[MediaSeasonInfo(season_number=1, episode_count=22)],
        primary_metadata_source="tmdb",
    )
    schedule_calls = []

    async def fake_build_schedule_bundle(requested_media, **kwargs):
        schedule_calls.append(requested_media.season_number)
        return (
            MediaScheduleSummary(
                media_type=MediaType.tv,
                status_label="Ended",
                first_air_date="2026-04-14",
                aired_episode_count=22,
                latest_aired_episode=ScheduleEpisode(season_number=1, episode_number=22, air_date="2026-05-02"),
            ),
            [ScheduleAiring(date="2026-05-02", kind="tv_episode_air", season_number=1, episode_number=22)],
        )

    provider_service = SimpleNamespace(info=AsyncMock(return_value=media))
    service = MediaProfileService(
        provider_service=provider_service,
        schedule_service=SimpleNamespace(build_schedule_bundle=fake_build_schedule_bundle),
    )

    monkeypatch.setattr(service, "is_managed_media", AsyncMock(return_value=True))
    monkeypatch.setattr(service.profile_repo, "find_by_media_id", AsyncMock(return_value=None))
    monkeypatch.setattr(service.profile_repo, "upsert_profile", AsyncMock(return_value=True))

    profile = await service.refresh_profile(media_id, season_number=1)

    assert schedule_calls == [1]
    assert profile is not None
    assert profile.status_label == "Ended"
    assert profile.aired_episode_count == 22
    assert profile.latest_aired_episode == ScheduleEpisode(season_number=1, episode_number=22, air_date="2026-05-02")


@pytest.mark.asyncio
async def test_refresh_profile_with_season_refreshes_only_target_season_schedule(monkeypatch):
    media_id = MediaID.parse("tmdb:tv:272476")
    existing = _ready_profile(media_id)
    existing.seasons = [
        MediaSeasonInfo(season_number=1, episode_count=22),
        MediaSeasonInfo(season_number=2, episode_count=6),
    ]
    existing.networks = [SchedulePlatform(id="network-1", name="Network One")]
    old_season_one = ScheduleAiring(date="2026-04-14", kind="tv_episode_air", season_number=1, episode_number=1)
    old_season_two = ScheduleAiring(date="2026-06-01", kind="tv_episode_air", season_number=2, episode_number=1)
    existing.airings = [old_season_one, old_season_two]
    media = MediaFullInfo(
        media_id=media_id,
        title="Sample",
        year=2026,
        media_type=MediaType.tv,
        tmdb_id=272476,
        episodes_count=28,
        seasons=existing.seasons,
        season_number=2,
        primary_metadata_source="tmdb",
    )
    schedule_calls = []
    schedule_kwargs = []
    new_season_two = ScheduleAiring(date="2026-06-08", kind="tv_episode_air", season_number=2, episode_number=2)

    async def fake_build_schedule_bundle(requested_media, **kwargs):
        schedule_calls.append(requested_media.season_number)
        schedule_kwargs.append(kwargs)
        return (
            MediaScheduleSummary(
                media_type=MediaType.tv,
                status_label="Sample",
                latest_aired_episode=ScheduleEpisode(season_number=2, episode_number=1, air_date="2026-06-01"),
                next_episode_to_air=ScheduleEpisode(season_number=2, episode_number=2, air_date="2026-06-08"),
            ),
            [new_season_two],
        )

    provider_service = SimpleNamespace(info=AsyncMock(return_value=media))
    service = MediaProfileService(
        provider_service=provider_service,
        schedule_service=SimpleNamespace(build_schedule_bundle=fake_build_schedule_bundle),
    )

    monkeypatch.setattr(service, "is_managed_media", AsyncMock(return_value=True))
    monkeypatch.setattr(service.profile_repo, "find_by_media_id", AsyncMock(return_value=existing))
    monkeypatch.setattr(service.profile_repo, "upsert_profile", AsyncMock(return_value=True))

    profile = await service.refresh_profile(media_id, existing=existing, season_number=2)

    provider_service.info.assert_awaited_once_with(media_id, season_number=2)
    assert schedule_calls == [2]
    assert schedule_kwargs == [{"network_platforms": [SchedulePlatform(id="network-1", name="Network One")]}]
    assert profile is not None
    assert profile.airings == [new_season_two]
    assert profile.next_episode_to_air == ScheduleEpisode(season_number=2, episode_number=2, air_date="2026-06-08")


@pytest.mark.asyncio
async def test_refresh_active_profiles_refreshes_active_tv_seasons(monkeypatch):
    media_id = MediaID.parse("tmdb:tv:272476")
    active_profile = _ready_profile(media_id)
    active_profile.seasons = [MediaSeasonInfo(season_number=2, episode_count=6)]
    season_profile = _ready_profile(media_id)
    service = MediaProfileService(provider_service=None, schedule_service=MediaScheduleService())
    refresh_profile = AsyncMock(return_value=season_profile)

    monkeypatch.setattr(service.lifecycle, "build_active_media_map", AsyncMock(return_value={media_id: None}))
    monkeypatch.setattr(service.profile_repo, "find_active", AsyncMock(return_value=[active_profile]))
    monkeypatch.setattr(service.scope_repo, "find_by_media_id", AsyncMock(return_value=[_scope(media_id, 2, episode_count=6)]))
    monkeypatch.setattr(service, "refresh_profile", refresh_profile)
    monkeypatch.setattr(service, "mark_inactive_profiles", AsyncMock(return_value=0))

    refreshed = await service.refresh_active_profiles()

    assert refreshed == 1
    assert refresh_profile.await_args_list[0].args == (media_id,)
    assert refresh_profile.await_args_list[0].kwargs["season_number"] == 2
    service.mark_inactive_profiles.assert_awaited_once_with([media_id])


@pytest.mark.asyncio
async def test_refresh_active_profiles_refreshes_due_hot_tv_schedule_only(monkeypatch):
    media_id = MediaID.parse("tmdb:tv:272476")
    now = time.time()
    active_profile = _ready_profile(
        media_id,
        detail_updated_at=now,
        next_episode_to_air=ScheduleEpisode(season_number=1, episode_number=2, air_date="2026-05-09"),
    )
    active_profile.schedule_updated_at = now - 3700
    refreshed_profile = _ready_profile(media_id, detail_updated_at=now)
    service = MediaProfileService(provider_service=None, schedule_service=MediaScheduleService())
    refresh_profile = AsyncMock(return_value=refreshed_profile)
    refresh_schedule = AsyncMock(return_value=refreshed_profile)

    monkeypatch.setattr(service.lifecycle, "build_active_media_map", AsyncMock(return_value={media_id: None}))
    monkeypatch.setattr(service.profile_repo, "find_active", AsyncMock(return_value=[active_profile]))
    monkeypatch.setattr(
        service.scope_repo,
        "find_by_media_id",
        AsyncMock(return_value=[
            _scope(
                media_id,
                1,
                next_episode_to_air=ScheduleEpisode(season_number=1, episode_number=2, air_date="2026-05-09"),
            )
        ]),
    )
    monkeypatch.setattr(service, "refresh_profile", refresh_profile)
    monkeypatch.setattr(service, "refresh_schedule_snapshot", refresh_schedule)
    monkeypatch.setattr(service, "mark_inactive_profiles", AsyncMock(return_value=0))

    refreshed = await service.refresh_active_profiles()

    assert refreshed == 1
    refresh_profile.assert_not_awaited()
    assert refresh_schedule.await_args_list[0].args == (media_id,)
    assert refresh_schedule.await_args_list[0].kwargs["season_number"] == 1


@pytest.mark.asyncio
async def test_refresh_active_profiles_skips_fresh_cold_profile(monkeypatch):
    media_id = MediaID.parse("tmdb:movie:1")
    now = time.time()
    active_profile = _ready_profile(media_id, detail_updated_at=now)
    active_profile.release_date = "2020-01-01"
    active_profile.schedule_updated_at = now
    service = MediaProfileService(provider_service=None, schedule_service=MediaScheduleService())
    refresh_profile = AsyncMock()
    refresh_schedule = AsyncMock()

    monkeypatch.setattr(service.lifecycle, "build_active_media_map", AsyncMock(return_value={media_id: None}))
    monkeypatch.setattr(service.profile_repo, "find_active", AsyncMock(return_value=[active_profile]))
    monkeypatch.setattr(service, "refresh_profile", refresh_profile)
    monkeypatch.setattr(service, "refresh_schedule_snapshot", refresh_schedule)
    monkeypatch.setattr(service, "mark_inactive_profiles", AsyncMock(return_value=0))

    refreshed = await service.refresh_active_profiles()

    assert refreshed == 0
    refresh_profile.assert_not_awaited()
    refresh_schedule.assert_not_awaited()


@pytest.mark.asyncio
async def test_refresh_schedule_snapshot_refreshes_placeholder_profile(monkeypatch):
    service = MediaProfileService(provider_service=None, schedule_service=MediaScheduleService())
    media_id = MediaID.parse("tmdb:movie:1")
    placeholder = SimpleNamespace(detail_ready=False)
    refreshed_profile = SimpleNamespace(detail_ready=True)
    refresh_mock = AsyncMock(return_value=refreshed_profile)

    monkeypatch.setattr(service.profile_repo, "find_by_media_id", AsyncMock(return_value=placeholder))
    monkeypatch.setattr(service, "refresh_profile", refresh_mock)

    profile = await service.refresh_schedule_snapshot(media_id)

    refresh_mock.assert_awaited_once_with(media_id, existing=placeholder, season_number=None)
    assert profile == refreshed_profile


@pytest.mark.asyncio
async def test_refresh_schedule_snapshot_refreshes_missing_profile(monkeypatch):
    service = MediaProfileService(provider_service=None, schedule_service=MediaScheduleService())
    media_id = MediaID.parse("tmdb:movie:1")
    refreshed_profile = SimpleNamespace(detail_ready=True)
    refresh_mock = AsyncMock(return_value=refreshed_profile)

    monkeypatch.setattr(service.profile_repo, "find_by_media_id", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "refresh_profile", refresh_mock)

    profile = await service.refresh_schedule_snapshot(media_id)

    refresh_mock.assert_awaited_once_with(media_id, existing=None, season_number=None)
    assert profile == refreshed_profile


@pytest.mark.asyncio
async def test_refresh_schedule_snapshot_requires_tv_season(monkeypatch):
    service = MediaProfileService(provider_service=None, schedule_service=MediaScheduleService())
    media_id = MediaID.parse("tmdb:tv:1")
    refresh_mock = AsyncMock()

    monkeypatch.setattr(service.profile_repo, "find_by_media_id", AsyncMock())
    monkeypatch.setattr(service, "refresh_profile", refresh_mock)

    with pytest.raises(SearchMissingSeasonInfoException):
        await service.refresh_schedule_snapshot(media_id)

    service.profile_repo.find_by_media_id.assert_not_awaited()
    refresh_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_refresh_profile_keeps_existing_schedule_when_schedule_refresh_fails(monkeypatch):
    media_id = MediaID.parse("tmdb:tv:1")
    old_airings = [
        ScheduleAiring(date="2026-01-01", kind="tv_episode_air", season_number=1, episode_number=1),
    ]
    existing = SimpleNamespace(
        media_id=media_id,
        media_type=MediaType.tv,
        title="Sample",
        original_title=None,
        poster_path=None,
        backdrop_path=None,
        logo_path=None,
        year=2024,
        overview=None,
        genres=[],
        imdb_id=None,
        douban_id=None,
        tmdb_id=1,
        primary_metadata_source="tmdb",
        metadata_capabilities=MediaCapabilities(has_schedule=True),
        tvdb_id=None,
        actors=[],
        directors=[],
        studios=[],
        vendors=[],
        duration=None,
        rating_count=None,
        vote_average=None,
        vote_count=None,
        rating_source=None,
        release_date=None,
        first_air_date=None,
        seasons_count=None,
        episodes_count=8,
        seasons=[],
        status=None,
        original_language=None,
        status_label="Sample",
        aired_episode_count=1,
        latest_aired_episode=None,
        next_episode_to_air=None,
        theatrical_release_date=None,
        digital_release_date=None,
        networks=[],
        online_platforms=[],
        airings=old_airings,
        is_active=True,
        last_seen_at=1,
        inactive_since=None,
        detail_ready=True,
        simple_info_updated_at=1,
        detail_updated_at=1,
        schedule_updated_at=123,
        created_at=1,
        updated_at=1,
    )
    existing.model_copy = lambda update: SimpleNamespace(**{**existing.__dict__, **update})
    media = MediaFullInfo(
        media_id=media_id,
        title="Sample",
        year=2024,
        media_type=MediaType.tv,
        tmdb_id=1,
        season_number=1,
        episodes_count=8,
        seasons=[MediaSeasonInfo(season_number=1, episode_count=8)],
        primary_metadata_source="tmdb",
    )
    existing_scope = _scope(
        media_id,
        1,
        status_label="Sample",
        aired_episode_count=1,
        airings=[
            MediaProfileScopeAiring(
                date="2026-01-01",
                kind="tv_episode_air",
                season_number=1,
                episode_number=1,
            )
        ],
    )
    schedule_service = SimpleNamespace(build_schedule_bundle=AsyncMock(side_effect=RuntimeError("tmdb down")))
    provider_service = SimpleNamespace(info=AsyncMock(return_value=media))
    service = MediaProfileService(provider_service=provider_service, schedule_service=schedule_service)

    monkeypatch.setattr(service, "is_managed_media", AsyncMock(return_value=True))
    monkeypatch.setattr(service.profile_repo, "find_by_media_id", AsyncMock(return_value=existing))
    monkeypatch.setattr(service.profile_repo, "upsert_profile", AsyncMock(return_value=True))
    monkeypatch.setattr(service.scope_repo, "find_by_media_id", AsyncMock(return_value=[existing_scope]))

    profile = await service.refresh_profile(media_id, existing=existing, season_number=1)

    assert profile is not None
    assert profile.status_label == "Sample"
    assert profile.airings == old_airings
    assert profile.schedule_updated_at == 123
