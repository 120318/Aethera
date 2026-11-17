from unittest.mock import AsyncMock, patch
from types import SimpleNamespace

import httpx
import pytest

from app.services.integration.danmu.providers.qq import QQDanmuProvider


def _card(title, video_id, *, cid="season-4", duration="3600", is_trailer="0"):
    return {"params": {
        "title": title, "vid": video_id, "cid": cid,
        "duration": duration, "is_trailer": is_trailer,
    }}


def _season_page(cards):
    return {"cards": [{"params": {
        "title": "第4季", "page_context": "cid=season-4",
    }}, *cards]}


def _legacy_client(payload):
    response = httpx.Response(200, json=payload, request=httpx.Request("POST", "https://example.test/episodes"))
    return SimpleNamespace(post=AsyncMock(return_value=response))


@pytest.mark.asyncio
async def test_qq_regular_video_ordinals_ignore_extras_order_and_duplicates():
    regular = [
        _card(f"第{issue}期{part}：正文", f"issue-{issue}-{part}")
        for issue in range(1, 7)
        for part in ("上", "下")
    ]
    cards = [
        _card("先导片上：出发", "intro"),
        _card("第6期加更：游戏", "extra"),
        _card("第6期还有加更：游戏", "another-extra"),
        _card("第6期 加更：游戏", "spaced-extra"),
        _card("第6期 上 加更：游戏", "spaced-upper-extra"),
        _card("第1期上：预告", "trailer", is_trailer="1"),
        _card("第1期上：片段", "clip", duration="90"),
        _card("第1期上：其他季", "other-season", cid="season-3"),
        *reversed(regular),
        regular[0],
    ]
    provider = QQDanmuProvider()
    with patch.object(provider, "_fetch_vector_page", AsyncMock(return_value=_season_page(cards))):
        for ordinal, card in enumerate(regular, 1):
            result = await provider._resolve_episode_vid_from_vector_page(
                None, "season-4", ordinal, "intro",
                absolute_episode_number=ordinal + 70, season_number=4,
            )
            assert result.video_id == card["params"]["vid"]
        result = await provider._resolve_episode_vid_from_vector_page(
            None, "season-4", 13, "intro", absolute_episode_number=83, season_number=4,
        )
        assert result.video_id is None
        assert result.has_regular_episodes


@pytest.mark.asyncio
@pytest.mark.parametrize("titles,expected", [
    (["第1期：正文", "第2期：正文"], ["v1", "v2"]),
    (["第1期上：正文", "第1期中：正文", "第1期下：正文"], ["v1", "v2", "v3"]),
    (["第1期（上）：正文", "第1期（下）：正文"], ["v1", "v2"]),
    (["第1期：正文", "第2期上：正文"], ["v1", "v2"]),
    (["第1期：正文", "第2期上：正文", "第2期中：正文"], ["v1", "v2", "v3"]),
])
async def test_qq_counts_actual_regular_parts_without_assuming_two_per_issue(titles, expected):
    provider = QQDanmuProvider()
    cards = [_card(title, f"v{number}") for number, title in enumerate(titles, 1)]
    with patch.object(provider, "_fetch_vector_page", AsyncMock(return_value=_season_page(list(reversed(cards))))):
        for ordinal, video_id in enumerate(expected, 1):
            result = await provider._resolve_episode_vid_from_vector_page(
                None, "season-4", ordinal, None, season_number=4,
            )
            assert result.video_id == video_id


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["title", "play_title", "union_title", "c_title_output"])
@pytest.mark.parametrize("keyword", ["预告", "花絮", "片花", "彩蛋", "先导片", "加更"])
@pytest.mark.parametrize("duration", ["3600", ""])
async def test_qq_long_or_unknown_duration_extras_in_any_title_do_not_conflict_with_regular_video(field, keyword, duration):
    extra = _card("第1期上：节目", "extra", duration=duration)
    extra["params"][field] = f"第1期上：{keyword}"
    cards = [extra, _card("第1期上：正文", "upper"), _card("第1期下：正文", "lower")]
    provider = QQDanmuProvider()
    with patch.object(provider, "_fetch_vector_page", AsyncMock(return_value=_season_page(cards))):
        result = await provider._resolve_episode_vid_from_vector_page(
            None, "season-4", 1, None, season_number=4,
        )
    assert result.video_id == "upper"


@pytest.mark.asyncio
@pytest.mark.parametrize("cards", [
    [_card("第2期上：正文", "v2")],
    [_card("第1期：正文", "v1"), _card("第3期：正文", "v3")],
    [_card("第1期下：正文", "v1")],
    [_card("第1期上：正文", "v1"), _card("第2期上：正文", "v2")],
    [_card("第1期上：正文", "v1"), _card("第1期上：另一版本", "v2")],
    [_card("第1期：完整版", "v1"), _card("第1期上：正文", "v2")],
    [_card("第1期上：正文", "v1"), _card("第1期下：正文", "v1")],
])
async def test_qq_does_not_renumber_incomplete_or_ambiguous_regular_lists(cards):
    provider = QQDanmuProvider()
    with patch.object(provider, "_fetch_vector_page", AsyncMock(return_value=_season_page(cards))):
        result = await provider._resolve_episode_vid_from_vector_page(
            None, "season-4", 1, None, season_number=4,
        )
        assert result.video_id is None
        assert result.has_regular_episodes


@pytest.mark.asyncio
async def test_qq_legacy_regular_list_uses_video_ordinal_instead_of_absolute_episode():
    payload = {"items": [
        {"item_params": _card("第1期下：正文", "lower")["params"]},
        {"item_params": _card("第1期上：正文", "upper")["params"]},
    ]}
    result = await QQDanmuProvider()._resolve_episode_vid(
        _legacy_client(payload), "season-4", 2, "intro", absolute_episode_number=72, season_number=1,
    )
    assert result == "lower"


@pytest.mark.asyncio
async def test_qq_incomplete_legacy_list_falls_back_to_complete_vector_list():
    legacy = {"items": [{"item_params": _card("第2期上：正文", "third")["params"]}]}
    cards = [
        _card("第1期上：正文", "first"),
        _card("第1期下：正文", "second"),
        _card("第2期上：正文", "third"),
    ]
    provider = QQDanmuProvider()
    with patch.object(provider, "_fetch_vector_page", AsyncMock(return_value=_season_page(cards))):
        assert await provider._resolve_episode_vid(
            _legacy_client(legacy), "season-4", 1, "intro", absolute_episode_number=71, season_number=4,
        ) == "first"


@pytest.mark.asyncio
async def test_qq_incomplete_regular_list_never_falls_back_to_intro_for_episode_one():
    provider = QQDanmuProvider()
    cards = [_card("第2期上：正文", "third")]
    with (
        patch.object(provider, "_fetch_vector_page", AsyncMock(return_value=_season_page(cards))),
        patch.object(provider, "_resolve_episode_vid_from_cover_page", AsyncMock()) as cover,
    ):
        assert await provider._resolve_episode_vid(
            _legacy_client({}), "season-4", 1, "intro", season_number=1,
        ) is None
    cover.assert_not_awaited()


@pytest.mark.asyncio
async def test_qq_later_season_regular_videos_require_verified_season_cid():
    legacy = {"items": [{"item_params": _card("第1期：正文", "legacy-first-season")["params"]}]}
    provider = QQDanmuProvider()
    with patch.object(provider, "_fetch_vector_page", AsyncMock(return_value={"cards": []})):
        assert await provider._resolve_episode_vid(
            _legacy_client(legacy), "season-4", 1, "intro", absolute_episode_number=71, season_number=4,
        ) is None
