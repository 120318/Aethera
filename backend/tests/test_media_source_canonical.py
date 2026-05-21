from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.db.repositories.media_external_mapping_repository import MediaExternalMappingRepository
from app.api.v1.media.detail import get_media_detail
from app.schemas.config import BrowseSource, ServicesConfig, TMDBConfig
from app.schemas.domain.media import EpisodeInfo, MediaFullInfo, MediaSeasonInfo, SeasonDetails
from app.schemas.domain.media_source import MediaSourceLookup, MediaSourceName
from app.schemas.domain.media_types import MediaType
from app.schemas.exception import MediaTMDBMappingRequiredException
from app.schemas.integration.media.provider import ProviderRating, ProviderSearchItem
from app.schemas.media_id import MediaID
from app.services.domain.media.provider.service import MediaProviderService
from app.services.domain.media.provider.mapping import MediaProviderMapping
from app.services.domain.media.provider.normalization import build_tmdb_media_info, normalize_title
from app.services.domain.media.mapping import MediaExternalMappingService, TMDBMappingAttachResult
from app.services.application.workflows.discover import DiscoverService
from app.services.application.views.media_detail_page.service import MediaDetailPageApplicationService, _ResolvedDetailTarget
from app.utils import build_loose_tmdb_search_title, build_tmdb_search_title


pytestmark = [pytest.mark.drift, pytest.mark.health]


class FakeDoubanClient:
    api_key = "test-key"

    async def get_subject_detail(self, source_id, subject_type):
        return SimpleNamespace(
            provider_id=source_id,
            title="text text" if subject_type == "tv" else "Sample",
            original_title="Example",
            year=2025,
            rating=SimpleNamespace(value=8.5, count=1000),
            vendors=[],
            episodes_count=None,
        )

    async def search_movie(self, q, start=0, count=10):
        return [
            SimpleNamespace(
                provider_id="douban-tv-2",
                title="text text",
                year=2025,
                media_type=MediaType.tv,
                rating=ProviderRating(value=8.5, count=1000),
                poster_path="/poster.jpg",
                subtitle="2025 / text / text",
            )
        ]


class FakeTMDBClient:
    api_key = "tmdb-key"

    async def search(self, media_type, query, year=None):
        return [
            ProviderSearchItem(
                provider_id="100088",
                title="Example Show",
                year=2024,
                media_type=MediaType.tv,
                rating=ProviderRating(value=7.8, count=1200),
                poster_path="/poster.jpg",
                overview="Plot",
                original_language="zh",
                genre_ids=[18, 80],
                subtitle="text / text / text",
            )
        ]


def _tmdb_details(provider_id: int) -> SimpleNamespace:
    return SimpleNamespace(
        provider_id=provider_id,
        title="Example Show",
        original_title="Example Show",
        overview="Plot",
        release_date=None,
        theatrical_release_date=None,
        digital_release_date=None,
        first_air_date="2024-01-01",
        poster_path="/poster.jpg",
        backdrop_path="/backdrop.jpg",
        genres=["Drama"],
        actors=[],
        directors=[],
        studios=[],
        networks=[],
        runtime="45",
        seasons=[
            MediaSeasonInfo(season_number=1, episode_count=8, air_date="2024-01-01"),
            MediaSeasonInfo(season_number=2, episode_count=10, air_date="2025-01-01"),
        ],
        seasons_count=2,
        episodes_count=10,
        next_episode_to_air=None,
        selected_season_details=None,
        status="Returning Series",
        original_language="zh",
        external_ids=SimpleNamespace(imdb_id="tt1234567", tvdb_id="7654321"),
        rating=SimpleNamespace(value=7.2, count=200),
    )


def test_build_tmdb_media_info_prefers_selected_season_detail_episode_count():
    details = _tmdb_details(100088)
    details.selected_season_details = SeasonDetails(
        season_number=2,
        episode_count=37,
        episodes=[
            EpisodeInfo(season_number=2, episode_number=episode_number, air_date="2025-01-01")
            for episode_number in range(1, 38)
        ],
    )

    media = build_tmdb_media_info(
        mid=MediaID.parse("tmdb:tv:100088"),
        details=details,
        imdb_id=None,
        vote_average=None,
        rating_count=None,
        rating_source="tmdb",
        season_number=2,
        vendors=[],
    )

    assert media.episodes_count == 37
    assert next(season for season in media.seasons if season.season_number == 2).episode_count == 37


