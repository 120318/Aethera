import pytest

from datetime import date, timedelta

from app.schemas.domain.media import EpisodeInfo, MediaFullInfo
from app.schemas.domain.media_context import MediaCapabilities
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.schedule import MediaScheduleSummary, ScheduleAiring, SchedulePlatform
from app.schemas.domain.vendor import Vendor
from app.schemas.media_id import MediaID
from app.services.domain.media.schedule import service as schedule_module
from app.services.domain.media.profile.context import media_profile_context_service
from app.services.domain.media.profile.scope_projection import build_scope_from_media
from app.services.domain.media.schedule.service import MediaScheduleService


def test_resolution_service_marks_douban_only_media_with_base_capabilities():
    media = MediaFullInfo(
        media_id=MediaID.parse("douban:movie:1"),
        title="Test Movie",
        year=2024,
        media_type=MediaType.movie,
        douban_id="1",
    )

    enriched = media_profile_context_service.enrich_media(media)

    assert enriched.primary_metadata_source == "douban"
    assert enriched.metadata_capabilities.has_enhanced_detail is False
    assert enriched.metadata_capabilities.has_schedule is False
    assert enriched.metadata_capabilities.has_movie_release_window is False


def test_resolution_service_marks_tmdb_media_with_enhanced_capabilities():
    media = MediaFullInfo(
        media_id=MediaID.parse("douban:tv:1"),
        title="Test Show",
        year=2024,
        media_type=MediaType.tv,
        douban_id="1",
        tmdb_id=123,
        primary_metadata_source="tmdb",
    )

    enriched = media_profile_context_service.enrich_media(media)

    assert enriched.primary_metadata_source == "tmdb"
    assert enriched.metadata_capabilities.has_enhanced_detail is True
    assert enriched.metadata_capabilities.has_schedule is True
    assert enriched.metadata_capabilities.has_season_episode_detail is True


def test_resolution_service_uses_tmdb_source_when_tmdb_id_exists_even_if_input_source_is_douban():
    media = MediaFullInfo(
        media_id=MediaID.parse("douban:tv:1"),
        title="Fallback Show",
        year=2024,
        media_type=MediaType.tv,
        douban_id="1",
        tmdb_id=123,
        primary_metadata_source="douban",
    )

    enriched = media_profile_context_service.enrich_media(media)

    assert enriched.primary_metadata_source == "tmdb"
    assert enriched.metadata_capabilities.has_enhanced_detail is True
    assert enriched.metadata_capabilities.has_schedule is True


def test_resolution_service_uses_tmdb_source_for_simple_media_when_tmdb_id_exists():
    from app.schemas.domain.media import MediaSimpleInfo

    media = MediaSimpleInfo(
        media_id=MediaID.parse("douban:tv:3"),
        title="Fallback Simple Show",
        year=2024,
        media_type=MediaType.tv,
        douban_id="3",
        tmdb_id=123,
        primary_metadata_source="douban",
        metadata_capabilities=MediaCapabilities(),
    )

    enriched = media_profile_context_service.enrich_simple_media(media)

    assert enriched.primary_metadata_source == "tmdb"
    assert enriched.metadata_capabilities.has_enhanced_detail is True
    assert enriched.metadata_capabilities.has_schedule is True


@pytest.mark.asyncio
async def test_schedule_service_degrades_cleanly_without_tmdb():
    media = media_profile_context_service.enrich_media(
        MediaFullInfo(
            media_id=MediaID.parse("douban:tv:2"),
            title="Douban Only Show",
            year=2024,
            media_type=MediaType.tv,
            douban_id="2",
            first_air_date="2024-01-01",
            episodes_count=12,
        )
    )

    summary = await MediaScheduleService().build_tv_schedule_summary(media, season_number=None)

    assert summary.first_air_date == "2024-01-01"
    assert summary.status_label is None
    assert summary.platforms == []
    assert summary.next_episode_to_air is None


@pytest.mark.asyncio
async def test_schedule_service_uses_douban_vendor_web_url_for_tv_network():
    media = MediaFullInfo(
        media_id=MediaID.parse("douban:tv:35805716"),
        title="Sample",
        year=2026,
        media_type=MediaType.tv,
        douban_id="35805716",
        first_air_date="2026-03-23",
        schedule=MediaScheduleSummary(
            media_type=MediaType.tv,
            platforms=[SchedulePlatform(id="iqiyi", name="iQIYI", url="https://www.iqiyi.com/")],
        ),
        vendors=[
            Vendor(
                id="iqiyi",
                name="Sample",
                url="http://www.iqiyi.com/v_1lr0jb5ixi8.html?vfm=m_331_dbdy",
            )
        ],
    )

    summary = await MediaScheduleService().build_tv_schedule_summary(media, season_number=None)

    assert len(summary.platforms) == 1
    assert summary.platforms[0].name == "爱奇艺"
    assert summary.platforms[0].url == "http://www.iqiyi.com/v_1lr0jb5ixi8.html?vfm=m_331_dbdy"


