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
            assert result.candidate.external_id == card["params"]["vid"]
        result = await provider._resolve_episode_vid_from_vector_page(
            None, "season-4", 13, "intro", absolute_episode_number=83, season_number=4,
        )
        assert result.candidate is None
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
            assert result.candidate.external_id == video_id


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
    assert result.candidate.external_id == "upper"


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
        assert result.candidate is None
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


@pytest.mark.asyncio
async def test_qq_catalog_with_only_extras_does_not_reuse_an_unverified_intro():
    provider = QQDanmuProvider()
    cards = [_card("先导片上：出发", "intro")]
    with (
        patch.object(provider, "_fetch_vector_page", AsyncMock(return_value=_season_page(cards))),
        patch.object(provider, "_resolve_episode_vid_from_cover_page", AsyncMock(return_value=None)),
    ):
        assert await provider._resolve_episode_vid(
            _legacy_client({}), "season-4", 1, "intro", season_number=1,
        ) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("foreign_cid", ["other-album", ""])
@pytest.mark.parametrize("include_target", [False, True])
async def test_qq_legacy_issue_sequence_only_uses_videos_verified_in_the_target_album(foreign_cid, include_target):
    items = [
        {"item_params": _card("第1期上：正文", "foreign-upper", cid=foreign_cid)["params"]},
        {"item_params": _card("第1期下：正文", "foreign-lower", cid=foreign_cid)["params"]},
    ]
    if include_target:
        items.extend([
            {"item_params": _card("第1期上：正文", "target-upper")["params"]},
            {"item_params": _card("第1期下：正文", "target-lower")["params"]},
        ])
    provider = QQDanmuProvider()
    with (
        patch.object(provider, "_fetch_vector_page", AsyncMock(return_value={})),
        patch.object(provider, "_resolve_episode_vid_from_cover_page", AsyncMock(return_value=None)),
    ):
        result = await provider._resolve_episode_vid(
            _legacy_client({"items": items}), "season-4", 1, "intro", season_number=1,
        )
    assert result == ("target-upper" if include_target else None)


@pytest.mark.asyncio
async def test_qq_legacy_numbered_candidates_allow_missing_cid_but_exclude_foreign_albums():
    unscoped = _card("第3集", "unscoped")["params"]
    unscoped.pop("cid")
    items = [
        {"item_params": _card("第3集", "foreign", cid="other-album")["params"]},
        {"item_params": unscoped},
    ]
    assert await QQDanmuProvider()._resolve_episode_vid(
        _legacy_client({"items": items}), "season-4", 3, "intro",
    ) == "unscoped"


@pytest.mark.asyncio
@pytest.mark.parametrize("target_first", [False, True])
@pytest.mark.parametrize("error", [httpx.ReadTimeout("unrelated page"), httpx.HTTPError("unrelated page")])
async def test_qq_cover_numbered_match_is_independent_of_unrelated_page_failures(target_first, error):
    ids = ["target", "broken"] if target_first else ["broken", "target"]
    response = httpx.Response(
        200, text='video_ids:[' + ','.join(f'"{vid}"' for vid in ids) + ']',
        request=httpx.Request("GET", "https://example.test/cover"),
    )
    client = SimpleNamespace(get=AsyncMock(return_value=response))
    target = {"title": "第1集", "duration": "3600"}
    results = [target, error] if target_first else [error, target]
    provider = QQDanmuProvider()
    with patch.object(provider, "_fetch_video_page_candidate", AsyncMock(side_effect=results)) as fetch:
        assert await provider._resolve_episode_vid_from_cover_page(client, "album", 1, "intro") == "target"
    assert fetch.await_count == (1 if target_first else 2)


@pytest.mark.asyncio
async def test_qq_cover_variety_match_collects_regular_parts_despite_an_unrelated_page_failure():
    response = httpx.Response(
        200, text='video_ids:["broken","upper","lower"]',
        request=httpx.Request("GET", "https://example.test/cover"),
    )
    client = SimpleNamespace(get=AsyncMock(return_value=response))
    provider = QQDanmuProvider()
    with patch.object(provider, "_fetch_video_page_candidate", AsyncMock(side_effect=[
        httpx.ReadTimeout("unrelated page"),
        {"title": "第1期上：正文", "duration": "3600"},
        {"title": "第1期下：正文", "duration": "3600"},
    ])) as fetch:
        assert await provider._resolve_episode_vid_from_cover_page(client, "album", 2, "intro") == "lower"
    assert fetch.await_count == 3
