import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest

pytestmark = [pytest.mark.drift, pytest.mark.health]

os.environ.setdefault("DATA_PATH", f"/tmp/aethera-test-data-{uuid.uuid4()}")

from app.schemas.config import SchedulerConfig
from app.schemas.domain.download import TaskContext, TaskData, TaskStatus
from app.schemas.domain.library import LibraryFile
from app.schemas.domain.media import EpisodeInfo, MediaExecutionSnapshot, MediaFullInfo, MediaSeasonInfo
from app.schemas.domain.media_subscription_state import MediaSubscriptionState
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.resource_attributes import ResourceAttributes
from app.schemas.domain.resource_search import MediaSearchQuery, Resource, ResourceSearchResult
from app.schemas.domain.subscription import Subscription
from app.schemas.domain.subscription_filters import SubscriptionFilters, UpgradePolicy
from app.schemas.domain.torrent import TorrentFileItem, TorrentMetadata, TorrentPayload
from app.schemas.media_id import MediaID
from app.schemas.domain.subscription_run_result import SubscriptionRunResponse
from app.schemas.runtime.subscription_runtime import SubscriptionPlanningStatus, SubscriptionRunPlan, SubscriptionRunPlanningResult
from app.services.domain.download import download_service
from app.services.domain.resource.selection import ResourceSelectionPlan, partition_search_results, select_resources
from app.services.application.workflows.resource_search import resource_search_service
from app.services.application.workflows.subscription.run import SubscriptionRunApplicationService
from app.services.domain.subscription.resource_run_plan_service import resource_run_plan_service


@asynccontextmanager
async def _acquired_scheduler_lock():
    yield True


def _subscription() -> Subscription:
    return Subscription(
        sub_id="sub-1",
        media_id=MediaID.parse("tmdb:tv:1"),
        media=_media(),
        season_number=1,
        sites=["site-a"],
        filters=None,
        directory_id="dir-1",
        filter_config_id=None,
        followed=True,
        active=True,
    )


def _media(
    *,
    imdb_id: str | None = "tt1234567",
    season_number: int = 1,
    episodes_count: int = 4,
    aired_episode_count: int = 0,
    next_episode_to_air: EpisodeInfo | None = None,
) -> MediaExecutionSnapshot:
    return MediaExecutionSnapshot(
        media_id=MediaID.parse("tmdb:tv:1"),
        title="Test Show",
        year=2024,
        media_type=MediaType.tv,
        season_number=season_number,
        episodes_count=episodes_count,
        imdb_id=imdb_id,
        aired_episode_count=aired_episode_count,
        next_episode_to_air=next_episode_to_air,
    )


def _future_date(days: int = 7) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def _full_media(*, imdb_id: str | None = "tt1234567", season_number: int = 1, episodes_count: int = 4) -> MediaFullInfo:
    return MediaFullInfo(
        media_id=MediaID.parse("tmdb:tv:1"),
        title="Test Show",
        year=2024,
        media_type=MediaType.tv,
        season_number=season_number,
        episodes_count=episodes_count,
        imdb_id=imdb_id,
        seasons=[MediaSeasonInfo(season_number=season_number, episode_count=episodes_count)],
    )


def _task_with_metadata(metadata: TorrentMetadata) -> TaskData:
    media = _media()
    return TaskData(
        id="task-1",
        media_id=media.media_id,
        torrent_hash=metadata.hash,
        status=TaskStatus.DOWNLOADING,
        context=TaskContext(download_url="https://example.com/torrent", media=media, directory_id="dir-1", parsed_attributes=metadata.attrs),
        metadata=metadata,
    )


def _disc_metadata(number: int, total: int = 2) -> TorrentMetadata:
    title = f"Show.S01.Disc.{number}.of.{total}"
    return TorrentMetadata(
        hash=f"hash-{number}",
        name=title,
        size=1,
        files=[],
        attrs=ResourceAttributes(
            title=title,
            seasons=[1],
            episodes=[],
            sources=["BluRay"],
            resource_form="BluRay Disc",
            resource_form_evidence="torrent_structure",
            disc_number=number,
            disc_total=total,
        ),
        coverage_kind="disc_package",
    )


def _disc_resource(title: str, seeders: int = 10) -> Resource:
    return Resource(
        resources=ResourceSearchResult(
            id=title,
            title=title,
            site="test",
            category="tv",
            size="1 GB",
            seeders=seeders,
            leechers=0,
            publish_date=datetime.now(UTC),
            download_url=f"https://example.com/{title}",
            result_id=title,
            matched_by_id=True,
        ),
        attrs=ResourceAttributes(title=title, seasons=[1], episodes=[], sources=["BluRay"], resource_form="BluRay Disc"),
    )


def _video_resource(title: str, episodes: list[int], seeders: int = 10) -> Resource:
    return Resource(
        resources=ResourceSearchResult(
            id=title,
            title=title,
            site="test",
            category="tv",
            size="1 GB",
            seeders=seeders,
            leechers=0,
            publish_date=datetime.now(UTC),
            download_url=f"https://example.com/{title}",
            result_id=title,
            matched_by_id=True,
        ),
        attrs=ResourceAttributes(title=title, seasons=[1], episodes=episodes, sources=["WEB-DL"], resource_form="Video File"),
    )


def _video_metadata(title: str, episodes: list[int]) -> TorrentMetadata:
    return TorrentMetadata(
        hash=f"hash-{title}",
        name=title,
        size=1,
        files=[
            TorrentFileItem(
                index=0,
                filename=f"{title}.mkv",
                size=1,
                attrs=ResourceAttributes(title=title, seasons=[1], episodes=episodes, sources=["WEB-DL"], resource_form="Video File"),
            )
        ],
        attrs=ResourceAttributes(title=title, seasons=[1], episodes=episodes, sources=["WEB-DL"], resource_form="Video File"),
        coverage_kind="exact_episodes",
    )


@pytest.mark.asyncio
async def test_subscription_sweep_uses_recent_feed_strategy_by_default(monkeypatch):
    service = SubscriptionRunApplicationService()
    search_run = AsyncMock(return_value=object())
    rss_run = AsyncMock(return_value=object())
    monkeypatch.setattr(service, "_acquire_subscription_sweep", lambda: _acquired_scheduler_lock())
    monkeypatch.setattr(service, "_run_all_with_search", search_run)
    monkeypatch.setattr(service, "_run_all_with_recent_feed", rss_run)
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.settings_service.get_scheduler_config",
        lambda: SchedulerConfig(),
    )

    await service.run_all()

    rss_run.assert_awaited_once()
    search_run.assert_not_awaited()