@pytest.mark.asyncio
async def test_schedule_service_converts_tencent_douban_deeplink_to_web_play_url():
    media = MediaFullInfo(
        media_id=MediaID.parse("douban:tv:36939912"),
        title="Sample",
        year=2026,
        media_type=MediaType.tv,
        douban_id="36939912",
        first_air_date="2026-04-01",
        schedule=MediaScheduleSummary(
            media_type=MediaType.tv,
            platforms=[SchedulePlatform(id="tencent", name="Tencent Video", url="https://v.qq.com/")],
        ),
        vendors=[
            Vendor(
                id="qq",
                name="Sample",
                url="douban://douban.com/goToWXMiniProgram?path=preload_play/play/index?cid=mzc002007tp60ap&vid=w41025my54z&type=0&id=gh_fce17bb0518f",
            )
        ],
    )

    summary = await MediaScheduleService().build_tv_schedule_summary(media, season_number=None)

    assert len(summary.platforms) == 1
    assert summary.platforms[0].name == "腾讯视频"
    assert summary.platforms[0].url == "https://v.qq.com/x/cover/mzc002007tp60ap/w41025my54z.html"


@pytest.mark.asyncio
async def test_schedule_service_dedupes_tencent_platform_aliases():
    media = MediaFullInfo(
        media_id=MediaID.parse("douban:tv:36939912"),
        title="Sample",
        year=2026,
        media_type=MediaType.tv,
        douban_id="36939912",
        first_air_date="2026-04-01",
        schedule=MediaScheduleSummary(
            media_type=MediaType.tv,
            platforms=[
                SchedulePlatform(id="tencent", name="腾讯视频", url="https://v.qq.com/"),
                SchedulePlatform(id="2008", name="Tencent Video", url="https://www.themoviedb.org/tv/1/watch"),
                SchedulePlatform(id=None, name="腾讯视频平台", url="https://v.qq.com/channel/tv"),
            ],
        ),
        vendors=[
            Vendor(
                id="qq",
                name="腾讯视频平台",
                url="https://v.qq.com/channel/tv",
            )
        ],
    )

    summary = await MediaScheduleService().build_tv_schedule_summary(media, season_number=None)

    assert len(summary.platforms) == 1
    assert summary.platforms[0].name == "腾讯视频"


@pytest.mark.asyncio
async def test_schedule_service_dedupes_prime_video_platform_aliases():
    media = MediaFullInfo(
        media_id=MediaID.parse("tmdb:tv:287641"),
        title="Sample",
        year=2026,
        media_type=MediaType.tv,
        tmdb_id=287641,
        first_air_date="2026-05-13",
        schedule=MediaScheduleSummary(
            media_type=MediaType.tv,
            platforms=[
                SchedulePlatform(id=None, name="Prime Video", url="https://www.primevideo.com/"),
                SchedulePlatform(id="9", name="Amazon Prime Video", url="https://www.themoviedb.org/tv/287641/watch", region="US"),
                SchedulePlatform(id="119", name="Amazon Prime Video with Ads", url="https://www.themoviedb.org/tv/287641/watch", region="US"),
                SchedulePlatform(id=None, name="Amazon Prime Video Free with Ads", url="https://www.themoviedb.org/tv/287641/watch", region="US"),
            ],
        ),
    )

    summary = await MediaScheduleService().build_tv_schedule_summary(media, season_number=None)

    assert len(summary.platforms) == 1
    assert summary.platforms[0].name == "Prime Video"
    payload = summary.model_dump(mode="json")
    assert [platform["name"] for platform in payload["platforms"]] == ["Prime Video"]
    assert "networks" not in payload
    assert "online_platforms" not in payload