def test_build_tmdb_media_info_uses_manual_episode_count_without_guessing_next_air_date():
    details = _tmdb_details(100088)
    details.seasons = [MediaSeasonInfo(season_number=2, episode_count=10, air_date="2025-01-01")]
    details.episodes_count = 10
    details.selected_season_details = SeasonDetails(
        season_number=2,
        episode_count=10,
        episodes=[
            EpisodeInfo(season_number=2, episode_number=episode_number, air_date="2025-01-01")
            for episode_number in range(1, 11)
        ],
    )

    media = build_tmdb_media_info(
        mid=MediaID.parse("tmdb:tv:100088"),
        details=details,
        imdb_id=None,
        vote_average=None,
        rating_count=None,
        rating_source="douban",
        season_number=2,
        vendors=[],
        episode_count_override=30,
    )

    assert media.episodes_count == 30
    selected_season = next(season for season in media.seasons if season.season_number == 2)
    assert selected_season.episode_count == 10
    assert selected_season.episode_count_override == 30
    assert media.aired_episode_count == 10
    assert media.next_episode_to_air is None
    assert media.schedule is not None
    assert media.schedule.next_episode_to_air is None
    assert media.status_label == "Airing"


def test_build_tmdb_media_info_uses_manual_episode_count_override():
    details = _tmdb_details(100088)
    details.seasons = [MediaSeasonInfo(season_number=2, episode_count=120, air_date="2025-01-01")]
    details.episodes_count = 120
    details.selected_season_details = SeasonDetails(
        season_number=2,
        episode_count=120,
        episodes=[
            EpisodeInfo(season_number=2, episode_number=episode_number, air_date="2025-01-01")
            for episode_number in range(1, 121)
        ],
    )

    media = build_tmdb_media_info(
        mid=MediaID.parse("tmdb:tv:100088"),
        details=details,
        imdb_id=None,
        vote_average=None,
        rating_count=None,
        rating_source="douban",
        season_number=2,
        vendors=[],
        episode_count_override=24,
    )

    assert media.episodes_count == 24
    assert media.episode_count_override == 24
    selected_season = next(season for season in media.seasons if season.season_number == 2)
    assert selected_season.episode_count == 120
    assert selected_season.episode_count_override == 24


@pytest.mark.asyncio
async def test_douban_source_detail_returns_tmdb_canonical_media_id(monkeypatch):
    service = MediaProviderService()
    monkeypatch.setattr(service.clients, "get_douban_client", lambda: FakeDoubanClient())
    monkeypatch.setattr(service.mapping, "get_tmdb_id", AsyncMock(return_value=100088))
    monkeypatch.setattr(service.detail, "get_tmdb_detail_bundle", AsyncMock(return_value=(_tmdb_details(100088), [])))

    media = await service.info_from_source(MediaSourceLookup(source="douban", source_id="douban-tv-2", media_type=MediaType.tv))

    assert str(media.media_id) == "tmdb:tv:100088"
    assert media.douban_id == "douban-tv-2"
    assert media.season_number == 2
    mapping = MediaExternalMappingRepository().find_by_douban_id("douban-tv-2", "tv")
    assert mapping is not None
    assert str(mapping.media_id) == "tmdb:tv:100088"


@pytest.mark.asyncio
async def test_douban_source_episode_count_does_not_override_tmdb_episode_count(monkeypatch):
    class EpisodeCountDoubanClient(FakeDoubanClient):
        async def get_subject_detail(self, source_id, subject_type):
            detail = await super().get_subject_detail(source_id, subject_type)
            detail.episodes_count = 37
            return detail

    service = MediaProviderService()
    monkeypatch.setattr(service.clients, "get_douban_client", lambda: EpisodeCountDoubanClient())
    monkeypatch.setattr(service.mapping, "get_tmdb_id", AsyncMock(return_value=100088))
    monkeypatch.setattr(service.detail, "get_tmdb_detail_bundle", AsyncMock(return_value=(_tmdb_details(100088), [])))

    media = await service.info_from_source(MediaSourceLookup(source="douban", source_id="douban-tv-count", media_type=MediaType.tv))

    assert media.episodes_count == 10
    assert next(season for season in media.seasons if season.season_number == media.season_number).episode_count == 10