@pytest.mark.asyncio
async def test_subscription_sweep_uses_recent_feed_first_when_rss_mode_starts(monkeypatch):
    service = SubscriptionRunApplicationService()
    search_run = AsyncMock(return_value=object())
    rss_run = AsyncMock(return_value=object())
    monkeypatch.setattr(service, "_acquire_subscription_sweep", lambda: _acquired_scheduler_lock())
    monkeypatch.setattr(service, "_run_all_with_search", search_run)
    monkeypatch.setattr(service, "_run_all_with_recent_feed", rss_run)
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.settings_service.get_scheduler_config",
        lambda: SchedulerConfig(
            subscription_resource_discovery_mode="rss_with_search_backfill",
            subscription_search_backfill_interval_seconds=3600,
        ),
    )

    await service.run_all()

    rss_run.assert_awaited_once()
    search_run.assert_not_awaited()


@pytest.mark.asyncio
async def test_search_sweep_only_runs_due_subscriptions(monkeypatch):
    service = SubscriptionRunApplicationService()
    now = time.time()
    due_state = MediaSubscriptionState(sub_id="due", media_id=MediaID.parse("tmdb:tv:1"), media=_media(), active=True, last_search_at=now - 1200)
    fresh_state = MediaSubscriptionState(sub_id="fresh", media_id=MediaID.parse("tmdb:tv:2"), media=_media(), active=True, last_search_at=now)
    run_one = AsyncMock(return_value=SubscriptionRunResponse(checked=1, added=1))
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.subscription_query_service.list_states",
        AsyncMock(return_value=[due_state, fresh_state]),
    )
    monkeypatch.setattr(service, "_build_runtime_subscription", AsyncMock(return_value=_subscription()))
    monkeypatch.setattr(service, "run_one", run_one)

    result = await service._run_all_with_search(SchedulerConfig(subscription_search_interval_seconds=600))

    assert result.checked == 1
    assert result.added == 1
    run_one.assert_awaited_once()
    assert run_one.await_args.kwargs["active_search"] is True


@pytest.mark.asyncio
async def test_search_sweep_limits_due_subscriptions_per_sweep(monkeypatch):
    service = SubscriptionRunApplicationService()
    now = time.time()
    older_state = MediaSubscriptionState(
        sub_id="older",
        media_id=MediaID.parse("tmdb:tv:1"),
        media=_media(),
        active=True,
        last_search_at=now - 7200,
    )
    newer_state = MediaSubscriptionState(
        sub_id="newer",
        media_id=MediaID.parse("tmdb:tv:2"),
        media=_media(),
        active=True,
        last_search_at=now - 3600,
    )
    built_subs = {
        "older": _subscription().model_copy(update={"sub_id": "older"}),
        "newer": _subscription().model_copy(update={"sub_id": "newer"}),
    }
    run_one = AsyncMock(return_value=SubscriptionRunResponse(checked=1, added=0))
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.subscription_query_service.list_states",
        AsyncMock(return_value=[newer_state, older_state]),
    )
    monkeypatch.setattr(service, "_build_runtime_subscription", AsyncMock(side_effect=lambda state: built_subs[state.sub_id]))
    monkeypatch.setattr(service, "run_one", run_one)

    await service._run_all_with_search(
        SchedulerConfig(
            subscription_search_interval_seconds=600,
            subscription_search_max_per_sweep=1,
        )
    )

    run_one.assert_awaited_once()
    assert run_one.await_args.args[0].sub_id == "older"
    assert run_one.await_args.kwargs["active_search"] is True


@pytest.mark.asyncio
async def test_search_sweep_runs_new_subscriptions_immediately(monkeypatch):
    service = SubscriptionRunApplicationService()
    state = MediaSubscriptionState(sub_id="new", media_id=MediaID.parse("tmdb:tv:1"), media=_media(), active=True)
    run_one = AsyncMock(return_value=SubscriptionRunResponse(checked=1, added=0))
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.subscription_query_service.list_states",
        AsyncMock(return_value=[state]),
    )
    monkeypatch.setattr(service, "_build_runtime_subscription", AsyncMock(return_value=_subscription()))
    monkeypatch.setattr(service, "run_one", run_one)

    await service._run_all_with_search(SchedulerConfig(subscription_search_interval_seconds=600))

    run_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_search_sweep_skips_due_search_when_future_episode_is_not_aired_and_targets_are_satisfied(monkeypatch):
    service = SubscriptionRunApplicationService()
    now = time.time()
    media = _media(
        aired_episode_count=2,
        next_episode_to_air=EpisodeInfo(season_number=1, episode_number=3, air_date=_future_date()),
    )
    state = MediaSubscriptionState(sub_id="future", media_id=MediaID.parse("tmdb:tv:1"), media=media, active=True, last_search_at=now - 7200)
    run_one = AsyncMock(return_value=SubscriptionRunResponse(checked=1, added=0))
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.subscription_query_service.list_states",
        AsyncMock(return_value=[state]),
    )
    monkeypatch.setattr(service, "_build_runtime_subscription", AsyncMock(return_value=_subscription().model_copy(update={"media": media})))
    monkeypatch.setattr(service, "_refresh_runtime_media_snapshot", AsyncMock(return_value=_subscription().model_copy(update={"media": media})))
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.resource_run_plan_service.build_subscription_plan",
        AsyncMock(return_value=SubscriptionRunPlanningResult(status=SubscriptionPlanningStatus.SATISFIED)),
    )
    monkeypatch.setattr(service, "run_one", run_one)

    result = await service._run_all_with_search(SchedulerConfig(subscription_search_interval_seconds=600))

    assert result.checked == 0
    assert result.added == 0
    run_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_search_sweep_keeps_due_search_when_future_episode_exists_but_aired_targets_are_missing(monkeypatch):
    service = SubscriptionRunApplicationService()
    now = time.time()
    media = _media(
        aired_episode_count=2,
        next_episode_to_air=EpisodeInfo(season_number=1, episode_number=3, air_date=_future_date()),
    )
    state = MediaSubscriptionState(sub_id="missing", media_id=MediaID.parse("tmdb:tv:1"), media=media, active=True, last_search_at=now - 7200)
    plan = SubscriptionRunPlan(
        sub_id="missing",
        media=media,
        season_number=1,
        correlation_id="corr",
        target_episodes={2},
    )
    run_one = AsyncMock(return_value=SubscriptionRunResponse(checked=1, added=0))
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.subscription_query_service.list_states",
        AsyncMock(return_value=[state]),
    )
    monkeypatch.setattr(service, "_build_runtime_subscription", AsyncMock(return_value=_subscription().model_copy(update={"sub_id": "missing", "media": media})))
    monkeypatch.setattr(service, "_refresh_runtime_media_snapshot", AsyncMock(return_value=_subscription().model_copy(update={"sub_id": "missing", "media": media})))
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.resource_run_plan_service.build_subscription_plan",
        AsyncMock(return_value=SubscriptionRunPlanningResult(status=SubscriptionPlanningStatus.READY, plan=plan)),
    )
    monkeypatch.setattr(service, "run_one", run_one)

    await service._run_all_with_search(SchedulerConfig(subscription_search_interval_seconds=600))

    run_one.assert_awaited_once()
    assert run_one.await_args.kwargs["active_search"] is True