@pytest.mark.asyncio
async def test_schedule_service_keeps_amazon_video_separate_from_prime_video():
    media = MediaFullInfo(
        media_id=MediaID.parse("tmdb:tv:1"),
        title="Sample",
        year=2026,
        media_type=MediaType.tv,
        tmdb_id=1,
        schedule=MediaScheduleSummary(
            media_type=MediaType.tv,
            platforms=[
                SchedulePlatform(id="9", name="Amazon Prime Video", url="https://www.themoviedb.org/tv/1/watch", region="US"),
                SchedulePlatform(id=None, name="Amazon Video", url="https://www.amazon.com/video", region="US"),
            ],
        ),
    )

    summary = await MediaScheduleService().build_tv_schedule_summary(media, season_number=None)

    assert [platform.name for platform in summary.platforms] == ["Prime Video", "Amazon Video"]


def test_scope_projection_persists_schedule_summary_platforms_without_airings():
    media = MediaFullInfo(
        media_id=MediaID.parse("tmdb:movie:1"),
        title="Sample",
        year=2026,
        media_type=MediaType.movie,
        schedule=MediaScheduleSummary(
            media_type=MediaType.movie,
            platforms=[SchedulePlatform(id="9", name="Prime Video", url="https://www.primevideo.com/")],
        ),
    )

    scope = build_scope_from_media(media)

    assert scope is not None
    assert [platform.name for platform in scope.platforms] == ["Prime Video"]
    assert scope.platforms[0].roles == ["online"]
    assert scope.platforms[0].source == "schedule"


def test_scope_projection_does_not_infer_tv_online_platforms_without_airings():
    media = MediaFullInfo(
        media_id=MediaID.parse("tmdb:tv:1"),
        title="Sample",
        year=2026,
        media_type=MediaType.tv,
        season_number=1,
        schedule=MediaScheduleSummary(
            media_type=MediaType.tv,
            platforms=[SchedulePlatform(id="network-1", name="Network One")],
        ),
    )

    scope = build_scope_from_media(media)

    assert scope is not None
    assert scope.platforms == []


def test_scope_projection_keeps_tv_schedule_online_platforms_when_airings_identify_networks():
    media = MediaFullInfo(
        media_id=MediaID.parse("tmdb:tv:1"),
        title="Sample",
        year=2026,
        media_type=MediaType.tv,
        season_number=1,
        schedule=MediaScheduleSummary(
            media_type=MediaType.tv,
            platforms=[
                SchedulePlatform(id="network-1", name="Network One"),
                SchedulePlatform(id="stream-1", name="Stream One"),
            ],
        ),
        airings=[
            ScheduleAiring(
                date="2026-05-13",
                kind="tv_episode_air",
                season_number=1,
                episode_number=1,
                platforms=[SchedulePlatform(id="network-1", name="Network One")],
            )
        ],
    )

    scope = build_scope_from_media(media)

    assert scope is not None
    roles_by_name = {platform.name: platform.roles for platform in scope.platforms}
    assert {name: set(roles) for name, roles in roles_by_name.items()} == {
        "Network One": {"network", "airing"},
        "Stream One": {"online"},
    }


@pytest.mark.asyncio
async def test_tv_schedule_bundle_keeps_online_platforms_off_episode_airings(monkeypatch):
    service = MediaScheduleService()
    media = MediaFullInfo(
        media_id=MediaID.parse("tmdb:tv:1"),
        title="Sample",
        year=2026,
        media_type=MediaType.tv,
        tmdb_id=1,
        primary_metadata_source="tmdb",
        metadata_capabilities=MediaCapabilities(has_schedule=True),
        season_number=1,
        first_air_date="2026-05-13",
        episodes_count=1,
        schedule=MediaScheduleSummary(
            media_type=MediaType.tv,
            platforms=[
                SchedulePlatform(id=None, name="Prime Video", url="https://www.primevideo.com/"),
                SchedulePlatform(id=None, name="Amazon Video", url="https://www.amazon.com/video", region="US"),
            ],
        ),
        airings=[
            ScheduleAiring(
                date="2026-05-13",
                kind="tv_episode_air",
                season_number=1,
                episode_number=1,
                platforms=[SchedulePlatform(id=None, name="Prime Video", url="https://www.primevideo.com/")],
            )
        ],
    )
    episodes = [
        EpisodeInfo(season_number=1, episode_number=1, air_date="2026-05-13", title="Pilot"),
    ]

    async def _inputs(context, season_number):
        return list(episodes), list(episodes), "2026-05-13"

    monkeypatch.setattr(service, "_build_tv_schedule_inputs", _inputs)

    summary, airings = await service.build_schedule_bundle(media)

    assert [platform.name for platform in summary.platforms] == ["Prime Video", "Amazon Video"]
    assert len(airings) == 1
    assert [platform.name for platform in airings[0].platforms] == ["Prime Video"]