@pytest.mark.asyncio
async def test_search_results_keep_douban_as_source_not_media_id(monkeypatch):
    service = MediaProviderService()
    monkeypatch.setattr(service.clients, "get_douban_client", lambda: FakeDoubanClient())

    results = await service.search("Sample", media_type=MediaType.tv)

    assert len(results) == 1
    assert results[0].media_id is None
    assert results[0].source == "douban"
    assert results[0].douban_id == "douban-tv-2"
    assert results[0].title == "text text"
    assert results[0].season_number is None


def test_tmdb_search_title_cleanup_is_conservative():
    assert build_tmdb_search_title("Sample 2026", is_tv=True) == ("Sample", None)
    assert build_tmdb_search_title("Sample (2026)", is_tv=True) == ("Sample", None)
    assert build_tmdb_search_title("老友记 第六季", is_tv=True) == ("老友记", 6)
    assert build_tmdb_search_title("老友记 第 三 季", is_tv=True) == ("老友记", 3)
    assert build_tmdb_search_title("老友记 第 3 季", is_tv=True) == ("老友记", 3)
    assert build_tmdb_search_title("庆余年2", is_tv=True) == ("庆余年", 2)
    assert build_tmdb_search_title("无限超越班4", is_tv=True) == ("无限超越班", 4)
    assert build_tmdb_search_title("无限超越班2026", is_tv=True) == ("无限超越班2026", None)
    assert build_tmdb_search_title("无限超越班88", is_tv=True) == ("无限超越班88", None)
    assert build_tmdb_search_title("Sample2026", is_tv=True) == ("Sample2026", None)
    assert build_tmdb_search_title("Sample3", is_tv=True) == ("Sample3", None)
    assert build_loose_tmdb_search_title("庆余年2") == "庆余年"
    assert build_loose_tmdb_search_title("Sample2026") == "Sample"
    assert build_loose_tmdb_search_title("Sample3") == "Sample3"


def test_provider_title_normalization_keeps_english_letters_and_removes_season_suffixes():
    assert normalize_title("The Expanse") == "the expanse"
    assert normalize_title("老友记 第六季") == "老友记"
    assert normalize_title("老友记 第6季") == "老友记"
    assert normalize_title("Friends Season 6") == "friends"


def test_tmdb_media_info_year_falls_back_to_selected_season_date():
    details = _tmdb_details(302244)
    details.first_air_date = None
    details.seasons = [
        MediaSeasonInfo(season_number=4, episode_count=12, air_date="2026-04-01"),
    ]

    media = build_tmdb_media_info(
        mid=MediaID(provider="tmdb", media_type=MediaType.tv, id="302244"),
        details=details,
        imdb_id=None,
        vote_average=None,
        rating_count=None,
        rating_source="tmdb",
        season_number=4,
        vendors=[],
        douban_id=None,
    )

    assert media.year == 2026


def test_tmdb_media_info_uses_selected_season_details_for_schedule_and_airings():
    details = _tmdb_details(302244)
    details.selected_season_details = SeasonDetails(
        season_number=1,
        air_date="2026-04-01",
        episodes=[
            EpisodeInfo(season_number=1, episode_number=1, air_date="2026-04-01", title="One"),
            EpisodeInfo(season_number=1, episode_number=2, air_date="2026-04-08", title="Two"),
        ],
    )

    media = build_tmdb_media_info(
        mid=MediaID(provider="tmdb", media_type=MediaType.tv, id="302244"),
        details=details,
        imdb_id=None,
        vote_average=None,
        rating_count=None,
        rating_source="tmdb",
        season_number=None,
        vendors=[],
        douban_id=None,
    )

    assert media.season_number == 1
    assert media.schedule is not None
    assert media.schedule.first_air_date == "2026-04-01"
    assert [item.episode_number for item in media.airings] == [1, 2]
    assert media.airings[0].date == "2026-04-01"


@pytest.mark.asyncio
async def test_tv_tmdb_mapping_does_not_auto_match_without_year_when_season_year_filter_has_no_result():
    calls = []

    class FakeClient:
        async def search(self, media_type, query, year=None):
            calls.append((media_type, query, year))
            if year == 2026:
                return []
            return [
                ProviderSearchItem(
                    provider_id="231620",
                    title="无限超越班",
                    year=2023,
                    media_type=MediaType.tv,
                    rating=ProviderRating(value=7.0, count=100),
                )
            ]

    mapping = MediaProviderMapping(clients=SimpleNamespace(get_tmdb_client=lambda: FakeClient()))

    tmdb_id = await mapping.get_tmdb_id("无限超越班", 2026, MediaType.tv)

    assert tmdb_id is None
    assert calls == [
        ("tv", "无限超越班", 2026),
    ]