@pytest.mark.asyncio
async def test_rss_sweep_uses_recent_feed_and_limits_due_searches(monkeypatch):
    service = SubscriptionRunApplicationService()
    now = time.time()
    fresh_state = MediaSubscriptionState(sub_id="fresh", media_id=MediaID.parse("tmdb:tv:1"), media=_media(), active=True, last_search_at=now)
    older_due_state = MediaSubscriptionState(sub_id="older-due", media_id=MediaID.parse("tmdb:tv:2"), media=_media(), active=True, last_search_at=now - 7200)
    newer_due_state = MediaSubscriptionState(sub_id="newer-due", media_id=MediaID.parse("tmdb:tv:3"), media=_media(), active=True, last_search_at=now - 3700)
    recent_candidate = ResourceSearchResult(
        id="recent-1",
        title="Test Show S01E01",
        site="site-a",
        category="tv",
        size="1 GB",
        seeders=1,
        leechers=0,
        publish_date=datetime.now(UTC),
        download_url="https://example.com/recent-1",
        result_id="recent-1",
    )
    built_subs = {
        "fresh": _subscription().model_copy(update={"sub_id": "fresh"}),
        "older-due": _subscription().model_copy(update={"sub_id": "older-due"}),
        "newer-due": _subscription().model_copy(update={"sub_id": "newer-due"}),
    }
    run_one = AsyncMock(return_value=SubscriptionRunResponse(checked=1, added=0))
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.subscription_query_service.list_states",
        AsyncMock(return_value=[fresh_state, newer_due_state, older_due_state]),
    )
    monkeypatch.setattr(service, "_fetch_recent_candidates_for_sweep", AsyncMock(return_value=[recent_candidate]))
    monkeypatch.setattr(service, "_build_runtime_subscription", AsyncMock(side_effect=lambda state: built_subs[state.sub_id]))
    monkeypatch.setattr(service, "run_one", run_one)

    await service._run_all_with_recent_feed(
        SchedulerConfig(
            subscription_search_backfill_interval_seconds=3600,
            subscription_search_max_per_sweep=1,
        )
    )

    assert run_one.await_count == 3
    first_call, second_call, third_call = run_one.await_args_list
    assert first_call.args[0].sub_id == "fresh"
    assert first_call.kwargs["recent_candidates"] == [recent_candidate]
    assert first_call.kwargs["active_search"] is False
    assert second_call.args[0].sub_id == "newer-due"
    assert second_call.kwargs["recent_candidates"] == [recent_candidate]
    assert second_call.kwargs["active_search"] is False
    assert third_call.args[0].sub_id == "older-due"
    assert third_call.kwargs["active_search"] is True
    assert "recent_candidates" not in third_call.kwargs


def test_recent_candidates_are_filtered_by_media_title_and_sites():
    service = SubscriptionRunApplicationService()
    media = _media(episodes_count=4, aired_episode_count=4)
    plan = SubscriptionRunPlan(
        sub_id="sub-1",
        media=media,
        season_number=1,
        correlation_id="corr-1",
        episode_mode=True,
        sites=["indexer-a::site-a"],
        filters=None,
        quality_profile=None,
        target_episodes={1},
        required_scores={},
        existing_disc_numbers=set(),
    )
    query = MediaSearchQuery(media=media, indexers=plan.sites)
    candidates = [
        ResourceSearchResult(
            id="match-title",
            title="Test Show S01E01 1080p WEB-DL",
            site="indexer-a::site-a",
            category="tv",
            size="1 GB",
            seeders=10,
            leechers=0,
            publish_date=datetime.now(UTC),
            download_url="https://example.com/match",
            result_id="match-title",
            matched_by_id=False,
        ),
        ResourceSearchResult(
            id="wrong-title",
            title="Other Show S01E01 1080p WEB-DL",
            site="indexer-a::site-a",
            category="tv",
            size="1 GB",
            seeders=10,
            leechers=0,
            publish_date=datetime.now(UTC),
            download_url="https://example.com/wrong-title",
            result_id="wrong-title",
            matched_by_id=False,
        ),
        ResourceSearchResult(
            id="wrong-site",
            title="Test Show S01E01 1080p WEB-DL",
            site="indexer-a::site-b",
            category="tv",
            size="1 GB",
            seeders=10,
            leechers=0,
            publish_date=datetime.now(UTC),
            download_url="https://example.com/wrong-site",
            result_id="wrong-site",
            matched_by_id=False,
        ),
    ]

    results = service._filter_recent_candidates(query=query, plan=plan, candidates=candidates)

    assert [result.id for result in results] == ["match-title"]
    assert results[0].result_id != "match-title"
    cached_result = resource_search_service.get_by_result_id(results[0].result_id)
    assert cached_result is not None
    assert cached_result.title == "Test Show S01E01 1080p WEB-DL"