@pytest.mark.asyncio
async def test_schedule_service_converts_youku_douban_deeplink_to_web_show_url():
    media = MediaFullInfo(
        media_id=MediaID.parse("douban:tv:35922594"),
        title="Sample",
        year=2025,
        media_type=MediaType.tv,
        douban_id="35922594",
        first_air_date="2025-01-01",
        schedule=MediaScheduleSummary(
            media_type=MediaType.tv,
            platforms=[SchedulePlatform(id="1419", name="Youku", url="https://www.youku.com/")],
        ),
        vendors=[
            Vendor(
                id="youku",
                name="Sample",
                url="douban://douban.com/goToWXMiniProgram?path=/pages/play/play%3FshowId%3Ddccc1a382ea3456eaa77%26refer%3Ddouban&id=gh_e548b8705c95&type=0",
            )
        ],
    )

    summary = await MediaScheduleService().build_tv_schedule_summary(media, season_number=None)

    assert len(summary.platforms) == 1
    assert summary.platforms[0].name == "优酷"
    assert summary.platforms[0].url == "https://v.youku.com/v_nextstage/id_dccc1a382ea3456eaa77.html"


@pytest.mark.asyncio
async def test_schedule_service_ignores_unresolved_non_web_vendor_deeplink():
    media = MediaFullInfo(
        media_id=MediaID.parse("douban:tv:1"),
        title="Unknown Deeplink",
        year=2026,
        media_type=MediaType.tv,
        douban_id="1",
        first_air_date="2026-04-01",
        schedule=MediaScheduleSummary(
            media_type=MediaType.tv,
            platforms=[SchedulePlatform(id="mgtv", name="Mango TV", url="https://www.mgtv.com/")],
        ),
        vendors=[Vendor(id="mgtv", name="textTV", url="mgtv://video/123")],
    )

    summary = await MediaScheduleService().build_tv_schedule_summary(media, season_number=None)

    assert len(summary.platforms) == 1
    assert summary.platforms[0].name == "芒果TV"
    assert summary.platforms[0].url == "https://www.mgtv.com/"


@pytest.mark.asyncio
async def test_schedule_service_drops_stale_next_episode_from_details_layer(monkeypatch):
    service = MediaScheduleService()
    media = MediaFullInfo(
        media_id=MediaID.parse("douban:tv:36093334"),
        title="Sample",
        year=2026,
        media_type=MediaType.tv,
        douban_id="36093334",
        tmdb_id=272476,
        primary_metadata_source="tmdb",
        metadata_capabilities=MediaCapabilities(has_schedule=True),
        first_air_date="2026-04-14",
        episodes_count=22,
        next_episode_to_air=EpisodeInfo(
            season_number=1,
            episode_number=16,
            air_date="2000-04-23",
            title="Sample",
        ),
    )
    aired_episodes = [
        EpisodeInfo(season_number=1, episode_number=21, air_date="2000-04-23", title="text 21 text"),
        EpisodeInfo(season_number=1, episode_number=22, air_date="2000-04-24", title="text 22 text"),
    ]

    async def _inputs(context, season_number):
        return list(aired_episodes), list(aired_episodes), "2000-04-23"

    monkeypatch.setattr(service, "_build_tv_schedule_inputs", _inputs)

    summary = await service.build_tv_schedule_summary(media, season_number=1)

    assert summary.aired_episode_count == 2
    assert summary.latest_aired_episode is not None
    assert summary.latest_aired_episode.episode_number == 22
    assert summary.next_episode_to_air is None


@pytest.mark.asyncio
async def test_schedule_service_keeps_next_episode_across_new_season(monkeypatch):
    service = MediaScheduleService()
    next_air_date = (date.today() + timedelta(days=7)).isoformat()
    media = MediaFullInfo(
        media_id=MediaID.parse("douban:tv:36093334"),
        title="Sample",
        year=2026,
        media_type=MediaType.tv,
        douban_id="36093334",
        tmdb_id=272476,
        primary_metadata_source="tmdb",
        metadata_capabilities=MediaCapabilities(has_schedule=True),
        first_air_date="2026-04-14",
        episodes_count=10,
        next_episode_to_air=EpisodeInfo(
            season_number=2,
            episode_number=1,
            air_date=next_air_date,
            title="Sample",
        ),
    )
    aired_episodes = [
        EpisodeInfo(season_number=1, episode_number=10, air_date="2026-04-23", title="text 10 text"),
    ]

    async def _inputs(context, season_number):
        return list(aired_episodes), list(aired_episodes), "2026-04-23"

    monkeypatch.setattr(service, "_build_tv_schedule_inputs", _inputs)

    summary = await service.build_tv_schedule_summary(media, season_number=1)

    assert summary.latest_aired_episode is not None
    assert summary.latest_aired_episode.season_number == 1
    assert summary.latest_aired_episode.episode_number == 10
    assert summary.next_episode_to_air is not None
    assert summary.next_episode_to_air.season_number == 2
    assert summary.next_episode_to_air.episode_number == 1


