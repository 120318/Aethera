from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.schemas.domain.media_types import MediaType
from app.schemas.domain.vendor import Vendor
from app.services.integration.danmu.episode_matching import DanmuEpisodeMatcher
from app.services.integration.danmu.models import DanmuComment, DanmuEpisodeCandidate, DanmuFetchInput
from app.services.integration.danmu.providers.bilibili import BilibiliDanmuProvider
from app.services.integration.danmu.providers.iqiyi import IqiyiDanmuProvider
from app.services.integration.danmu.providers.qq import QQDanmuProvider
from app.services.integration.danmu.providers.youku import YoukuDanmuProvider


def _platform_card(platform, video_id, title, order):
    if platform == "qq":
        return {"vid": video_id, "cid": "season-4", "title": title, "duration": "3600"}
    if platform == "iqiyi":
        return {"tvId": video_id, "name": title, "shortTitle": title, "order": order}
    if platform == "youku":
        return {"id": video_id, "title": title, "seq": str(order)}
    return {"id": order, "cid": video_id, "title": str(order), "long_title": title, "duration": 3600000}


class _CatalogClient:
    def __init__(self, cards):
        self.cards = cards

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, url, **kwargs):
        request = httpx.Request("GET", url)
        if "baseinfo" in url:
            return httpx.Response(200, json={"data": {"albumId": "album", "videoCount": len(self.cards)}}, request=request)
        if "avlistinfo" in url:
            return httpx.Response(200, json={"data": {"epsodelist": self.cards}}, request=request)
        if "shows/videos" in url:
            return httpx.Response(200, json={"videos": self.cards}, request=request)
        if "pgc/view" in url:
            return httpx.Response(200, json={"result": {"episodes": self.cards}}, request=request)
        if "list.so" in url:
            return httpx.Response(200, content=b'<i><d p="1,1,25,16777215,0,0,0,0">hello</d></i>', request=request)
        if "barrage/base" in url:
            return httpx.Response(200, json={"segment_index": {"0": {"segment_name": "segment"}}}, request=request)
        if "barrage/segment" in url:
            return httpx.Response(200, json={"barrage_list": [{"time_offset": 1000, "content": "hello"}]}, request=request)
        raise AssertionError(url)

    async def post(self, url, **kwargs):
        if "universal_backend_service" in url:
            return httpx.Response(200, json={"ret": 35013}, request=httpx.Request("POST", url))
        return httpx.Response(200, json={"ret": 0, "data": {"cards": [
            {"params": {"title": "第4季", "page_context": "cid=season-4"}},
            *[{"params": card} for card in self.cards],
        ]}}, request=httpx.Request("POST", url))