def test_recent_candidates_do_not_match_loose_single_word_titles():
    service = SubscriptionRunApplicationService()
    media = _media(episodes_count=1, aired_episode_count=1).model_copy(update={"title": "It", "imdb_id": None})
    plan = SubscriptionRunPlan(
        sub_id="sub-1",
        media=media,
        season_number=1,
        correlation_id="corr-1",
        episode_mode=True,
        sites=None,
        filters=None,
        quality_profile=None,
        target_episodes={1},
        required_scores={},
        existing_disc_numbers=set(),
    )
    query = MediaSearchQuery(media=media)
    candidates = [
        ResourceSearchResult(
            id="wrong-substring",
            title="Interstellar 2014 1080p WEB-DL",
            site="site-a",
            category="movie",
            size="1 GB",
            seeders=10,
            leechers=0,
            publish_date=datetime.now(UTC),
            download_url="https://example.com/wrong-substring",
            result_id="wrong-substring",
            matched_by_id=False,
        ),
        ResourceSearchResult(
            id="wrong-middle-token",
            title="Before It Ends 2026 1080p WEB-DL",
            site="site-a",
            category="movie",
            size="1 GB",
            seeders=10,
            leechers=0,
            publish_date=datetime.now(UTC),
            download_url="https://example.com/wrong-middle-token",
            result_id="wrong-middle-token",
            matched_by_id=False,
        ),
        ResourceSearchResult(
            id="right-prefixed-token",
            title="[GROUP] It 2017 1080p WEB-DL",
            site="site-a",
            category="movie",
            size="1 GB",
            seeders=10,
            leechers=0,
            publish_date=datetime.now(UTC),
            download_url="https://example.com/right-prefixed-token",
            result_id="right-prefixed-token",
            matched_by_id=False,
        ),
        ResourceSearchResult(
            id="right-prefix-token",
            title="It 2017 1080p WEB-DL",
            site="site-a",
            category="movie",
            size="1 GB",
            seeders=10,
            leechers=0,
            publish_date=datetime.now(UTC),
            download_url="https://example.com/right-prefix-token",
            result_id="right-prefix-token",
            matched_by_id=False,
        ),
    ]

    results = service._filter_recent_candidates(query=query, plan=plan, candidates=candidates)

    assert [result.title for result in results] == ["[GROUP] It 2017 1080p WEB-DL", "It 2017 1080p WEB-DL"]


def test_active_search_due_ignores_last_run_when_never_searched():
    service = SubscriptionRunApplicationService()
    state = MediaSubscriptionState(
        sub_id="new",
        media_id=MediaID.parse("tmdb:tv:1"),
        media=_media(),
        active=True,
        last_run_at=time.time(),
        last_search_at=None,
    )

    assert service._active_search_due(state, 3600) is True


@pytest.mark.asyncio
async def test_compute_target_episodes_excludes_present_and_downloading_episodes(monkeypatch):
    service = SubscriptionRunApplicationService()
    sub = _subscription()
    media = _media(episodes_count=5)

    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.library_service.get_present_episodes",
        AsyncMock(return_value={1, 3}),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.download_service.list_active_episodes_by_media",
        AsyncMock(return_value={4}),
    )

    plan = ((await resource_run_plan_service.build_subscription_plan(sub.model_copy(update={"media": media}))).plan)

    assert plan is not None
    assert plan.target_episodes == {2, 5}
    assert plan.required_scores == {}


def test_tv_disc_package_task_does_not_fallback_to_episode_one():
    season, episodes = download_service.resolve_task_episode_coverage(_task_with_metadata(_disc_metadata(1)))

    assert season == 1
    assert episodes == []


def test_task_episode_coverage_uses_task_media_context_season_when_parser_has_no_season():
    metadata = TorrentMetadata(
        hash="hash-no-season",
        name="Show.Episode.01",
        size=1,
        files=[],
        attrs=ResourceAttributes(title="Show.Episode.01"),
    )
    task = _task_with_metadata(metadata)
    task.context.media = task.context.media.model_copy(update={"season_number": 2})

    season, episodes = download_service.resolve_task_episode_coverage(task)

    assert season == 2
    assert episodes == [1]


def test_task_episode_coverage_only_counts_selected_files():
    metadata = TorrentMetadata(
        hash="hash-partial",
        name="Show.S01E01-E05",
        size=5,
        files=[
            TorrentFileItem(
                index=index,
                filename=f"Show.S01E{episode:02d}.mkv",
                size=1,
                attrs=ResourceAttributes(title="Show", seasons=[1], episodes=[episode], sources=["WEB-DL"], resource_form="Video File"),
            )
            for index, episode in enumerate(range(1, 6))
        ],
        attrs=ResourceAttributes(title="Show", seasons=[1], episodes=list(range(1, 6)), sources=["WEB-DL"], resource_form="Video File"),
        coverage_kind="exact_episodes",
    )
    task = _task_with_metadata(metadata)
    task.context.selected_files = [0, 1, 2]

    season, episodes = download_service.resolve_task_episode_coverage(task)

    assert season == 1
    assert episodes == [1, 2, 3]


@pytest.mark.asyncio
async def test_disc_package_subscription_skips_existing_disc_number(monkeypatch):
    resources = [_disc_resource("Show.S01.Disc.1.of.2", seeders=30), _disc_resource("Show.S01.Disc.2.of.2", seeders=20)]
    payloads = {
        "Show.S01.Disc.1.of.2": TorrentPayload(metadata=_disc_metadata(1), blob=b"one"),
        "Show.S01.Disc.2.of.2": TorrentPayload(metadata=_disc_metadata(2), blob=b"two"),
    }

    async def fake_fetch_payload(result):
        return payloads[result.title]

    monkeypatch.setattr(
        "app.services.domain.resource.selection.fetch_torrent_payload",
        fake_fetch_payload,
    )

    selected = await select_resources(
        resources,
        episodes={1, 2, 3},
        filters=SubscriptionFilters(resource_kind=["original_disc"], resource_form=["BluRay Disc"]),
        episode_mode=True,
        existing_disc_numbers={1},
    )

    assert len(selected) == 1
    assert selected[0][2].resources.title == "Show.S01.Disc.2.of.2"
    assert selected[0][1] == []


def test_disc_package_subscription_partition_bypasses_title_episode_filter(monkeypatch):
    media = _media(episodes_count=3)
    search_result = ResourceSearchResult(
        id="disc-1",
        title="Show.S01.BluRay.Disc1",
        site="test",
        category="tv",
        size="1 GB",
        seeders=10,
        leechers=0,
        publish_date=datetime.now(UTC),
        download_url="https://example.com/disc-1",
        result_id="disc-1",
        matched_by_id=True,
    )
    monkeypatch.setattr(
        "app.services.domain.resource.selection.resource_parser.parse",
        lambda _title, desc="": ResourceAttributes(
            title="Show.S01.BluRay.Disc1",
            seasons=[1],
            episodes=[1],
            sources=["BluRay"],
            resource_form="BluRay Disc",
        ),
    )
    plan = ResourceSelectionPlan(
        media_id=media.media_id,
        season_number=1,
        episode_mode=True,
        filters=SubscriptionFilters(resource_kind=["original_disc"], resource_form=["BluRay Disc"]),
        target_episodes={2, 3},
    )

    standard_results, unmatched_results, has_any_id_match = partition_search_results(
        plan,
        [search_result],
        unmatched_rules=[],
    )

    assert [item.resources.title for item in standard_results] == ["Show.S01.BluRay.Disc1"]
    assert unmatched_results == []
    assert has_any_id_match is True