@pytest.mark.asyncio
async def test_detail_page_douban_title_year_search_strips_tv_season_suffix(monkeypatch):
    service = MediaDetailPageApplicationService()
    mapping = SimpleNamespace(
        mapping_repo=SimpleNamespace(find_by_douban_id=lambda source_id, media_type: None),
        get_tmdb_id=AsyncMock(return_value=37824707),
        canonical_tmdb_media_id=lambda media_type, tmdb_id: MediaID(
            provider="tmdb",
            media_type=media_type,
            id=str(tmdb_id),
        ),
        set_cached_tmdb_mapping=AsyncMock(),
    )
    monkeypatch.setattr(
        "app.services.application.views.media_detail_page.service.media_service.provider_service.mapping",
        mapping,
    )

    target = await service._resolve_target(
        media_id=None,
        source=MediaSourceName.douban,
        source_id="37824707",
        media_type=MediaType.tv,
        title="无限超越班 第四季",
        year=2026,
        season_number=None,
    )

    mapping.get_tmdb_id.assert_awaited_once_with("无限超越班", 2026, MediaType.tv)
    assert str(target.media_id) == "tmdb:tv:37824707"
    assert target.season_number == 4


@pytest.mark.asyncio
async def test_detail_page_douban_title_year_search_defaults_tv_to_first_season(monkeypatch):
    service = MediaDetailPageApplicationService()
    mapping = SimpleNamespace(
        mapping_repo=SimpleNamespace(find_by_douban_id=lambda source_id, media_type: None),
        get_tmdb_id=AsyncMock(return_value=274622),
        canonical_tmdb_media_id=lambda media_type, tmdb_id: MediaID(
            provider="tmdb",
            media_type=media_type,
            id=str(tmdb_id),
        ),
        set_cached_tmdb_mapping=AsyncMock(),
    )
    monkeypatch.setattr(
        "app.services.application.views.media_detail_page.service.media_service.provider_service.mapping",
        mapping,
    )

    target = await service._resolve_target(
        media_id=None,
        source=MediaSourceName.douban,
        source_id="douban-tv-no-season",
        media_type=MediaType.tv,
        title="Sample",
        year=2026,
        season_number=None,
    )

    mapping.get_tmdb_id.assert_awaited_once_with("Sample", 2026, MediaType.tv)
    assert str(target.media_id) == "tmdb:tv:274622"
    assert target.season_number == 1
    assert mapping.set_cached_tmdb_mapping.await_args_list[0].args[4] == 1


@pytest.mark.asyncio
async def test_detail_page_douban_source_keeps_cached_detail_but_hides_tmdb_rating(monkeypatch):
    service = MediaDetailPageApplicationService()
    media = MediaFullInfo(
        media_id=MediaID.parse("tmdb:tv:100088"),
        title="Example Show",
        year=2024,
        media_type=MediaType.tv,
        tmdb_id=100088,
        vote_average=7.2,
        rating_count=200,
        vote_count=200,
        rating_source="tmdb",
        seasons=[MediaSeasonInfo(season_number=1, episode_count=8)],
        primary_metadata_source="tmdb",
    )
    fake_media_service = SimpleNamespace(
        info_with_cache_status=AsyncMock(return_value=(media, "hit")),
        apply_season_context=lambda item, season_number: item.model_copy(update={"season_number": season_number}),
        is_viewed_media=lambda media_id: False,
    )
    monkeypatch.setattr(
        "app.services.application.views.media_detail_page.service.media_service",
        fake_media_service,
    )

    loaded = await service._load_media(_ResolvedDetailTarget(
        media_id=MediaID.parse("tmdb:tv:100088"),
        season_number=1,
        source=MediaSourceName.douban,
        source_id="douban-tv-no-rating",
    ))

    fake_media_service.info_with_cache_status.assert_awaited_once()
    assert loaded.cache_mode == "hit"
    assert loaded.media.douban_id == "douban-tv-no-rating"
    assert loaded.media.vote_average is None
    assert loaded.media.rating_count is None
    assert loaded.media.vote_count is None
    assert loaded.media.rating_source == "douban"


