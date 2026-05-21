import asyncio
import json
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch

from app.addons.descriptors import _danmu_jobs
from app.core.action_context import action_context
from app.schemas.config import AddonsConfig
from app.schemas.domain.addon_events import ImportedMediaFile, MediaImportCompletedEventMeta
from app.schemas.domain.action import ActionTrigger
from app.schemas.domain.event import Event, EventType
from app.schemas.domain.library import LibraryFile, LibraryFileArtifact, LibraryFileArtifactStatus, LibraryFileArtifactType
from app.schemas.domain.media import MediaFullInfo
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.vendor import Vendor
from app.schemas.media_id import MediaID
from app.services.application.workflows.danmu.service import DanmuApplicationService
from app.services.application.workflows.danmu.duration_guard import danmu_duration_guard
from app.services.application.workflows.danmu.formatters import build_ass, build_xml
from app.services.application.workflows.danmu.sidecar_outputs import remove_outputs, sidecar_path
from app.services.integration.danmu.models import DanmuComment, DanmuFetchInput, DanmuFetchResult
from app.services.integration.danmu.providers.bilibili import BilibiliDanmuProvider
from app.services.integration.danmu.providers.iqiyi import IqiyiDanmuProvider
from app.services.integration.danmu.providers.qq import QQDanmuProvider
from app.services.integration.danmu.providers.youku import YoukuDanmuProvider
from app.services.integration.danmu.service import DanmuProviderService
from app.services.integration.danmu.utils import extract_youku_show_id, parse_qq_json