def test_disc_package_subscription_partition_keeps_metadata_only_candidates(monkeypatch):
    media = _media(episodes_count=3)
    search_result = ResourceSearchResult(
        id="maybe-disc",
        title="Show.S01.1080p.BluRay",
        site="test",
        category="tv",
        size="1 GB",
        seeders=10,
        leechers=0,
        publish_date=datetime.now(UTC),
        download_url="https://example.com/maybe-disc",
        result_id="maybe-disc",
        matched_by_id=True,
    )
    monkeypatch.setattr(
        "app.services.domain.resource.selection.resource_parser.parse",
        lambda _title, desc="": ResourceAttributes(
            title="Show.S01.1080p.BluRay",
            seasons=[1],
            episodes=[1],
            sources=["BluRay"],
            resource_form="Video File",
        ),
    )
    plan = ResourceSelectionPlan(
        media_id=media.media_id,
        season_number=1,
        episode_mode=True,
        filters=SubscriptionFilters(resource_kind=["original_disc"], resource_form=["BluRay Disc"]),
        target_episodes={2, 3},
    )

    standard_results, unmatched_results, has_any_id_match = partition_search_results(
        plan,
        [search_result],
        unmatched_rules=[],
    )

    assert [item.resources.title for item in standard_results] == ["Show.S01.1080p.BluRay"]
    assert unmatched_results == []
    assert has_any_id_match is True


def test_partition_uses_description_episode_when_title_has_no_episode():
    media = _media(episodes_count=12)
    search_result = ResourceSearchResult(
        id="desc-episode",
        title="爱情没有神话.2160p.WEB-DL.H265",
        description="爱情没有神话 第11集 | 类型：剧情 爱情 | 主演：唐嫣 赵又廷",
        site="test",
        category="tv",
        size="1 GB",
        seeders=10,
        leechers=0,
        publish_date=datetime.now(UTC),
        download_url="https://example.com/desc-episode",
        result_id="desc-episode",
        matched_by_id=True,
    )
    plan = ResourceSelectionPlan(
        media_id=media.media_id,
        season_number=1,
        episode_mode=True,
        filters=SubscriptionFilters(resource_kind=["video_file"]),
        target_episodes={11},
    )

    standard_results, unmatched_results, has_any_id_match = partition_search_results(
        plan,
        [search_result],
        unmatched_rules=[],
    )

    assert [item.resources.title for item in standard_results] == ["爱情没有神话.2160p.WEB-DL.H265"]
    assert standard_results[0].attrs.episodes == [11]
    assert unmatched_results == []
    assert has_any_id_match is True


@pytest.mark.asyncio
async def test_default_subscription_category_excludes_original_disc(monkeypatch):
    resources = [_disc_resource("Show.S01.Disc.1.of.2", seeders=50), _video_resource("Show.S01E01.1080p.WEB-DL", [1], seeders=20)]
    payloads = {
        "Show.S01.Disc.1.of.2": TorrentPayload(metadata=_disc_metadata(1), blob=b"disc"),
        "Show.S01E01.1080p.WEB-DL": TorrentPayload(metadata=_video_metadata("Show.S01E01.1080p.WEB-DL", [1]), blob=b"video"),
    }

    async def fake_fetch_payload(result):
        return payloads[result.title]

    monkeypatch.setattr(
        "app.services.domain.resource.selection.fetch_torrent_payload",
        fake_fetch_payload,
    )

    selected = await select_resources(
        resources,
        episodes={1},
        filters=SubscriptionFilters(),
        episode_mode=True,
    )

    assert len(selected) == 1
    assert selected[0][2].resources.title == "Show.S01E01.1080p.WEB-DL"


@pytest.mark.asyncio
async def test_select_resources_continues_after_known_candidate_payload_misses_targets(monkeypatch):
    stale_pack = _video_resource("Show.S01.2160p.WEB-DL", [45, 46, 47, 48, 49, 50, 51, 52], seeders=50)
    episode_45 = _video_resource("Show.S01E45.2160p.WEB-DL", [45], seeders=20)
    payloads = {
        stale_pack.resources.title: TorrentPayload(
            metadata=TorrentMetadata(
                hash="hash-stale",
                name=stale_pack.resources.title,
                size=40,
                files=[
                    TorrentFileItem(
                        index=index,
                        filename=f"Show.S01E{episode:02d}.mkv",
                        size=1,
                        attrs=ResourceAttributes(
                            title=f"Show.S01E{episode:02d}",
                            seasons=[1],
                            episodes=[episode],
                            sources=["WEB-DL"],
                            resource_form="Video File",
                        ),
                    )
                    for index, episode in enumerate(range(1, 41))
                ],
                attrs=ResourceAttributes(
                    title=stale_pack.resources.title,
                    seasons=[1],
                    episodes=list(range(1, 41)),
                    sources=["WEB-DL"],
                    resource_form="Video File",
                ),
                coverage_kind="exact_episodes",
            ),
            blob=b"stale",
        ),
        episode_45.resources.title: TorrentPayload(metadata=_video_metadata(episode_45.resources.title, [45]), blob=b"episode"),
    }

    async def fake_fetch_payload(result):
        return payloads[result.title]

    monkeypatch.setattr(
        "app.services.domain.resource.selection.fetch_torrent_payload",
        fake_fetch_payload,
    )

    selected = await select_resources(
        [stale_pack, episode_45],
        episodes={45},
        filters=SubscriptionFilters(resource_kind=["video_file"]),
        episode_mode=True,
    )

    assert len(selected) == 1
    assert selected[0][2].resources.title == episode_45.resources.title
    assert selected[0][1] == [0]