async def _fetch(platform, cards, episode, episode_count):
    providers = {"qq": QQDanmuProvider, "iqiyi": IqiyiDanmuProvider, "youku": YoukuDanmuProvider, "bilibili": BilibiliDanmuProvider}
    urls = {
        "qq": "https://v.qq.com/x/cover/season-4/intro.html",
        "iqiyi": "https://www.iqiyi.com/v_1.html",
        "youku": "douban://douban.com/goToWXMiniProgram?path=/pages/play/play%3FshowId%3Dshow-1",
        "bilibili": "https://m.bilibili.com/bangumi/play/ep1",
    }
    provider = providers[platform]()
    comments = [DanmuComment(time_seconds=1, text="hello")]
    with (
        patch(f"app.services.integration.danmu.providers.{platform}.httpx.AsyncClient", return_value=_CatalogClient(cards)),
        patch.object(IqiyiDanmuProvider, "_fetch_segments", AsyncMock(return_value=comments)),
        patch.object(YoukuDanmuProvider, "_fetch_danmu", AsyncMock(return_value=comments)),
    ):
        return await provider.fetch(
            Vendor(id=platform, url=urls[platform]),
            DanmuFetchInput(media_type=MediaType.tv, episode_number=episode, episode_count=episode_count, season_number=4),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("platform", ["qq", "iqiyi", "youku", "bilibili"])
async def test_all_providers_resolve_eleventh_regular_video_from_scrambled_split_issues(platform):
    regular = [
        _platform_card(platform, str(1000 + number), f"第{(number + 1) // 2}期{part}：正文", number)
        for number, part in enumerate(["上", "下"] * 6, 1)
    ]
    cards = [
        _platform_card(platform, "intro", "先导片上：出发", 99),
        _platform_card(platform, "bonus", "第6期加更：游戏", 98),
        _platform_card(platform, "featurette", "第1期上：花絮", 97),
        *reversed(regular), regular[0],
    ]
    result = await _fetch(platform, cards, 11, 25)
    assert result is not None
    assert result.source_id == "1011"
    assert result.provider == platform


@pytest.mark.asyncio
@pytest.mark.parametrize("platform", ["qq", "iqiyi", "youku", "bilibili"])
async def test_all_providers_allow_partial_airing_catalog(platform):
    cards = [_platform_card(platform, "1001", "第1集", 1), _platform_card(platform, "1002", "第2集", 2)]
    result = await _fetch(platform, cards, 2, 37)
    assert result is not None
    assert result.source_id == "1002"


@pytest.mark.asyncio
@pytest.mark.parametrize("platform", ["qq", "iqiyi", "youku", "bilibili"])
async def test_all_providers_reject_incomplete_variety_sequence(platform):
    cards = [_platform_card(platform, "1003", "第2期上：正文", 3)]
    assert await _fetch(platform, cards, 1, 25) is None


def test_ordered_catalog_filters_extras_and_deduplicates_before_counting():
    candidates = [
        DanmuEpisodeCandidate(external_id="intro", titles=["先导片"], sequence_index=0),
        DanmuEpisodeCandidate(external_id="first", titles=["Opening"], sequence_index=1),
        DanmuEpisodeCandidate(external_id="extra", titles=["加更"], sequence_index=2),
        DanmuEpisodeCandidate(external_id="second", titles=["Journey"], sequence_index=3),
        DanmuEpisodeCandidate(external_id="first", titles=["Opening"], sequence_index=4),
    ]
    matcher = DanmuEpisodeMatcher()
    assert matcher.select(candidates, 1).candidate.external_id == "first"
    assert matcher.select(candidates, 2).candidate.external_id == "second"
    assert matcher.select(candidates, 3).candidate is None


def test_unordered_unlabelled_catalog_is_not_treated_as_a_regular_video_sequence():
    candidates = [DanmuEpisodeCandidate(external_id="unknown", titles=["Opening"])]
    assert DanmuEpisodeMatcher().select(candidates, 1).candidate is None


def test_authoritative_catalog_order_is_independent_of_displayed_global_episode_numbers():
    candidates = [
        DanmuEpisodeCandidate(external_id="second", titles=["第80集"], sequence_index=80),
        DanmuEpisodeCandidate(external_id="first", titles=["第79集"], sequence_index=79),
    ]
    matcher = DanmuEpisodeMatcher()
    assert matcher.select(candidates, 1).candidate.external_id == "first"
    assert matcher.select(candidates, 2).candidate.external_id == "second"


@pytest.mark.asyncio
@pytest.mark.parametrize("platform", ["iqiyi", "youku", "bilibili"])
async def test_ordered_providers_filter_extras_before_counting_videos_without_issue_labels(platform):
    first = _platform_card(platform, "first", "Opening", 79)
    extra = _platform_card(platform, "extra", "花絮", 80)
    second = _platform_card(platform, "second", "Journey", 81)
    result = await _fetch(platform, [second, extra, first, first], 2, 25)
    assert result is not None
    assert result.source_id == "second"


def test_numbered_catalog_keeps_episode_identity_when_earlier_episodes_are_missing():
    candidates = [DanmuEpisodeCandidate(external_id="third", titles=["第3集"])]
    matcher = DanmuEpisodeMatcher()
    assert matcher.select(candidates, 1).candidate is None
    assert matcher.select(candidates, 3).candidate.external_id == "third"


def test_one_video_cannot_represent_two_numbered_episodes():
    candidates = [
        DanmuEpisodeCandidate(external_id="same", episode_number=1),
        DanmuEpisodeCandidate(external_id="same", episode_number=2),
    ]
    assert DanmuEpisodeMatcher().select(candidates, 1).candidate is None