class TestDanmuAddonContracts(unittest.TestCase):
    def test_default_config_is_disabled_with_supported_providers(self):
        config = AddonsConfig()

        self.assertFalse(config.danmu.enabled)
        self.assertEqual(["iqiyi", "bilibili", "youku", "qq"], config.danmu.providers)
        self.assertTrue(config.danmu.output_xml)
        self.assertTrue(config.danmu.output_ass)
        self.assertEqual(60, config.danmu.font_size)
        self.assertEqual(80, config.danmu.font_opacity_percent)
        self.assertEqual(20, config.danmu.scroll_duration_seconds)
        self.assertEqual(20, config.danmu.density_percent)
        self.assertEqual("top", config.danmu.display_area)
        self.assertEqual(120, config.danmu.duration_tolerance_seconds)
        self.assertTrue(config.danmu.backfill_enabled)
        self.assertEqual(21600, config.danmu.backfill_interval_seconds)
        self.assertEqual(30, config.danmu.backfill_recent_days)
        self.assertEqual(90, config.danmu.backfill_missing_window_days)

    def test_config_clamps_danmu_visual_settings(self):
        too_small = AddonsConfig.model_validate(
            {"danmu": {"font_size": 1, "font_opacity_percent": 1, "scroll_duration_seconds": 1, "density_percent": 1}}
        )
        too_large = AddonsConfig.model_validate(
            {"danmu": {"font_size": 200, "font_opacity_percent": 200, "scroll_duration_seconds": 90, "density_percent": 200}}
        )

        self.assertEqual(18, too_small.danmu.font_size)
        self.assertEqual(30, too_small.danmu.font_opacity_percent)
        self.assertEqual(5, too_small.danmu.scroll_duration_seconds)
        self.assertEqual(10, too_small.danmu.density_percent)
        self.assertEqual(96, too_large.danmu.font_size)
        self.assertEqual(100, too_large.danmu.font_opacity_percent)
        self.assertEqual(35, too_large.danmu.scroll_duration_seconds)
        self.assertEqual(100, too_large.danmu.density_percent)

    def test_config_clamps_danmu_backfill_settings(self):
        config = AddonsConfig.model_validate(
            {"danmu": {"backfill_interval_seconds": 1, "backfill_recent_days": 0, "backfill_missing_window_days": 0, "duration_tolerance_seconds": -1}}
        )

        self.assertEqual(60, config.danmu.backfill_interval_seconds)
        self.assertEqual(1, config.danmu.backfill_recent_days)
        self.assertEqual(1, config.danmu.backfill_missing_window_days)
        self.assertEqual(0, config.danmu.duration_tolerance_seconds)

    def test_danmu_backfill_job_registered_when_enabled(self):
        config = AddonsConfig.model_validate(
            {"danmu": {"enabled": True, "backfill_enabled": True, "backfill_interval_seconds": 600}}
        )

        with patch("app.addons.descriptors.danmu_application_service.config", return_value=config.danmu):
            jobs = _danmu_jobs()

        self.assertEqual(1, len(jobs))
        self.assertEqual("danmu.backfill", jobs[0].id)
        self.assertEqual(600, jobs[0].interval_seconds)

    def test_danmu_backfill_job_not_registered_when_disabled(self):
        config = AddonsConfig.model_validate(
            {"danmu": {"enabled": True, "backfill_enabled": False}}
        )

        with patch("app.addons.descriptors.danmu_application_service.config", return_value=config.danmu):
            jobs = _danmu_jobs()

        self.assertEqual([], jobs)

    def test_formatters_emit_xml_and_ass(self):
        comments = [DanmuComment(time_seconds=1.5, text="hello <danmu>")]

        xml = build_xml(comments)
        ass = build_ass(comments)

        self.assertIn("hello &lt;danmu&gt;", xml)
        self.assertIn("[Events]", ass)
        self.assertIn("hello <danmu>", ass)

    def test_formatters_use_configured_size_and_speed(self):
        comments = [DanmuComment(time_seconds=1.0, text="hello", color="#ff0000")]

        xml = build_xml(comments, font_size=60)
        ass = build_ass(comments, font_size=60, font_opacity_percent=80, scroll_duration_seconds=20)

        self.assertIn('p="1.000,1,60,16711680,0,0,0,0"', xml)
        self.assertIn("Style: Danmu,Arial,60,&H33FFFFFF,", ass)
        self.assertIn(",1,2,0,7,30,30,30,1", ass)
        self.assertIn("Dialogue: 0,0:00:01.00,0:00:21.00,Danmu", ass)

    def test_formatters_use_layout_density_for_xml_and_ass(self):
        comments = [DanmuComment(time_seconds=0, text=f"hello {index}") for index in range(20)]

        xml = build_xml(comments, font_size=60, density_percent=20)
        ass = build_ass(comments, font_size=60, density_percent=20)

        self.assertEqual(xml.count("<d "), ass.count("Dialogue:"))
        self.assertLess(xml.count("<d "), len(comments))

    def test_layout_density_is_not_a_direct_percentage_count(self):
        comments = [DanmuComment(time_seconds=float(index), text=f"hello {index}") for index in range(10)]

        xml = build_xml(comments, font_size=60, density_percent=50)

        self.assertNotEqual(5, xml.count("<d "))

    def test_ass_layout_drops_overlapping_same_time_comments(self):
        comments = [DanmuComment(time_seconds=1, text=f"hello {index}") for index in range(20)]

        ass = build_ass(comments, font_size=60, density_percent=100, display_area="top")

        self.assertEqual(6, ass.count("Dialogue:"))

    def test_ass_layout_respects_size_speed_and_display_area_capacity(self):
        comments = [DanmuComment(time_seconds=1, text=f"hello {index}") for index in range(30)]

        top_area = build_ass(comments, font_size=40, density_percent=100, display_area="top")
        full_area = build_ass(comments, font_size=40, density_percent=100, display_area="full")
        larger_font = build_ass(comments, font_size=80, density_percent=100, display_area="top")
        slower_scroll = build_ass(
            [DanmuComment(time_seconds=float(index), text=f"hello {index}") for index in range(30)],
            font_size=60,
            scroll_duration_seconds=35,
            density_percent=20,
            display_area="top",
        )
        faster_scroll = build_ass(
            [DanmuComment(time_seconds=float(index), text=f"hello {index}") for index in range(30)],
            font_size=60,
            scroll_duration_seconds=5,
            density_percent=20,
            display_area="top",
        )

        self.assertGreater(full_area.count("Dialogue:"), top_area.count("Dialogue:"))
        self.assertLess(larger_font.count("Dialogue:"), top_area.count("Dialogue:"))
        self.assertLess(slower_scroll.count("Dialogue:"), faster_scroll.count("Dialogue:"))

    def test_provider_supports_douban_vendor_entries(self):
        self.assertTrue(IqiyiDanmuProvider().supports(Vendor(id="iqiyi", name="Sample", url="http://www.iqiyi.com/v_abc.html")))
        self.assertTrue(BilibiliDanmuProvider().supports(Vendor(id="bilibili", name="Btext", url="https://m.bilibili.com/bangumi/play/ep1")))
        self.assertTrue(YoukuDanmuProvider().supports(Vendor(id="youku", name="Sample", url="http://v.youku.com/v_show/id_abc.html")))
        self.assertTrue(QQDanmuProvider().supports(Vendor(id="qq", name="Sample", url="douban://douban.com/goToWXMiniProgram?path=x?cid=c&vid=v")))

    def test_provider_supports_chinese_only_vendor_names(self):
        self.assertTrue(IqiyiDanmuProvider().supports(Vendor(name="爱奇艺")))
        self.assertTrue(BilibiliDanmuProvider().supports(Vendor(name="哔哩哔哩")))
        self.assertTrue(BilibiliDanmuProvider().supports(Vendor(name="B站")))
        self.assertTrue(YoukuDanmuProvider().supports(Vendor(name="优酷")))
        self.assertTrue(QQDanmuProvider().supports(Vendor(name="腾讯视频")))

    def test_provider_can_fetch_requires_playback_entry(self):
        self.assertTrue(IqiyiDanmuProvider().can_fetch(Vendor(id="iqiyi", name="Sample", url="http://www.iqiyi.com/v_abc.html")))
        self.assertFalse(IqiyiDanmuProvider().can_fetch(Vendor(id="iqiyi", name="Sample", url="https://www.iqiyi.com/")))
        self.assertTrue(BilibiliDanmuProvider().can_fetch(Vendor(id="bilibili", name="Btext", url="https://m.bilibili.com/bangumi/play/ep1")))
        self.assertFalse(BilibiliDanmuProvider().can_fetch(Vendor(id="bilibili", name="Btext", url="https://www.bilibili.com/")))
        self.assertTrue(YoukuDanmuProvider().can_fetch(Vendor(id="youku", name="Sample", url="http://v.youku.com/v_show/id_abc.html")))
        self.assertTrue(
            YoukuDanmuProvider().can_fetch(
                Vendor(
                    id="youku",
                    name="Sample",
                    url="douban://douban.com/goToWXMiniProgram?path=/pages/play/play%3FshowId%3Dshow-1",
                )
            )
        )
        self.assertFalse(YoukuDanmuProvider().can_fetch(Vendor(id="youku", name="Sample", url="https://www.youku.com/")))
        self.assertTrue(
            QQDanmuProvider().can_fetch(
                Vendor(id="qq", name="Sample", url="douban://douban.com/goToWXMiniProgram?path=x?cid=c&vid=v")
            )
        )
        self.assertFalse(QQDanmuProvider().can_fetch(Vendor(id="qq", name="Sample", url="https://v.qq.com/")))

    def test_danmu_service_fetchable_vendor_rejects_platform_homepage(self):
        service = DanmuProviderService()

        self.assertTrue(
            service.has_fetchable_vendor(
                [Vendor(id="youku", name="Sample", url="http://v.youku.com/v_show/id_abc.html")],
                ["youku"],
            )
        )
        self.assertFalse(
            service.has_fetchable_vendor(
                [Vendor(id="youku", name="Sample", url="https://www.youku.com/")],
                ["youku"],
            )
        )

    def test_provider_entry_id_parsers(self):
        self.assertEqual("1lr0jb5ixi8", IqiyiDanmuProvider()._extract_page_id("http://www.iqiyi.com/v_1lr0jb5ixi8.html"))
        self.assertEqual("3561185", BilibiliDanmuProvider()._extract_ep_id("https://m.bilibili.com/bangumi/play/ep3561185"))
        self.assertEqual(
            "show-1",
            extract_youku_show_id("douban://douban.com/goToWXMiniProgram?path=/pages/play/play%3FshowId%3Dshow-1"),
        )
        self.assertEqual("show-2", extract_youku_show_id("https://v.youku.com/v_nextstage/id_show-2.html"))
        self.assertEqual(
            ("mzc002007tp60ap", "w41025my54z"),
            QQDanmuProvider()._extract_ids(
                Vendor(
                    id="qq",
                    name="Sample",
                    url="douban://douban.com/goToWXMiniProgram?path=preload_play/play/index?cid=mzc002007tp60ap&vid=w41025my54z",
                )
            ),
        )

    def test_qq_segment_paths_support_object_and_string_shapes(self):
        provider = QQDanmuProvider()

        paths = provider._segment_paths(
            {
                "segment_index": {
                    "0": {"segment_start": "0", "segment_name": "t/v1/0/30000"},
                    "30000": "t/v1/30000/60000",
                    "60000": {"segment_start": "60000"},
                }
            }
        )

        self.assertEqual(["t/v1/0/30000", "t/v1/30000/60000"], paths)

    def test_qq_segments_include_start_offset(self):
        provider = QQDanmuProvider()

        segments = provider._segments(
            {
                "segment_index": {
                    "0": {"segment_start": "0", "segment_name": "t/v1/0/30000"},
                    "30000": "t/v1/30000/60000",
                }
            }
        )

        self.assertEqual("t/v1/0/30000", segments[0].path)
        self.assertEqual(0, segments[0].start_seconds)
        self.assertEqual("t/v1/30000/60000", segments[1].path)
        self.assertEqual(30, segments[1].start_seconds)
        self.assertEqual(60, provider._segments_duration_seconds(segments))

    def test_qq_json_parser_uses_absolute_time_offset(self):
        comments = parse_qq_json(b'{"barrage_list":[{"time_offset":32000,"content":"hello"}]}')

        self.assertEqual(32, comments[0].time_seconds)

    def test_qq_cover_page_video_ids_can_resolve_episode_vid(self):
        provider = QQDanmuProvider()

        self.assertEqual(
            ["vid-1", "vid-2", "vid-3"],
            provider._extract_video_ids('window.__DATA__={coverInfoMap:{x:{video_ids:["vid-1","vid-2","vid-3"]}}}'),
        )

    def test_qq_cover_page_episode_vid_out_of_range_returns_none(self):
        provider = QQDanmuProvider()

        self.assertEqual(
            [],
            provider._extract_video_ids("window.__DATA__={coverInfoMap:{x:{title:\"Show\"}}}"),
        )

    def test_qq_cover_page_candidate_skips_trailers(self):
        provider = QQDanmuProvider()

        self.assertFalse(
            provider._is_episode_candidate(
                {
                    "title": "3",
                    "unionTitle": "text_03",
                    "playTitle": "text 03text",
                    "duration": "01:20",
                },
                3,
            )
        )
        self.assertTrue(
            provider._is_episode_candidate(
                {
                    "title": "3",
                    "unionTitle": "text_03",
                    "playTitle": "text text03text",
                    "duration": "46:23",
                },
                3,
            )
        )

    def test_qq_candidate_matches_common_chinese_episode_titles(self):
        provider = QQDanmuProvider()

        self.assertTrue(provider._text_matches_episode_number("第01集", 1))
        self.assertTrue(provider._text_matches_episode_number("第1集", 1))
        self.assertTrue(provider._text_matches_episode_number("第01话", 1))

    def test_youku_danmu_parser_uses_text_field_when_content_missing(self):
        class FakeResponse:
            def __init__(self, text: str):
                self.text = text

            def raise_for_status(self):
                return None

        class FakeClient:
            cookies = {"_m_h5_tk": "token_123"}

            async def get(self, *args, **kwargs):
                data_text = kwargs.get("params", {}).get("data", "{}")
                segment = json.loads(data_text).get("mat", 0)
                if segment == 0:
                    return FakeResponse('{"data":{"result":[{"text":"hello","playat":1500}]}}')
                return FakeResponse('{"data":{"result":[]}}')

        provider = YoukuDanmuProvider()

        comments = asyncio.run(provider._fetch_danmu(FakeClient(), "video-1"))

        self.assertEqual("hello", comments[0].text)
        self.assertEqual(1.5, comments[0].time_seconds)

    def test_youku_fetch_danmu_reads_multiple_minute_segments(self):
        class FakeResponse:
            def __init__(self, text: str):
                self.text = text

            def raise_for_status(self):
                return None

        class FakeClient:
            cookies = {"_m_h5_tk": "token_123"}

            async def get(self, *args, **kwargs):
                data_text = kwargs.get("params", {}).get("data", "{}")
                segment = json.loads(data_text).get("mat", 0)
                if segment == 0:
                    return FakeResponse('{"data":{"result":[{"text":"first","playat":1500}]}}')
                if segment == 1:
                    return FakeResponse('{"data":{"result":[{"text":"second","playat":61500}]}}')
                return FakeResponse('{"data":{"result":[]}}')

        provider = YoukuDanmuProvider()

        comments = asyncio.run(provider._fetch_danmu(FakeClient(), "video-1"))

        self.assertEqual(["first", "second"], [comment.text for comment in comments])

    def test_youku_fetch_danmu_reads_after_initial_empty_segments(self):
        class FakeResponse:
            def __init__(self, text: str):
                self.text = text

            def raise_for_status(self):
                return None

        class FakeClient:
            cookies = {"_m_h5_tk": "token_123"}

            def __init__(self):
                self.requested_segments = []

            async def get(self, *args, **kwargs):
                data_text = kwargs.get("params", {}).get("data", "{}")
                segment = json.loads(data_text).get("mat", 0)
                self.requested_segments.append(segment)
                if segment == 6:
                    return FakeResponse('{"data":{"result":[{"text":"late","playat":181500}]}}')
                return FakeResponse('{"data":{"result":[]}}')

        provider = YoukuDanmuProvider()
        provider._max_danmu_segments = 8
        client = FakeClient()

        comments = asyncio.run(provider._fetch_danmu(client, "video-1"))

        self.assertEqual(["late"], [comment.text for comment in comments])
        self.assertEqual(list(range(provider._max_danmu_segments)), sorted(client.requested_segments))

    def test_youku_danmu_parser_reads_nested_result_payload(self):
        provider = YoukuDanmuProvider()
        payload = json.dumps(
            {
                "data": {
                    "result": json.dumps(
                        {"data": {"result": [{"content": "nested", "playat": 2500}]}},
                        ensure_ascii=False,
                    )
                }
            },
            ensure_ascii=False,
        )

        comments = provider._parse_danmu_payload(payload)

        self.assertEqual("nested", comments[0].text)
        self.assertEqual(2.5, comments[0].time_seconds)

    def test_qq_episode_vid_falls_back_to_cover_page_video_ids(self):
        class FakeResponse:
            def __init__(self, *, payload=None, text=""):
                self._payload = payload or {}
                self.text = text

            def raise_for_status(self):
                return None

            def json(self):
                return self._payload

        class FakeClient:
            async def post(self, *args, **kwargs):
                return FakeResponse(payload={"ret": 35013, "msg": "unknow error."})

            async def get(self, *args, **kwargs):
                return FakeResponse(text='window.__DATA__={coverInfoMap:{x:{video_ids:["vid-1","vid-2","vid-3"]}}}')

        provider = QQDanmuProvider()

        with patch.object(
            provider,
            "_fetch_video_page_candidate",
            new=AsyncMock(
                side_effect=[
                    {"title": "1", "playTitle": "Show text01text", "duration": "40:00"},
                    {"title": "2", "playTitle": "Show text02text", "duration": "01:00"},
                    {"title": "2", "playTitle": "Show text02text", "duration": "42:00"},
                ]
            ),
        ):
            result = asyncio.run(provider._resolve_episode_vid(FakeClient(), "cid-1", 2, "vid-1"))

        self.assertEqual("vid-3", result)

    def test_qq_episode_vid_prefers_absolute_episode_for_later_seasons(self):
        class FakeResponse:
            def __init__(self, *, payload=None):
                self._payload = payload or {}

            def raise_for_status(self):
                return None

            def json(self):
                return self._payload

        class FakeClient:
            async def post(self, *args, **kwargs):
                return FakeResponse(payload={
                    "items": [
                        {"item_params": {"vid": "season-1-episode-3", "title": "Show_03"}},
                        {"item_params": {"vid": "season-2-episode-3", "title": "Show_29"}},
                    ]
                })

        provider = QQDanmuProvider()

        result = asyncio.run(
            provider._resolve_episode_vid(
                FakeClient(),
                "cid-1",
                3,
                "fallback",
                absolute_episode_number=29,
                season_number=2,
            )
        )

        self.assertEqual("season-2-episode-3", result)

    def test_bilibili_movie_can_select_direct_episode_without_episode_number(self):
        provider = BilibiliDanmuProvider()
        request = DanmuFetchInput(media_type=MediaType.movie)

        selected = provider._select_episode([{"id": 3561185, "cid": "cid-1"}], "3561185", request)

        self.assertEqual("cid-1", selected["cid"])

    def test_youku_movie_uses_direct_video_id_without_episode_number(self):
        provider = YoukuDanmuProvider()
        request = DanmuFetchInput(media_type=MediaType.movie)

        with patch.object(provider, "_fetch_danmu", new=AsyncMock(return_value=[DanmuComment(time_seconds=1, text="hello")])):
            result = asyncio.run(provider.fetch(Vendor(url="http://v.youku.com/v_show/id_XNDQ1.html"), request))

        self.assertIsNotNone(result)
        self.assertEqual("XNDQ1", result.source_id)

    def test_youku_tv_can_fetch_from_show_id_entry(self):
        provider = YoukuDanmuProvider()
        request = DanmuFetchInput(media_type=MediaType.tv, episode_number=2, episode_count=37)

        with (
            patch.object(provider, "_resolve_show_id", new=AsyncMock()) as resolve_show_mock,
            patch.object(provider, "_resolve_episode_video_id", new=AsyncMock(return_value="episode-video-2")) as resolve_episode_mock,
            patch.object(provider, "_fetch_danmu", new=AsyncMock(return_value=[DanmuComment(time_seconds=1, text="hello")])),
        ):
            result = asyncio.run(
                provider.fetch(
                    Vendor(url="douban://douban.com/goToWXMiniProgram?path=/pages/play/play%3FshowId%3Dshow-1"),
                    request,
                )
            )

        self.assertIsNotNone(result)
        self.assertEqual("episode-video-2", result.source_id)
        resolve_show_mock.assert_not_awaited()
        self.assertEqual("show-1", resolve_episode_mock.await_args.args[1])

    def test_youku_episode_selection_allows_partial_airing_list(self):
        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"videos": [{"id": "episode-video-1"}, {"id": "episode-video-2"}]}

        class FakeClient:
            async def get(self, *args, **kwargs):
                return FakeResponse()

        provider = YoukuDanmuProvider()
        request = DanmuFetchInput(media_type=MediaType.tv, episode_number=2, episode_count=37)

        result = asyncio.run(provider._resolve_episode_video_id(FakeClient(), "show-1", request))

        self.assertEqual("episode-video-2", result)

    def test_youku_tv_still_requires_episode_number(self):
        provider = YoukuDanmuProvider()
        request = DanmuFetchInput(media_type=MediaType.tv)

        with patch.object(provider, "_fetch_danmu", new=AsyncMock(return_value=[DanmuComment(time_seconds=1, text="hello")])) as fetch_mock:
            result = asyncio.run(provider.fetch(Vendor(url="http://v.youku.com/v_show/id_XNDQ1.html"), request))

        self.assertIsNone(result)
        fetch_mock.assert_not_awaited()