@pytest.mark.asyncio
async def test_original_disc_category_only_selects_disc_package(monkeypatch):
    resources = [_disc_resource("Show.S01.Disc.1.of.1", seeders=20), _video_resource("Show.S01E01.1080p.WEB-DL", [1], seeders=50)]
    payloads = {
        "Show.S01.Disc.1.of.1": TorrentPayload(metadata=_disc_metadata(1, total=1), blob=b"disc"),
        "Show.S01E01.1080p.WEB-DL": TorrentPayload(metadata=_video_metadata("Show.S01E01.1080p.WEB-DL", [1]), blob=b"video"),
    }

    async def fake_fetch_payload(result):
        return payloads[result.title]

    monkeypatch.setattr(
        "app.services.domain.resource.selection.fetch_torrent_payload",
        fake_fetch_payload,
    )

    selected = await select_resources(
        resources,
        episodes={1},
        filters=SubscriptionFilters(resource_kind=["original_disc"]),
        episode_mode=True,
    )

    assert len(selected) == 1
    assert selected[0][2].resources.title == "Show.S01.Disc.1.of.1"
    assert selected[0][1] == []


@pytest.mark.asyncio
async def test_combined_resource_categories_select_video_and_disc(monkeypatch):
    resources = [_disc_resource("Show.S01.Disc.1.of.1", seeders=20), _video_resource("Show.S01E01.1080p.WEB-DL", [1], seeders=50)]
    payloads = {
        "Show.S01.Disc.1.of.1": TorrentPayload(metadata=_disc_metadata(1, total=1), blob=b"disc"),
        "Show.S01E01.1080p.WEB-DL": TorrentPayload(metadata=_video_metadata("Show.S01E01.1080p.WEB-DL", [1]), blob=b"video"),
    }

    async def fake_fetch_payload(result):
        return payloads[result.title]

    monkeypatch.setattr(
        "app.services.domain.resource.selection.fetch_torrent_payload",
        fake_fetch_payload,
    )

    selected = await select_resources(
        resources,
        episodes={1},
        filters=SubscriptionFilters(resource_kind=["video_file", "original_disc"]),
        episode_mode=True,
    )

    assert [item[2].resources.title for item in selected] == ["Show.S01E01.1080p.WEB-DL", "Show.S01.Disc.1.of.1"]


@pytest.mark.asyncio
async def test_compute_target_episodes_researches_present_tv_episodes_below_target_filters(monkeypatch):
    service = SubscriptionRunApplicationService()
    sub = _subscription()
    sub.filters = SubscriptionFilters(upgrade_policy=UpgradePolicy(enabled=True))
    sub.target_filters = SubscriptionFilters(resolution=["2160p"])
    media = _media(episodes_count=3)

    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.library_service.get_present_episodes",
        AsyncMock(return_value={1, 2}),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.download_service.list_active_episodes_by_media",
        AsyncMock(return_value=set()),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.library_service.get_episode_attributes",
        AsyncMock(return_value={
            1: [ResourceAttributes(resolution="1080p")],
            2: [ResourceAttributes(resolution="2160p")],
        }),
    )

    plan = ((await resource_run_plan_service.build_subscription_plan(sub.model_copy(update={"media": media}))).plan)

    assert plan is not None
    assert plan.target_episodes == {1, 3}
    assert plan.required_scores == {}


@pytest.mark.asyncio
async def test_disc_package_run_plan_continues_when_video_episodes_complete(monkeypatch):
    service = SubscriptionRunApplicationService()
    sub = _subscription()
    sub.filters = SubscriptionFilters(resource_kind=["original_disc"], resource_form=["BluRay Disc"])
    media = _media(episodes_count=3)

    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.library_service.get_present_episodes",
        AsyncMock(return_value={1, 2, 3}),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.download_service.list_active_episodes_by_media",
        AsyncMock(return_value=set()),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.download_service.get_tasks",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.library_service.get_files_by_media",
        AsyncMock(return_value=[]),
    )

    sub = sub.model_copy(update={"media": media, "season_number": media.season_number})
    plan = ((await resource_run_plan_service.build_subscription_plan(sub)).plan)

    assert plan is not None
    assert plan.target_episodes == set()
    assert plan.existing_disc_numbers == set()


@pytest.mark.asyncio
async def test_disc_package_run_plan_stops_when_season_package_exists(monkeypatch):
    service = SubscriptionRunApplicationService()
    sub = _subscription()
    sub.filters = SubscriptionFilters(resource_kind=["original_disc"], resource_form=["BluRay Disc"])
    media = _media(episodes_count=3)
    metadata = _disc_metadata(1, total=1).model_copy(update={"coverage_kind": "season_package"})

    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.library_service.get_present_episodes",
        AsyncMock(return_value={1, 2, 3}),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.download_service.list_active_episodes_by_media",
        AsyncMock(return_value=set()),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.download_service.get_tasks",
        AsyncMock(return_value=[_task_with_metadata(metadata)]),
    )

    sub = sub.model_copy(update={"media": media, "season_number": media.season_number})
    plan = ((await resource_run_plan_service.build_subscription_plan(sub)).plan)

    assert plan is None


@pytest.mark.asyncio
async def test_disc_package_run_plan_uses_library_disc_numbers_after_task_deleted(monkeypatch):
    service = SubscriptionRunApplicationService()
    sub = _subscription()
    sub.filters = SubscriptionFilters(resource_kind=["original_disc"], resource_form=["BluRay Disc"])
    media = _media(episodes_count=3)
    library_disc = LibraryFile(
        id="disc-1-file",
        task_id="deleted-task",
        directory_id="dir-1",
        media_id=sub.media_id,
        path="Shows/Test/Season 01/Package/Disc 1/BDMV",
        file_name="index.bdmv",
        file_size=1,
        created_at=0,
        resource_attributes=ResourceAttributes(
            seasons=[1],
            episodes=[],
            resource_form="BluRay Disc",
            package_layout="BDMV",
            disc_number=1,
            disc_total=2,
        ),
    )

    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.library_service.get_present_episodes",
        AsyncMock(return_value={1, 2, 3}),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.download_service.list_active_episodes_by_media",
        AsyncMock(return_value=set()),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.download_service.get_tasks",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.library_service.get_files_by_media",
        AsyncMock(return_value=[library_disc]),
    )

    sub = sub.model_copy(update={"media": media, "season_number": media.season_number})
    plan = ((await resource_run_plan_service.build_subscription_plan(sub)).plan)

    assert plan is not None
    assert plan.existing_disc_numbers == {1}