@pytest.mark.asyncio
async def test_detail_page_mapping_required_uses_loose_candidate_search_query(monkeypatch):
    service = MediaDetailPageApplicationService()
    mapping = MediaProviderMapping(clients=SimpleNamespace(get_tmdb_client=lambda: None))
    mapping.mapping_repo = SimpleNamespace(find_by_douban_id=lambda source_id, media_type: None)
    mapping.get_tmdb_id = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "app.services.application.views.media_detail_page.service.media_service.provider_service.mapping",
        mapping,
    )

    with pytest.raises(MediaTMDBMappingRequiredException) as exc_info:
        await service._resolve_target(
            media_id=None,
            source=MediaSourceName.douban,
            source_id="douban-tv-tight-year",
            media_type=MediaType.tv,
            title="无限超越班2026",
            year=2026,
            season_number=None,
        )

    mapping.get_tmdb_id.assert_awaited_once_with("无限超越班2026", 2026, MediaType.tv)
    assert exc_info.value.data.title == "无限超越班2026"
    assert exc_info.value.data.search_query == "无限超越班"


@pytest.mark.asyncio
async def test_douban_source_mapping_required_keeps_display_title_and_search_query(monkeypatch):
    class TightYearDoubanClient(FakeDoubanClient):
        async def get_subject_detail(self, source_id, subject_type):
            detail = await super().get_subject_detail(source_id, subject_type)
            detail.title = "Sample2026"
            detail.year = 2026
            return detail

    service = MediaProviderService()
    monkeypatch.setattr(service.clients, "get_douban_client", lambda: TightYearDoubanClient())
    monkeypatch.setattr(service.mapping, "get_tmdb_id", AsyncMock(return_value=None))

    with pytest.raises(MediaTMDBMappingRequiredException) as exc_info:
        await service.info_from_source(MediaSourceLookup(source="douban", source_id="douban-tv-tight-year", media_type=MediaType.tv))

    payload = exc_info.value.data
    assert payload.title == "Sample2026"
    assert payload.search_query == "Sample"
    assert payload.year == 2026


@pytest.mark.asyncio
async def test_tmdb_search_results_use_canonical_media_id(monkeypatch):
    service = MediaProviderService()
    monkeypatch.setattr(service.clients, "get_tmdb_client", lambda: FakeTMDBClient())

    results = await service.search("Example", media_type=MediaType.tv, source=BrowseSource.tmdb)

    assert len(results) == 1
    assert str(results[0].media_id) == "tmdb:tv:100088"
    assert results[0].source == "tmdb"
    assert results[0].source_id == "100088"
    assert results[0].season_number is None
    assert results[0].overview == "Plot"
    assert results[0].original_language == "zh"
    assert results[0].genre_ids == [18, 80]
    assert results[0].subtitle_line1 == "text / text / text"
    assert results[0].subtitle_line2 is None


@pytest.mark.asyncio
async def test_tmdb_discover_results_use_canonical_media_id(monkeypatch):
    service = DiscoverService()
    monkeypatch.setattr("app.services.application.workflows.discover.service.media_service.discover_available", lambda source: True)
    monkeypatch.setattr("app.services.application.workflows.discover.service.media_service.supports_discover_key", lambda source, key: key == "tv_popular")
    monkeypatch.setattr(
        "app.services.application.workflows.discover.service.media_service.discover_items",
        AsyncMock(
            return_value=[
                ProviderSearchItem(
                    provider_id="100088",
                    title="Example Show",
                    year=2024,
                    media_type=MediaType.tv,
                    rating=ProviderRating(value=7.8, count=1200),
                    poster_path="/poster.jpg",
                    overview="Plot",
                    original_language="zh",
                    genre_ids=[18, 80],
                    subtitle="text / text / text",
                )
            ]
        ),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.discover.service.settings_service.get_base_services_config",
        lambda: ServicesConfig(
            browse_source=BrowseSource.tmdb,
            themoviedb=TMDBConfig(api_key="tmdb-key", discover_lists=["tv_popular"]),
        ),
    )
    monkeypatch.setattr(service, "_load_cached_list", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "_cache_list", AsyncMock())

    lists = await service.get_lists(None, 10)

    assert len(lists) == 1
    assert lists[0].key == "tv_popular"
    assert str(lists[0].items[0].media_id) == "tmdb:tv:100088"
    assert lists[0].items[0].source == "tmdb"
    assert lists[0].items[0].overview == "Plot"
    assert lists[0].items[0].original_language == "zh"
    assert lists[0].items[0].genre_ids == [18, 80]
    assert lists[0].items[0].subtitle_line1 == "text / text / text"
    assert lists[0].items[0].subtitle_line2 is None