class TestDanmuApplicationService(unittest.IsolatedAsyncioTestCase):
    def _media(
        self,
        *,
        media_id: MediaID | None = None,
        media_type: MediaType = MediaType.movie,
        title: str = "Movie",
        year: int = 2026,
        **updates,
    ) -> MediaFullInfo:
        return MediaFullInfo(
            media_id=media_id or MediaID.parse("tmdb:movie:1"),
            media_type=media_type,
            title=title,
            year=year,
            **updates,
        )

    async def test_duration_mismatch_blocks_danmu_generation(self):
        config = AddonsConfig.model_validate({"danmu": {"duration_tolerance_seconds": 60}}).danmu
        result = DanmuFetchResult(
            provider="qq",
            source_id="vid-1",
            source_duration_seconds=2400,
            comments=[DanmuComment(time_seconds=1, text="hello")],
        )

        with patch.object(danmu_duration_guard, "probe_video_duration_seconds", new=AsyncMock(return_value=2780)):
            self.assertTrue(await danmu_duration_guard.has_duration_mismatch(Path("/library/E01.mkv"), result, config))

    async def test_duration_match_allows_danmu_generation(self):
        config = AddonsConfig.model_validate({"danmu": {"duration_tolerance_seconds": 60}}).danmu
        result = DanmuFetchResult(
            provider="qq",
            source_id="vid-1",
            source_duration_seconds=2730,
            comments=[DanmuComment(time_seconds=1, text="hello")],
        )

        with patch.object(danmu_duration_guard, "probe_video_duration_seconds", new=AsyncMock(return_value=2780)):
            self.assertFalse(await danmu_duration_guard.has_duration_mismatch(Path("/library/E01.mkv"), result, config))

    async def test_duration_check_is_skipped_without_probe_or_source_duration(self):
        config = AddonsConfig.model_validate({"danmu": {"duration_tolerance_seconds": 60}}).danmu
        result = DanmuFetchResult(
            provider="qq",
            source_id="vid-1",
            source_duration_seconds=None,
            comments=[DanmuComment(time_seconds=1, text="hello")],
        )

        with patch.object(danmu_duration_guard, "probe_video_duration_seconds", new=AsyncMock(return_value=2780)):
            self.assertFalse(await danmu_duration_guard.has_duration_mismatch(Path("/library/E01.mkv"), result, config))

    async def test_remove_outputs_deletes_existing_sidecars(self):
        config = AddonsConfig.model_validate({"danmu": {"output_xml": True, "output_ass": True}}).danmu
        with TemporaryDirectory() as tmp_dir:
            video_path = Path(tmp_dir) / "E01.mkv"
            video_path.write_text("video")
            xml_path = sidecar_path(video_path, "xml")
            ass_path = sidecar_path(video_path, "ass")
            xml_path.write_text("xml")
            ass_path.write_text("ass")

            remove_outputs(video_path, config)

            self.assertFalse(xml_path.exists())
            self.assertFalse(ass_path.exists())

    async def test_refresh_media_server_after_sidecar_generation(self):
        service = DanmuApplicationService()
        media_id = MediaID.parse("tmdb:movie:1")
        media = self._media(
            media_id=media_id,
            media_type=MediaType.movie,
            title="Movie",
            year=2026,
        )

        with (
            patch("app.services.application.workflows.danmu.service.refresh_media_server", new=AsyncMock()) as refresh_mock,
        ):
            await service._refresh_media_server(media, Path("/library/Movie/Movie.mkv"))

        refreshed_media = refresh_mock.await_args.args[0]
        self.assertEqual(refreshed_media.media_id, media_id)
        self.assertEqual(refreshed_media.title, "Movie")
        refresh_mock.assert_awaited_once_with(refreshed_media, "/library/Movie/Movie.mkv")

    async def test_refresh_media_server_failure_does_not_raise(self):
        service = DanmuApplicationService()
        media_id = MediaID.parse("tmdb:movie:1")
        media = self._media(
            media_id=media_id,
            media_type=MediaType.movie,
            title="Movie",
            year=2026,
        )

        with patch("app.services.application.workflows.danmu.service.refresh_media_server", new=AsyncMock(side_effect=RuntimeError("boom"))):
            await service._refresh_media_server(media, Path("/library/Movie/Movie.mkv"))

    async def test_manual_generation_reuses_current_command_action(self):
        service = DanmuApplicationService()
        media = self._media()

        with (
            action_context("command-action-1"),
            patch.object(service, "_create_action", return_value=SimpleNamespace(id="addon-action-1")) as create_mock,
        ):
            action_id, owns_action = service._resolve_generation_action(
                event=None,
                trigger=ActionTrigger.manual,
                media=media,
                video_path="/library/Movie/Movie.mkv",
                episode_number=None,
            )

        self.assertEqual("command-action-1", action_id)
        self.assertFalse(owns_action)
        create_mock.assert_not_called()

    async def test_non_command_generation_creates_addon_action(self):
        service = DanmuApplicationService()
        media = self._media()

        with patch.object(service, "_create_action", return_value=SimpleNamespace(id="addon-action-1")) as create_mock:
            action_id, owns_action = service._resolve_generation_action(
                event=None,
                trigger=ActionTrigger.scheduler,
                media=media,
                video_path="/library/Movie/Movie.mkv",
                episode_number=None,
            )

        self.assertEqual("addon-action-1", action_id)
        self.assertTrue(owns_action)
        create_mock.assert_called_once()

    async def test_import_event_generation_passes_library_file_for_artifacts(self):
        service = DanmuApplicationService()
        config = AddonsConfig.model_validate({"danmu": {"enabled": True, "directory_ids": ["dir-1"]}}).danmu
        media_id = MediaID.parse("tmdb:movie:1")
        media = self._media(
            media_id=media_id,
            vendors=[Vendor(id="youku", name="Youku", url="http://v.youku.com/v_show/id_XNDQ1.html")],
        )

        with TemporaryDirectory() as tmp_dir:
            video_path = Path(tmp_dir) / "Movie.mkv"
            video_path.write_text("video")
            library_file = LibraryFile(
                id="file-1",
                task_id="task-1",
                directory_id="dir-1",
                media_id=media_id,
                path=str(video_path.parent),
                file_name=video_path.name,
                file_size=1,
                created_at=1,
            )
            event = Event(
                type=EventType.MEDIA_IMPORT_COMPLETED,
                meta=MediaImportCompletedEventMeta(
                    task_id="task-1",
                    directory_id="dir-1",
                    media_id=media_id,
                    file_path=str(video_path),
                    imported_files=[ImportedMediaFile(destination_path=str(video_path), episode_number=None)],
                ).model_dump_json(),
            )

            with (
                patch.object(service, "config", return_value=config),
                patch.object(service, "_generate_for_video", new=AsyncMock(return_value=False)) as generate_mock,
                patch(
                    "app.services.application.workflows.danmu.service.danmu_source_resolver.media_with_fetchable_source",
                    new=AsyncMock(return_value=media),
                ),
                patch("app.services.domain.library.service.library_service.get_files_by_task", new=AsyncMock(return_value=[library_file])),
            ):
                await service.handle_event(event)

        generate_mock.assert_awaited_once()
        self.assertEqual(library_file, generate_mock.await_args.kwargs["library_file"])

    async def test_backfill_policy_generates_when_recent_configured_sidecar_missing(self):
        service = DanmuApplicationService()
        config = AddonsConfig.model_validate({"danmu": {"output_xml": True, "output_ass": True}}).danmu
        media_id = MediaID.parse("tmdb:movie:1")
        media = self._media(
            media_id=media_id,
            media_type=MediaType.movie,
            title="Movie",
            year=2026,
            release_date=date.today().isoformat(),
        )
        library_file = LibraryFile(
            id="file-1",
            task_id="task-1",
            directory_id="dir-1",
            media_id=media_id,
            path="/library/Movie",
            file_name="Movie.mkv",
            file_size=1,
            created_at=1,
        )
        with TemporaryDirectory() as tmp_dir:
            video_path = Path(tmp_dir) / "Movie.mkv"
            video_path.write_text("video")
            sidecar_path(video_path, "xml").write_text("xml")

            self.assertTrue(service._should_backfill_video(media, library_file, video_path, config))

    async def test_backfill_policy_ignores_old_missing_sidecars_without_skipped_artifacts(self):
        service = DanmuApplicationService()
        config = AddonsConfig.model_validate({"danmu": {"output_xml": True, "output_ass": True, "backfill_recent_days": 30}}).danmu
        media_id = MediaID.parse("tmdb:movie:1")
        media = self._media(
            media_id=media_id,
            media_type=MediaType.movie,
            title="Movie",
            year=2026,
            release_date="2020-01-01",
        )
        library_file = LibraryFile(
            id="file-1",
            task_id="task-1",
            directory_id="dir-1",
            media_id=media_id,
            path="/library/Movie",
            file_name="Movie.mkv",
            file_size=1,
            created_at=1,
        )
        with TemporaryDirectory() as tmp_dir:
            video_path = Path(tmp_dir) / "Movie.mkv"
            video_path.write_text("video")

            self.assertFalse(service._should_backfill_video(media, library_file, video_path, config))

    async def test_backfill_policy_does_not_retry_old_files_with_skipped_danmu_artifacts(self):
        service = DanmuApplicationService()
        config = AddonsConfig.model_validate({"danmu": {"output_xml": True, "output_ass": True, "backfill_recent_days": 30}}).danmu
        media_id = MediaID.parse("tmdb:movie:1")
        media = self._media(
            media_id=media_id,
            media_type=MediaType.movie,
            title="Movie",
            year=2026,
            release_date="2020-01-01",
        )
        library_file = LibraryFile(
            id="file-1",
            task_id="task-1",
            directory_id="dir-1",
            media_id=media_id,
            path="/library/Movie",
            file_name="Movie.mkv",
            file_size=1,
            created_at=1,
        )
        with TemporaryDirectory() as tmp_dir:
            video_path = Path(tmp_dir) / "Movie.mkv"
            video_path.write_text("video")
            artifacts = [
                LibraryFileArtifact(
                    id="artifact-xml",
                    library_file_id=library_file.id,
                    artifact_type=LibraryFileArtifactType.danmu_xml,
                    expected_path=str(sidecar_path(video_path, "xml")),
                    status=LibraryFileArtifactStatus.skipped,
                    created_at=1,
                    updated_at=1,
                ),
                LibraryFileArtifact(
                    id="artifact-ass",
                    library_file_id=library_file.id,
                    artifact_type=LibraryFileArtifactType.danmu_ass,
                    expected_path=str(sidecar_path(video_path, "ass")),
                    status=LibraryFileArtifactStatus.skipped,
                    created_at=1,
                    updated_at=1,
                ),
            ]

            self.assertFalse(service._should_backfill_video(media, library_file, video_path, config, artifacts=artifacts))

    async def test_backfill_policy_does_not_refresh_recent_watchable_media_with_existing_sidecars(self):
        service = DanmuApplicationService()
        config = AddonsConfig.model_validate({"danmu": {"output_xml": True, "output_ass": True, "backfill_recent_days": 30}}).danmu
        media_id = MediaID.parse("tmdb:movie:1")
        media = self._media(
            media_id=media_id,
            media_type=MediaType.movie,
            title="Movie",
            year=2026,
            digital_release_date=date.today().isoformat(),
        )
        library_file = LibraryFile(
            id="file-1",
            task_id="task-1",
            directory_id="dir-1",
            media_id=media_id,
            path="/library/Movie",
            file_name="Movie.mkv",
            file_size=1,
            created_at=1,
        )
        with TemporaryDirectory() as tmp_dir:
            video_path = Path(tmp_dir) / "Movie.mkv"
            video_path.write_text("video")
            sidecar_path(video_path, "xml").write_text("xml")
            sidecar_path(video_path, "ass").write_text("ass")

            self.assertFalse(service._should_backfill_video(media, library_file, video_path, config))

    async def test_backfill_reuses_media_info_per_media_id(self):
        service = DanmuApplicationService()
        config = AddonsConfig.model_validate(
            {"danmu": {"enabled": True, "backfill_enabled": True, "directory_ids": ["dir-1"]}}
        ).danmu
        media_id = MediaID.parse("tmdb:movie:1")
        media = self._media(
            media_id=media_id,
            release_date=date.today().isoformat(),
            vendors=[Vendor(id="youku", name="Youku", url="http://v.youku.com/v_show/id_XNDQ1.html")],
        )

        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            first = root / "Movie.CD1.mkv"
            second = root / "Movie.CD2.mkv"
            first.write_text("video")
            second.write_text("video")
            files = [
                LibraryFile(
                    id="file-1",
                    task_id="task-1",
                    directory_id="dir-1",
                    media_id=media_id,
                    path=str(root),
                    file_name=first.name,
                    file_size=1,
                    created_at=1,
                ),
                LibraryFile(
                    id="file-2",
                    task_id="task-1",
                    directory_id="dir-1",
                    media_id=media_id,
                    path=str(root),
                    file_name=second.name,
                    file_size=1,
                    created_at=1,
                ),
            ]
            info_mock = AsyncMock(return_value=media)

            with (
                patch.object(service, "config", return_value=config),
                patch.object(service, "_generate_for_video", new=AsyncMock(return_value=True)) as generate_mock,
                patch("app.services.application.workflows.danmu.service.danmu_source_resolver.media_with_fetchable_source", info_mock),
                patch("app.services.domain.library.service.library_service.list_files", new=AsyncMock(return_value=files)),
                patch("app.services.domain.library.service.library_service.is_primary_file", return_value=True),
            ):
                await service.run_backfill()

        info_mock.assert_awaited_once_with(media_id, season_number=None, config=config)
        self.assertEqual(2, generate_mock.await_count)