@pytest.mark.asyncio
async def test_disc_package_run_plan_stops_when_library_season_package_exists(monkeypatch):
    service = SubscriptionRunApplicationService()
    sub = _subscription()
    sub.filters = SubscriptionFilters(resource_kind=["original_disc"], resource_form=["BluRay Disc"])
    media = _media(episodes_count=3)
    library_package = LibraryFile(
        id="season-package-file",
        task_id="deleted-task",
        directory_id="dir-1",
        media_id=sub.media_id,
        path="Shows/Test/Season 01/Season.Package/BDMV",
        file_name="index.bdmv",
        file_size=1,
        created_at=0,
        resource_attributes=ResourceAttributes(
            seasons=[1],
            episodes=[],
            resource_form="BluRay Disc",
            package_layout="BDMV",
        ),
    )

    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.library_service.get_present_episodes",
        AsyncMock(return_value={1, 2, 3}),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.download_service.list_active_episodes_by_media",
        AsyncMock(return_value=set()),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.download_service.get_tasks",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.library_service.get_files_by_media",
        AsyncMock(return_value=[library_package]),
    )

    sub = sub.model_copy(update={"media": media, "season_number": media.season_number})
    plan = ((await resource_run_plan_service.build_subscription_plan(sub)).plan)

    assert plan is None


@pytest.mark.asyncio
async def test_disc_package_run_plan_ignores_existing_package_that_mismatches_filters(monkeypatch):
    service = SubscriptionRunApplicationService()
    sub = _subscription()
    sub.filters = SubscriptionFilters(resource_kind=["original_disc"], resource_form=["DVD Disc"])
    media = _media(episodes_count=3)
    library_package = LibraryFile(
        id="season-package-file",
        task_id="deleted-task",
        directory_id="dir-1",
        media_id=sub.media_id,
        path="Shows/Test/Season 01/Season.Package/BDMV",
        file_name="index.bdmv",
        file_size=1,
        created_at=0,
        resource_attributes=ResourceAttributes(
            seasons=[1],
            episodes=[],
            resource_form="BluRay Disc",
            package_layout="BDMV",
        ),
    )

    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.library_service.get_present_episodes",
        AsyncMock(return_value={1, 2, 3}),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.download_service.list_active_episodes_by_media",
        AsyncMock(return_value=set()),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.download_service.get_tasks",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.library_service.get_files_by_media",
        AsyncMock(return_value=[library_package]),
    )

    sub = sub.model_copy(update={"media": media, "season_number": media.season_number})
    plan = ((await resource_run_plan_service.build_subscription_plan(sub)).plan)

    assert plan is not None
    assert plan.existing_disc_numbers == set()


@pytest.mark.asyncio
async def test_compute_target_episodes_researches_library_movie_below_target_filters(monkeypatch):
    service = SubscriptionRunApplicationService()
    sub = Subscription(
        sub_id="sub-movie",
        media_id=MediaID.parse("tmdb:movie:1"),
        media=MediaExecutionSnapshot(media_id=MediaID.parse("tmdb:movie:1"), title="Test Movie", year=2024),
        sites=["site-a"],
        filters=SubscriptionFilters(upgrade_policy=UpgradePolicy(enabled=True)),
        target_filters=SubscriptionFilters(resolution=["2160p"]),
        directory_id="dir-1",
        active=True,
    )
    media = MediaExecutionSnapshot(
        media_id=sub.media_id,
        title="Test Movie",
        year=2024,
    )

    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.library_service.get_present_episodes",
        AsyncMock(return_value={1}),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.download_service.list_active_episodes_by_media",
        AsyncMock(return_value=set()),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.library_service.get_files_by_media",
        AsyncMock(return_value=[type("LibraryFile", (), {"resource_attributes": ResourceAttributes(resolution="1080p")})()]),
    )

    plan = ((await resource_run_plan_service.build_subscription_plan(sub.model_copy(update={"media": media}))).plan)

    assert plan is not None
    assert plan.target_episodes == {1}
    assert plan.required_scores == {}


@pytest.mark.asyncio
async def test_run_one_skips_movie_search_before_digital_release(monkeypatch):
    service = SubscriptionRunApplicationService()
    media_id = MediaID.parse("tmdb:movie:1")
    media = MediaExecutionSnapshot(
        media_id=media_id,
        title="Future Movie",
        year=2026,
        digital_release_date=_future_date(),
    )
    sub = Subscription(
        sub_id="sub-movie-future",
        media_id=media_id,
        media=media,
        sites=["site-a"],
        directory_id="dir-1",
        active=True,
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.media_service.resolve_execution_snapshot",
        AsyncMock(return_value=media),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.subscription_store.save_run_record",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.library_service.get_present_episodes",
        AsyncMock(return_value=set()),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.download_service.list_active_episodes_by_media",
        AsyncMock(return_value=set()),
    )
    search_media_mock = AsyncMock(return_value=[])
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.resource_search_service.search_media",
        search_media_mock,
    )

    result = await service.run_one(sub)

    assert result.checked == 0
    assert result.added == 0
    search_media_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_one_keeps_searching_movie_original_disc_before_digital_release(monkeypatch):
    service = SubscriptionRunApplicationService()
    media_id = MediaID.parse("tmdb:movie:1")
    media = MediaExecutionSnapshot(
        media_id=media_id,
        title="Future Disc Movie",
        year=2026,
        digital_release_date=_future_date(),
    )
    sub = Subscription(
        sub_id="sub-movie-disc-future",
        media_id=media_id,
        media=media,
        sites=["site-a"],
        filters=SubscriptionFilters(resource_kind=["original_disc"], resource_form=["BluRay Disc"]),
        directory_id="dir-1",
        active=True,
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.media_service.resolve_execution_snapshot",
        AsyncMock(return_value=media),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.subscription_store.save_run_record",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.library_service.get_present_episodes",
        AsyncMock(return_value=set()),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.download_service.list_active_episodes_by_media",
        AsyncMock(return_value=set()),
    )
    search_media_mock = AsyncMock(return_value=[])
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.resource_search_service.search_media",
        search_media_mock,
    )

    await service.run_one(sub)

    search_media_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_one_skips_movie_original_disc_before_physical_release(monkeypatch):
    service = SubscriptionRunApplicationService()
    media_id = MediaID.parse("tmdb:movie:1")
    media = MediaExecutionSnapshot(
        media_id=media_id,
        title="Future Disc Movie",
        year=2026,
        digital_release_date=_future_date(),
        physical_release_date=_future_date(),
    )
    sub = Subscription(
        sub_id="sub-movie-disc-physical-future",
        media_id=media_id,
        media=media,
        sites=["site-a"],
        filters=SubscriptionFilters(resource_kind=["original_disc"], resource_form=["BluRay Disc"]),
        directory_id="dir-1",
        active=True,
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.media_service.resolve_execution_snapshot",
        AsyncMock(return_value=media),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.subscription_store.save_run_record",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.library_service.get_present_episodes",
        AsyncMock(return_value=set()),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.download_service.list_active_episodes_by_media",
        AsyncMock(return_value=set()),
    )
    search_media_mock = AsyncMock(return_value=[])
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.resource_search_service.search_media",
        search_media_mock,
    )

    result = await service.run_one(sub)

    assert result.checked == 0
    assert result.added == 0
    search_media_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_one_skips_tv_search_when_currently_aired_episodes_are_complete(monkeypatch):
    service = SubscriptionRunApplicationService()
    media = _media(
        episodes_count=4,
        aired_episode_count=2,
        next_episode_to_air=EpisodeInfo(season_number=1, episode_number=3, air_date=_future_date()),
    )
    sub = _subscription().model_copy(update={"media": media})
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.media_service.resolve_execution_snapshot",
        AsyncMock(return_value=media),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.subscription_store.save_run_record",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.library_service.get_present_episodes",
        AsyncMock(return_value={1, 2}),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.download_service.list_active_episodes_by_media",
        AsyncMock(return_value=set()),
    )
    search_media_mock = AsyncMock(return_value=[])
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.resource_search_service.search_media",
        search_media_mock,
    )

    result = await service.run_one(sub)

    assert result.checked == 0
    assert result.added == 0
    search_media_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_one_keeps_searching_when_aired_tv_episode_is_missing(monkeypatch):
    service = SubscriptionRunApplicationService()
    media = _media(
        episodes_count=4,
        aired_episode_count=2,
        next_episode_to_air=EpisodeInfo(season_number=1, episode_number=3, air_date=_future_date()),
    )
    sub = _subscription().model_copy(update={"media": media})
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.media_service.resolve_execution_snapshot",
        AsyncMock(return_value=media),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.subscription_store.save_run_record",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.library_service.get_present_episodes",
        AsyncMock(return_value={1}),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.download_service.list_active_episodes_by_media",
        AsyncMock(return_value=set()),
    )
    search_media_mock = AsyncMock(return_value=[])
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.resource_search_service.search_media",
        search_media_mock,
    )

    await service.run_one(sub)

    search_media_mock.assert_awaited_once()
    query = search_media_mock.await_args.args[0]
    assert query.season_number == 1