@pytest.mark.asyncio
async def test_tmdb_source_detail_defaults_to_first_season_in_route(monkeypatch):
    media = MediaFullInfo(
        media_id=MediaID.parse("tmdb:tv:100088"),
        title="Example Show",
        year=2024,
        media_type=MediaType.tv,
        seasons=[
            MediaSeasonInfo(season_number=1, episode_count=8),
            MediaSeasonInfo(season_number=2, episode_count=10),
        ],
    )
    media_info = AsyncMock(return_value=media)
    monkeypatch.setattr("app.services.application.views.media_detail.service.media_service.info", media_info)
    monkeypatch.setattr("app.services.application.views.media_detail.service.media_service.is_viewed_media", lambda _media_id: False)

    response = await get_media_detail(
        mid=None,
        source=MediaSourceName.tmdb,
        source_id="100088",
        media_type=MediaType.tv,
    )

    assert str(response.media.media_id) == "tmdb:tv:100088"
    assert response.media.season_number == 1
    assert response.media.episodes_count == 8
    media_info.assert_awaited_once_with(MediaID.parse("tmdb:tv:100088"), season_number=1)


@pytest.mark.asyncio
async def test_douban_source_uses_existing_mapping_without_tmdb_search(monkeypatch):
    repo = MediaExternalMappingRepository()
    repo.upsert(
        MediaID(provider="douban", media_type=MediaType.tv, id="douban-tv-existing"),
        tmdb_id=100088,
        imdb_id="tt1234567",
        douban_id="douban-tv-existing",
        season_number=2,
    )
    service = MediaProviderService()
    monkeypatch.setattr(service.clients, "get_douban_client", lambda: FakeDoubanClient())
    tmdb_search = AsyncMock(return_value=100088)
    monkeypatch.setattr(service.mapping, "get_tmdb_id", tmdb_search)
    monkeypatch.setattr(service.detail, "get_tmdb_detail_bundle", AsyncMock(return_value=(_tmdb_details(100088), [])))

    media = await service.info_from_source(MediaSourceLookup(source="douban", source_id="douban-tv-existing", media_type=MediaType.tv))

    assert str(media.media_id) == "tmdb:tv:100088"
    assert media.season_number == 2
    tmdb_search.assert_not_awaited()
    canonical_mapping = repo.find_by_media_id_and_season(MediaID(provider="tmdb", media_type=MediaType.tv, id="100088"), 2)
    assert canonical_mapping is not None
    assert canonical_mapping.douban_id == "douban-tv-existing"


def test_external_mapping_upsert_writes_episode_count_override_directly():
    repo = MediaExternalMappingRepository()
    media_id = MediaID(provider="tmdb", media_type=MediaType.tv, id="100088")
    repo.upsert(
        media_id,
        tmdb_id=100088,
        imdb_id="tt1234567",
        douban_id="douban-tv-override",
        season_number=2,
        episode_count_override=8,
    )
    mapping = repo.find_by_media_id_and_season(media_id, 2)
    assert mapping is not None
    assert mapping.episode_count_override == 8

    repo.upsert(
        media_id,
        tmdb_id=100088,
        imdb_id="tt1234567",
        douban_id="douban-tv-override",
        season_number=2,
    )

    mapping = repo.find_by_media_id_and_season(media_id, 2)
    assert mapping is not None
    assert mapping.episode_count_override is None

    repo.upsert(
        media_id,
        tmdb_id=100088,
        imdb_id="tt1234567",
        douban_id="douban-tv-override",
        season_number=2,
        episode_count_override=None,
    )

    mapping = repo.find_by_media_id_and_season(media_id, 2)
    assert mapping is not None
    assert mapping.episode_count_override is None