@pytest.mark.asyncio
async def test_schedule_service_counts_episode_airing_today_as_aired(monkeypatch):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 4, 27)

    service = MediaScheduleService()
    media = MediaFullInfo(
        media_id=MediaID.parse("tmdb:tv:272476"),
        title="Sample",
        year=2026,
        media_type=MediaType.tv,
        tmdb_id=272476,
        primary_metadata_source="tmdb",
        metadata_capabilities=MediaCapabilities(has_schedule=True),
        first_air_date="2026-04-14",
        episodes_count=2,
        status="Ended",
    )
    season_episodes = [
        EpisodeInfo(season_number=1, episode_number=1, air_date="2026-04-20", title="Sample"),
        EpisodeInfo(season_number=1, episode_number=2, air_date="2026-04-27", title="Sample"),
    ]

    async def _inputs(context, season_number):
        return list(season_episodes), service._tv_aired_episodes(season_episodes), "2026-04-14"

    monkeypatch.setattr(schedule_module, "date", FixedDate)
    monkeypatch.setattr(service, "_build_tv_schedule_inputs", _inputs)

    summary = await service.build_tv_schedule_summary(media, season_number=1)

    assert summary.status_label == "Ended"
    assert summary.aired_episode_count == 2
    assert summary.latest_aired_episode is not None
    assert summary.latest_aired_episode.episode_number == 2
    assert summary.next_episode_to_air is None


@pytest.mark.asyncio
async def test_schedule_service_fetches_only_selected_tv_season(monkeypatch):
    service = MediaScheduleService()
    media = MediaFullInfo(
        media_id=MediaID.parse("tmdb:tv:272476"),
        title="Sample",
        year=2026,
        media_type=MediaType.tv,
        tmdb_id=272476,
        primary_metadata_source="tmdb",
        metadata_capabilities=MediaCapabilities(has_schedule=True),
        season_number=20,
        episodes_count=2,
    )
    requested = []

    async def fake_season_details(tmdb_id, season_number):
        requested.append((tmdb_id, season_number))
        return type("Season", (), {
            "air_date": None,
            "episodes": [
                EpisodeInfo(season_number=season_number, episode_number=1, air_date="2000-01-01", title="Sample"),
                EpisodeInfo(season_number=season_number, episode_number=2, air_date="2000-01-02", title="Sample"),
            ]
        })()

    monkeypatch.setattr(service, "_get_schedule_season_details", fake_season_details)

    summary = await service.build_schedule_summary_for_media(media)

    assert requested == [(272476, 20)]
    assert summary.aired_episode_count == 2
    assert summary.latest_aired_episode.season_number == 20


@pytest.mark.asyncio
async def test_schedule_service_uses_selected_season_first_air_date(monkeypatch):
    service = MediaScheduleService()
    media = MediaFullInfo(
        media_id=MediaID.parse("tmdb:tv:60574"),
        title="Sample",
        year=2019,
        media_type=MediaType.tv,
        tmdb_id=60574,
        primary_metadata_source="tmdb",
        metadata_capabilities=MediaCapabilities(has_schedule=True),
        first_air_date="2019-09-03",
        season_number=4,
        episodes_count=6,
    )

    async def fake_season_details(tmdb_id, season_number):
        return type("Season", (), {
            "air_date": "2023-02-01",
            "episodes": [
                EpisodeInfo(season_number=season_number, episode_number=1, air_date="2023-02-02", title="Sample"),
                EpisodeInfo(season_number=season_number, episode_number=2, air_date="2023-02-09", title="Sample"),
            ],
        })()

    monkeypatch.setattr(service, "_get_schedule_season_details", fake_season_details)

    summary = await service.build_schedule_summary_for_media(media)

    assert summary.first_air_date == "2023-02-01"