@pytest.mark.asyncio
async def test_run_one_keeps_searching_original_disc_before_future_schedule(monkeypatch):
    service = SubscriptionRunApplicationService()
    media = _media(
        episodes_count=4,
        aired_episode_count=2,
        next_episode_to_air=EpisodeInfo(season_number=1, episode_number=3, air_date=_future_date()),
    )
    sub = _subscription().model_copy(update={
        "media": media,
        "filters": SubscriptionFilters(resource_kind=["original_disc"], resource_form=["BluRay Disc"]),
    })
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.media_service.resolve_execution_snapshot",
        AsyncMock(return_value=media),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.subscription_store.save_run_record",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.library_service.get_present_episodes",
        AsyncMock(return_value={1, 2}),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.download_service.list_active_episodes_by_media",
        AsyncMock(return_value=set()),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.download_service.get_tasks",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.library_service.get_files_by_media",
        AsyncMock(return_value=[]),
    )
    search_media_mock = AsyncMock(return_value=[])
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.resource_search_service.search_media",
        search_media_mock,
    )

    await service.run_one(sub)

    search_media_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_one_still_searches_when_tv_media_snapshot_loses_imdb_id(monkeypatch):
    service = SubscriptionRunApplicationService()
    media = _media(imdb_id=None)
    sub = _subscription().model_copy(update={"media": media})
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.media_service.resolve_execution_snapshot",
        AsyncMock(return_value=_media(imdb_id=None)),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.subscription_store.save_run_record",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.library_service.get_present_episodes",
        AsyncMock(return_value=set()),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.download_service.list_active_episodes_by_media",
        AsyncMock(return_value=set()),
    )
    search_media_mock = AsyncMock(return_value=[])
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.resource_search_service.search_media",
        search_media_mock,
    )

    result = await service.run_one(sub)

    assert result.checked == 0
    assert result.added == 0
    search_media_mock.assert_awaited_once()
    query = search_media_mock.await_args.args[0]
    assert query.imdbid is None
    assert query.title == "Test Show"
    assert query.season_number == 1


@pytest.mark.asyncio
async def test_run_one_uses_subscription_season_instead_of_media_snapshot_season(monkeypatch):
    service = SubscriptionRunApplicationService()
    media = _media(episodes_count=4).model_copy(update={"season_number": 2})
    sub = _subscription().model_copy(update={"season_number": 2, "media": media})
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.media_service.resolve_execution_snapshot",
        AsyncMock(return_value=_media(season_number=2, episodes_count=4)),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.subscription_store.save_run_record",
        AsyncMock(),
    )
    present_mock = AsyncMock(return_value=set())
    active_mock = AsyncMock(return_value=set())
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.library_service.get_present_episodes",
        present_mock,
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.download_service.list_active_episodes_by_media",
        active_mock,
    )
    search_media_mock = AsyncMock(return_value=[])
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.resource_search_service.search_media",
        search_media_mock,
    )

    await service.run_one(sub)

    search_media_mock.assert_awaited_once()
    query = search_media_mock.await_args.args[0]
    assert query.season_number == 2
    assert all(call.kwargs.get("season") == 2 for call in present_mock.await_args_list)
    assert active_mock.await_args.kwargs.get("season") == 2


@pytest.mark.asyncio
async def test_run_one_refreshes_stale_subscription_media_snapshot_before_planning(monkeypatch):
    service = SubscriptionRunApplicationService()
    stale_media = _media(episodes_count=0)
    sub = _subscription().model_copy(update={"media": stale_media})
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.media_service.resolve_execution_snapshot",
        AsyncMock(return_value=_media(episodes_count=4)),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.subscription_store.save_run_record",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.library_service.get_present_episodes",
        AsyncMock(return_value=set()),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.download_service.list_active_episodes_by_media",
        AsyncMock(return_value=set()),
    )
    search_media_mock = AsyncMock(return_value=[])
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.resource_search_service.search_media",
        search_media_mock,
    )

    result = await service.run_one(sub)

    assert result.checked == 0
    search_media_mock.assert_awaited_once()
    query = search_media_mock.await_args.args[0]
    assert query.media.episodes_count == 4