def test_external_mapping_rollback_restores_episode_count_override():
    repo = MediaExternalMappingRepository()
    service = MediaExternalMappingService(mapping_repo=repo)
    previous_media_id = MediaID(provider="douban", media_type=MediaType.tv, id="douban-tv-rollback")
    canonical_media_id = MediaID(provider="tmdb", media_type=MediaType.tv, id="100090")
    repo.upsert(
        previous_media_id,
        tmdb_id=100090,
        imdb_id="ttrollback",
        douban_id="douban-tv-rollback",
        season_number=4,
        episode_count_override=11,
    )
    previous_mapping = repo.find_by_douban_id("douban-tv-rollback", "tv")
    assert previous_mapping is not None

    repo.upsert(
        canonical_media_id,
        tmdb_id=100090,
        imdb_id="ttrollback-new",
        douban_id="douban-tv-rollback",
        season_number=4,
        episode_count_override=None,
    )

    service.rollback_tmdb_mapping_attach(
        TMDBMappingAttachResult(
            canonical_media_id=canonical_media_id,
            source_media_id=previous_media_id,
            season_number=4,
            previous_mapping=previous_mapping,
        )
    )

    restored = repo.find_by_douban_id("douban-tv-rollback", "tv")
    assert restored is not None
    assert restored.media_id == previous_media_id
    assert restored.episode_count_override == 11


@pytest.mark.asyncio
async def test_douban_source_existing_mapping_keeps_empty_douban_rating(monkeypatch):
    repo = MediaExternalMappingRepository()
    repo.upsert(
        MediaID(provider="douban", media_type=MediaType.tv, id="douban-tv-no-rating"),
        tmdb_id=100088,
        imdb_id="tt1234567",
        douban_id="douban-tv-no-rating",
        season_number=2,
    )
    service = MediaProviderService()

    class NoRatingDoubanClient(FakeDoubanClient):
        async def get_subject_detail(self, source_id, subject_type):
            detail = await super().get_subject_detail(source_id, subject_type)
            detail.rating = ProviderRating(value=0.0, count=0)
            return detail

    tmdb_details = _tmdb_details(100088)
    tmdb_details.rating = ProviderRating(value=7.2, count=200)
    monkeypatch.setattr(service.clients, "get_douban_client", lambda: NoRatingDoubanClient())
    monkeypatch.setattr(service.detail, "get_tmdb_detail_bundle", AsyncMock(return_value=(tmdb_details, [])))

    media = await service.info_from_source(MediaSourceLookup(source="douban", source_id="douban-tv-no-rating", media_type=MediaType.tv))

    assert str(media.media_id) == "tmdb:tv:100088"
    assert media.douban_id == "douban-tv-no-rating"
    assert media.vote_average is None
    assert media.rating_count is None
    assert media.vote_count is None
    assert media.rating_source == "douban"


@pytest.mark.asyncio
async def test_douban_search_viewed_uses_source_mapping(monkeypatch):
    repo = MediaExternalMappingRepository()
    repo.upsert(
        MediaID(provider="tmdb", media_type=MediaType.tv, id="100088"),
        tmdb_id=100088,
        imdb_id="tt1234567",
        douban_id="douban-tv-2",
        season_number=2,
    )
    service = MediaProviderService()
    monkeypatch.setattr(service.clients, "get_douban_client", lambda: FakeDoubanClient())
    results = await service.search("Sample", media_type=MediaType.tv)

    from app.services.domain.media import MediaService

    MediaService().mark_viewed_search_results(results)

    assert results[0].media_id is None
    assert results[0].source == "douban"
    assert results[0].source_id == "douban-tv-2"
    assert results[0].viewed is True


@pytest.mark.asyncio
async def test_tmdb_search_viewed_uses_canonical_mapping(monkeypatch):
    repo = MediaExternalMappingRepository()
    repo.upsert(
        MediaID(provider="tmdb", media_type=MediaType.tv, id="100088"),
        tmdb_id=100088,
        imdb_id="tt1234567",
        douban_id=None,
        season_number=None,
    )
    service = MediaProviderService()
    monkeypatch.setattr(service.clients, "get_tmdb_client", lambda: FakeTMDBClient())
    results = await service.search("Example", media_type=MediaType.tv, source=BrowseSource.tmdb)

    from app.services.domain.media import MediaService

    MediaService().mark_viewed_search_results(results)

    assert str(results[0].media_id) == "tmdb:tv:100088"
    assert results[0].source == "tmdb"
    assert results[0].source_id == "100088"
    assert results[0].viewed is True
