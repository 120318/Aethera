from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.schemas.domain.media import MediaExecutionSnapshot, MediaTarget
from app.schemas.domain.library import LibraryFile
from app.schemas.domain.media_download_config import EffectiveMediaDownloadConfig
from app.schemas.domain.command import CommandInitiator, CommandRecord, CommandStatus, CommandTargetType, CommandType, TaskCreateCommandRecordPayload
from app.schemas.domain.download import TaskContext, TaskData, TaskStatus
from app.schemas.domain.quality_ranking import QualityRankingConfig
from app.schemas.domain.quality_profile import QualityProfile
from app.schemas.domain.resource_attributes import ResourceAttributes
from app.schemas.domain.resource_search import Resource, ResourceSearchResult
from app.schemas.domain.media_subscription_state import MediaSubscriptionState, SubscriptionEndReason, UpgradeCompletionSnapshot
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.subscription import Subscription
from app.schemas.domain.subscription_filters import SubscriptionFilters, UpgradePolicy
from app.schemas.domain.torrent import TorrentMetadata
from app.schemas.exception import DownloadException, SubscriptionNotFoundException
from app.schemas.media_id import MediaID
from app.services.domain.subscription.query_service import subscription_query_service
from app.services.application.workflows.subscription.run import SubscriptionRunApplicationService
from app.services.domain.subscription.completion_checker import subscription_completion_checker
from app.services.domain.subscription.resource_run_plan_service import resource_run_plan_service
from app.services.domain.subscription.upgrade_baseline_service import subscription_upgrade_baseline_service
from app.schemas.runtime.subscription_lifecycle import ResourceRunSelection
from datetime import UTC, datetime


def _movie_subscription(*, upgrade_enabled: bool = False) -> Subscription:
    media = MediaExecutionSnapshot(media_id=MediaID.parse("tmdb:movie:1"), title="Sample", year=2024)
    return Subscription(
        sub_id="sub-movie",
        media_id=media.media_id,
        media=media,
        directory_id="dir-1",
        active=True,
        filters=SubscriptionFilters(upgrade_policy=UpgradePolicy(enabled=upgrade_enabled)) if upgrade_enabled else None,
    )


def _tv_subscription(*, upgrade_enabled: bool = False) -> Subscription:
    media = MediaExecutionSnapshot(media_id=MediaID.parse("tmdb:tv:1"), title="Sample", year=2024, season_number=1, episodes_count=12)
    return Subscription(
        sub_id="sub-tv",
        media_id=media.media_id,
        media=media,
        season_number=1,
        directory_id="dir-1",
        active=True,
        filters=SubscriptionFilters(upgrade_policy=UpgradePolicy(enabled=upgrade_enabled)) if upgrade_enabled else None,
    )


def _tv_disc_subscription() -> Subscription:
    sub = _tv_subscription()
    sub.filters = SubscriptionFilters(resource_kind=["original_disc"], resource_form=["BluRay Disc"])
    return sub


def _disc_task(number: int, total: int = 2):
    media = MediaExecutionSnapshot(media_id=MediaID.parse("tmdb:tv:1"), title="Sample", year=2024, season_number=1, episodes_count=12)
    title = f"Show.S01.Disc.{number}.of.{total}"
    metadata = TorrentMetadata(
        hash=f"hash-{number}",
        name=title,
        size=1,
        files=[],
        attrs=ResourceAttributes(
            title=title,
            seasons=[1],
            episodes=[],
            resource_form="BluRay Disc",
            resource_form_evidence="torrent_structure",
            disc_number=number,
            disc_total=total,
        ),
        coverage_kind="disc_package",
    )
    return TaskData(
        id=f"task-{number}",
        media_id=media.media_id,
        torrent_hash=metadata.hash,
        status=TaskStatus.DOWNLOADING,
        context=TaskContext(download_url="https://example.com/torrent", media=media, directory_id="dir-1", parsed_attributes=metadata.attrs),
        metadata=metadata,
    )


def _season_package_task():
    media = MediaExecutionSnapshot(media_id=MediaID.parse("tmdb:tv:1"), title="Sample", year=2024, season_number=1, episodes_count=12)
    metadata = TorrentMetadata(
        hash="hash-season",
        name="Show.S01.Complete.BDMV",
        size=1,
        files=[],
        attrs=ResourceAttributes(
            title="Show.S01.Complete.BDMV",
            seasons=[1],
            episodes=[],
            resource_form="BluRay Disc",
            resource_form_evidence="torrent_structure",
        ),
        coverage_kind="season_package",
    )
    return TaskData(
        id="task-season",
        media_id=media.media_id,
        torrent_hash=metadata.hash,
        status=TaskStatus.DOWNLOADING,
        context=TaskContext(download_url="https://example.com/torrent", media=media, directory_id="dir-1", parsed_attributes=metadata.attrs),
        metadata=metadata,
    )


def _movie_media() -> MediaExecutionSnapshot:
    return MediaExecutionSnapshot(
        media_id=MediaID.parse("tmdb:movie:1"),
        title="Sample",
        year=2024,
    )


def _tv_media(*, aired_episode_count: int = 4, episodes_count: int = 12) -> MediaExecutionSnapshot:
    return MediaExecutionSnapshot(
        media_id=MediaID.parse("tmdb:tv:1"),
        title="Sample",
        year=2024,
        season_number=1,
        episodes_count=episodes_count,
        aired_episode_count=aired_episode_count,
    )


def _task_create_command() -> CommandRecord:
    media_id = MediaID.parse("tmdb:movie:1")
    return CommandRecord(
        id="cmd-task-create",
        type=CommandType.TASK_CREATE,
        status=CommandStatus.QUEUED,
        message="Sample",
        payload=TaskCreateCommandRecordPayload(media=_movie_media(), result_id="r1", directory_id="dir-1"),
        initiator=CommandInitiator.SYSTEM,
        media_id=media_id,
        target=MediaTarget(media_id=media_id),
        uniq_key="command:task.create:test",
        target_type=CommandTargetType.MEDIA,
        target_id=str(media_id),
        created_at=datetime.now(),
    )


def test_compose_runtime_subscription_keeps_upgrade_policy_without_custom_filters():
    state = MediaSubscriptionState(
        sub_id="sub-tv",
        media_id=MediaID.parse("tmdb:tv:1"),
        media=_tv_media(),
        active=True,
        followed=True,
        upgrade_policy=UpgradePolicy(enabled=True, strategy="consistent_skip_low", min_upgrade_score_delta=12),
    )
    config = EffectiveMediaDownloadConfig(
        media_id=state.media_id,
        sub_id=state.sub_id,
        directory_id="dir-1",
        filter_config_id=None,
        quality_profile_id=None,
        filters=None,
        sites=None,
        unmatched_rules=[],
        quality_profile=None,
    )

    sub = subscription_query_service.compose_runtime_subscription(state, config)

    assert sub.filters is not None
    assert sub.filters.upgrade_policy is not None
    assert sub.filters.upgrade_policy.enabled is True
    assert sub.filters.upgrade_policy.strategy == "consistent_skip_low"


def test_compose_runtime_subscription_falls_back_to_target_preset_when_target_filters_is_empty(monkeypatch):
    state = MediaSubscriptionState(
        sub_id="sub-tv",
        media_id=MediaID.parse("tmdb:tv:1"),
        media=_tv_media(),
        active=True,
        followed=True,
        target_filters=SubscriptionFilters(),
        target_filter_config_id="filter-target",
    )
    config = EffectiveMediaDownloadConfig(
        media_id=state.media_id,
        sub_id=state.sub_id,
        directory_id="dir-1",
        filter_config_id=None,
        quality_profile_id=None,
        filters=None,
        sites=None,
        unmatched_rules=[],
        quality_profile=None,
    )
    preset_filters = SubscriptionFilters(resolution=["2160p"])

    monkeypatch.setattr(
        "app.services.domain.subscription.query_service.settings_service.get_filter",
        lambda filter_id: type("FilterConfig", (), {"filters": preset_filters})() if filter_id == "filter-target" else None,
    )

    sub = subscription_query_service.compose_runtime_subscription(state, config)

    assert sub.target_filters == preset_filters


def test_compose_runtime_subscription_merges_target_preset_override(monkeypatch):
    state = MediaSubscriptionState(
        sub_id="sub-tv",
        media_id=MediaID.parse("tmdb:tv:1"),
        media=_tv_media(),
        active=True,
        followed=True,
        target_filters=SubscriptionFilters(resolution=["1080p"]),
        target_filter_config_id="filter-target",
    )
    config = EffectiveMediaDownloadConfig(
        media_id=state.media_id,
        sub_id=state.sub_id,
        directory_id="dir-1",
        filter_config_id=None,
        quality_profile_id=None,
        filters=None,
        sites=None,
        unmatched_rules=[],
        quality_profile=None,
    )
    preset_filters = SubscriptionFilters(resolution=["2160p"], source=["BluRay"], codec=["HEVC"])

    monkeypatch.setattr(
        "app.services.domain.subscription.query_service.settings_service.get_filter",
        lambda filter_id: type("FilterConfig", (), {"filters": preset_filters})() if filter_id == "filter-target" else None,
    )

    sub = subscription_query_service.compose_runtime_subscription(state, config)

    assert sub.target_filters == SubscriptionFilters(resolution=["1080p"], source=["BluRay"], codec=["HEVC"])


@pytest.mark.asyncio
async def test_run_one_by_sub_id_rejects_inactive_subscription(monkeypatch):
    service = SubscriptionRunApplicationService()
    state = MediaSubscriptionState(
        sub_id="sub-inactive",
        media_id=MediaID.parse("tmdb:movie:1"),
        media=_movie_media(),
        active=False,
    )

    monkeypatch.setattr(
        "app.services.domain.subscription.query_service.subscription_query_service.get_state_by_sub_id",
        AsyncMock(return_value=None),
    )
    build_runtime_subscription = AsyncMock()
    monkeypatch.setattr(service, "_build_runtime_subscription", build_runtime_subscription)

    with pytest.raises(SubscriptionNotFoundException):
        await service.run_one_by_sub_id("sub-inactive")

    build_runtime_subscription.assert_not_awaited()


@pytest.mark.asyncio
async def test_subscription_run_search_bypasses_indexer_cache(monkeypatch):
    seen_queries = []

    async def fake_search(query):
        seen_queries.append(query)
        return []

    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.resource_search_service.search_media",
        fake_search,
    )
    media = _movie_media()
    plan = type(
        "Plan",
        (),
        {
            "media": media,
            "season_number": None,
            "sites": ["site-a"],
            "correlation_id": "corr-1",
        },
    )()

    await SubscriptionRunApplicationService()._search_and_select_resources(subscription=_movie_subscription(), plan=plan)

    assert seen_queries
    assert seen_queries[0].use_cache is False


@pytest.mark.asyncio
async def test_subscription_run_search_does_not_emit_failed_event_when_no_resources(monkeypatch):
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.resource_search_service.search_media",
        AsyncMock(return_value=[]),
    )
    media = _movie_media()
    plan = type(
        "Plan",
        (),
        {
            "media": media,
            "season_number": None,
            "sites": ["site-a"],
            "correlation_id": "corr-1",
        },
    )()

    results = await SubscriptionRunApplicationService()._search_and_select_resources(subscription=_movie_subscription(), plan=plan)

    assert results.checked == 0
    assert results.matched == 0


@pytest.mark.asyncio
async def test_run_one_does_not_emit_event_when_no_resources(monkeypatch):
    service = SubscriptionRunApplicationService()
    sub = _movie_subscription()
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.media_service.resolve_execution_snapshot",
        AsyncMock(return_value=sub.media),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.subscription_store.save_run_record",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.subscription_store.save_run_record",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.subscription_completion_checker.check",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.library_service.get_present_episodes",
        AsyncMock(return_value=set()),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.download_service.list_active_episodes_by_media",
        AsyncMock(return_value=set()),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.resource_search_service.search_media",
        AsyncMock(return_value=[]),
    )
    emit_media = Mock()
    monkeypatch.setattr("app.services.application.workflows.subscription.run.event_service.emit_media", emit_media)

    result = await service.run_one(sub)

    assert result.checked == 0
    assert result.added == 0
    emit_media.assert_not_called()


@pytest.mark.asyncio
async def test_run_one_emits_failed_event_when_subscription_is_invalid(monkeypatch):
    service = SubscriptionRunApplicationService()
    media = MediaExecutionSnapshot(
        media_id=MediaID.parse("tmdb:tv:1"),
        title="Sample",
        year=2024,
        season_number=1,
    )
    sub = Subscription(
        sub_id="sub-tv",
        media_id=media.media_id,
        media=media,
        season_number=1,
        directory_id="dir-1",
        active=True,
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.media_service.resolve_execution_snapshot",
        AsyncMock(return_value=media),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.subscription_store.save_run_record",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.subscription_store.save_run_record",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.subscription_completion_checker.check",
        AsyncMock(return_value=None),
    )
    emit_media = Mock()
    monkeypatch.setattr("app.services.application.workflows.subscription.run.event_service.emit_media", emit_media)

    result = await service.run_one(sub)

    assert result.checked == 0
    assert result.added == 0
    emit_media.assert_called_once()
    event = emit_media.call_args.args[0]
    assert event.type.value == "subscription.run.failed"
    assert event.message_key is None
    assert event.message_params == {"reason_key": "backendErrors.subscriptionRunEpisodeCountMissing"}


@pytest.mark.asyncio
async def test_run_one_emits_failed_event_when_all_selected_resources_fail_to_queue(monkeypatch):
    service = SubscriptionRunApplicationService()
    sub = _movie_subscription()
    resource_result = ResourceSearchResult(
        id="movie-pack",
        title="movie-pack",
        site="test",
        category="movie",
        size="1 GB",
        seeders=10,
        leechers=0,
        publish_date=datetime.now(UTC),
        download_url="https://example.com/movie-pack",
        result_id="movie-pack",
        matched_by_id=True,
    )
    resource = Resource(
        resources=resource_result,
        attrs=ResourceAttributes(title="movie-pack", resolution="1080p"),
    )
    payload = SimpleNamespace(metadata=SimpleNamespace(name="movie-pack", size=1, get_episodes=lambda: set()))
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.media_service.resolve_execution_snapshot",
        AsyncMock(return_value=sub.media),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.subscription_store.save_run_record",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.subscription_store.save_run_record",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.subscription_completion_checker.check",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.SubscriptionRunApplicationService._search_and_select_resources",
        AsyncMock(return_value=ResourceRunSelection(checked=1, matched=1, selected=[(payload, [], resource)])),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.command_service.create_command",
        AsyncMock(side_effect=DownloadException("queue failed")),
    )
    emit_media = Mock()
    monkeypatch.setattr("app.services.application.workflows.subscription.run.event_service.emit_media", emit_media)

    result = await service.run_one(sub)

    assert result.checked == 1
    assert result.added == 0
    emit_media.assert_called_once()
    event = emit_media.call_args.args[0]
    assert event.type.value == "subscription.run.failed"
    assert event.message_params == {"reason_key": "subscriptionRunMessages.queueFailed"}


@pytest.mark.asyncio
async def test_resolve_movie_completion_state_ends_when_file_exists(monkeypatch):
    service = SubscriptionRunApplicationService()

    monkeypatch.setattr(
        "app.services.domain.subscription.upgrade_baseline_service.library_service.get_files_by_media",
        AsyncMock(return_value=[object()]),
    )

    reason = await subscription_completion_checker.resolve_movie_completion_state(_movie_subscription(), _movie_media())

    assert reason == SubscriptionEndReason.MOVIE_LIBRARY_COMPLETED


@pytest.mark.asyncio
async def test_resolve_movie_completion_state_ends_when_download_exists(monkeypatch):
    service = SubscriptionRunApplicationService()

    monkeypatch.setattr(
        "app.services.domain.subscription.upgrade_baseline_service.library_service.get_files_by_media",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.completion_checker.download_service.get_tasks",
        AsyncMock(return_value=[object()]),
    )

    reason = await subscription_completion_checker.resolve_movie_completion_state(_movie_subscription(), _movie_media())

    assert reason == SubscriptionEndReason.MOVIE_DOWNLOADING_COMPLETED


@pytest.mark.asyncio
async def test_resolve_movie_completion_state_skips_auto_end_for_movie_upgrade(monkeypatch):
    service = SubscriptionRunApplicationService()

    monkeypatch.setattr(
        "app.services.domain.subscription.upgrade_baseline_service.library_service.get_files_by_media",
        AsyncMock(return_value=[object()]),
    )

    reason = await subscription_completion_checker.resolve_movie_completion_state(_movie_subscription(upgrade_enabled=True), _movie_media())

    assert reason is None


@pytest.mark.asyncio
async def test_resolve_movie_completion_state_does_not_end_for_empty_target_filters(monkeypatch):
    service = SubscriptionRunApplicationService()
    subscription = _movie_subscription(upgrade_enabled=True)
    subscription.target_filters = SubscriptionFilters()

    monkeypatch.setattr(
        "app.services.domain.subscription.upgrade_baseline_service.library_service.get_files_by_media",
        AsyncMock(return_value=[object()]),
    )

    reason = await subscription_completion_checker.resolve_movie_completion_state(subscription, _movie_media())

    assert reason is None


@pytest.mark.asyncio
async def test_resolve_movie_completion_state_does_not_end_when_only_task_create_command_is_queued(monkeypatch):
    service = SubscriptionRunApplicationService()

    monkeypatch.setattr(
        "app.services.domain.subscription.upgrade_baseline_service.library_service.get_files_by_media",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.completion_checker.download_service.get_tasks",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.run.command_service.list_media_active_commands",
        AsyncMock(return_value=[_task_create_command()]),
    )

    reason = await subscription_completion_checker.resolve_movie_completion_state(_movie_subscription(), _movie_media())

    assert reason is None


@pytest.mark.asyncio
async def test_resolve_tv_completion_state_ends_when_all_episodes_are_covered(monkeypatch):
    service = SubscriptionRunApplicationService()

    monkeypatch.setattr(
        "app.services.domain.subscription.completion_checker.library_service.get_present_episodes",
        AsyncMock(return_value={1, 2, 3, 4, 5, 6}),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.completion_checker.download_service.list_active_episodes_by_media",
        AsyncMock(return_value={7, 8, 9, 10, 11, 12}),
    )

    reason = await subscription_completion_checker.resolve_tv_completion_state(_tv_subscription(), _tv_media(aired_episode_count=4))

    assert reason == SubscriptionEndReason.TV_COMPLETED


@pytest.mark.asyncio
async def test_resolve_tv_completion_state_does_not_end_when_only_current_aired_episodes_are_complete(monkeypatch):
    service = SubscriptionRunApplicationService()

    monkeypatch.setattr(
        "app.services.domain.subscription.completion_checker.library_service.get_present_episodes",
        AsyncMock(return_value={1, 2}),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.completion_checker.download_service.list_active_episodes_by_media",
        AsyncMock(return_value={3}),
    )

    reason = await subscription_completion_checker.resolve_tv_completion_state(_tv_subscription(), _tv_media(aired_episode_count=4))

    assert reason is None


@pytest.mark.asyncio
async def test_resolve_tv_completion_state_does_not_end_when_all_episodes_are_incomplete(monkeypatch):
    service = SubscriptionRunApplicationService()

    monkeypatch.setattr(
        "app.services.domain.subscription.completion_checker.library_service.get_present_episodes",
        AsyncMock(return_value={1, 2, 3, 4, 5, 6}),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.completion_checker.download_service.list_active_episodes_by_media",
        AsyncMock(return_value={7, 8, 9, 10, 11}),
    )

    reason = await subscription_completion_checker.resolve_tv_completion_state(_tv_subscription(), _tv_media(aired_episode_count=12))

    assert reason is None


@pytest.mark.drift
@pytest.mark.asyncio
async def test_resolve_tv_disc_subscription_ends_when_season_package_is_downloading(monkeypatch):
    service = SubscriptionRunApplicationService()

    monkeypatch.setattr(
        "app.services.domain.subscription.completion_checker.download_service.get_tasks",
        AsyncMock(return_value=[_season_package_task()]),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.upgrade_baseline_service.library_service.get_files_by_media",
        AsyncMock(return_value=[]),
    )

    reason = await subscription_completion_checker.resolve_tv_completion_state(_tv_disc_subscription(), _tv_media(aired_episode_count=4))

    assert reason == SubscriptionEndReason.TV_COMPLETED


@pytest.mark.drift
@pytest.mark.asyncio
async def test_resolve_tv_disc_subscription_waits_for_all_discs(monkeypatch):
    service = SubscriptionRunApplicationService()

    monkeypatch.setattr(
        "app.services.domain.subscription.completion_checker.download_service.get_tasks",
        AsyncMock(return_value=[_disc_task(1, total=2)]),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.upgrade_baseline_service.library_service.get_files_by_media",
        AsyncMock(return_value=[]),
    )

    reason = await subscription_completion_checker.resolve_tv_completion_state(_tv_disc_subscription(), _tv_media(aired_episode_count=4))

    assert reason is None


@pytest.mark.drift
@pytest.mark.asyncio
async def test_resolve_tv_disc_subscription_ends_when_all_discs_are_downloading(monkeypatch):
    service = SubscriptionRunApplicationService()

    monkeypatch.setattr(
        "app.services.domain.subscription.completion_checker.download_service.get_tasks",
        AsyncMock(return_value=[_disc_task(1, total=2), _disc_task(2, total=2)]),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.upgrade_baseline_service.library_service.get_files_by_media",
        AsyncMock(return_value=[]),
    )

    reason = await subscription_completion_checker.resolve_tv_completion_state(_tv_disc_subscription(), _tv_media(aired_episode_count=4))

    assert reason == SubscriptionEndReason.TV_COMPLETED


@pytest.mark.drift
@pytest.mark.asyncio
async def test_resolve_tv_disc_subscription_ends_when_library_has_all_discs(monkeypatch):
    service = SubscriptionRunApplicationService()
    media_id = MediaID.parse("tmdb:tv:1")
    files = [
        LibraryFile(
            id="disc-1",
            task_id="deleted-task",
            directory_id="dir-1",
        media_id=media_id,
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
        ),
        LibraryFile(
            id="disc-2",
            task_id="deleted-task",
            directory_id="dir-1",
        media_id=media_id,
            path="Shows/Test/Season 01/Package/Disc 2/BDMV",
            file_name="index.bdmv",
            file_size=1,
            created_at=0,
            resource_attributes=ResourceAttributes(
                seasons=[1],
                episodes=[],
                resource_form="BluRay Disc",
                package_layout="BDMV",
                disc_number=2,
                disc_total=2,
            ),
        ),
    ]

    monkeypatch.setattr(
        "app.services.domain.subscription.completion_checker.download_service.get_tasks",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.upgrade_baseline_service.library_service.get_files_by_media",
        AsyncMock(return_value=files),
    )

    reason = await subscription_completion_checker.resolve_tv_completion_state(_tv_disc_subscription(), _tv_media(aired_episode_count=4))

    assert reason == SubscriptionEndReason.TV_COMPLETED


@pytest.mark.drift
@pytest.mark.asyncio
async def test_resolve_tv_disc_subscription_ends_when_library_has_season_package(monkeypatch):
    service = SubscriptionRunApplicationService()
    media_id = MediaID.parse("tmdb:tv:1")
    package_file = LibraryFile(
        id="season-package",
        task_id="deleted-task",
        directory_id="dir-1",
        media_id=media_id,
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
        "app.services.domain.subscription.completion_checker.download_service.get_tasks",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.upgrade_baseline_service.library_service.get_files_by_media",
        AsyncMock(return_value=[package_file]),
    )

    reason = await subscription_completion_checker.resolve_tv_completion_state(_tv_disc_subscription(), _tv_media(aired_episode_count=4))

    assert reason == SubscriptionEndReason.TV_COMPLETED


@pytest.mark.drift
@pytest.mark.asyncio
async def test_resolve_tv_disc_subscription_ignores_library_package_that_mismatches_filters(monkeypatch):
    service = SubscriptionRunApplicationService()
    media_id = MediaID.parse("tmdb:tv:1")
    sub = _tv_disc_subscription()
    sub.filters = SubscriptionFilters(resource_kind=["original_disc"], resource_form=["DVD Disc"])
    package_file = LibraryFile(
        id="season-package",
        task_id="deleted-task",
        directory_id="dir-1",
        media_id=media_id,
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
        "app.services.domain.subscription.completion_checker.download_service.get_tasks",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.upgrade_baseline_service.library_service.get_files_by_media",
        AsyncMock(return_value=[package_file]),
    )

    reason = await subscription_completion_checker.resolve_tv_completion_state(sub, _tv_media(aired_episode_count=4))

    assert reason is None


@pytest.mark.asyncio
async def test_resolve_tv_completion_state_does_not_end_when_upgrade_baseline_not_met(monkeypatch):
    service = SubscriptionRunApplicationService()
    state = MediaSubscriptionState(
        sub_id="sub-tv",
        media_id=MediaID.parse("tmdb:tv:1"),
        media=_tv_media(),
        active=True,
        upgrade_completion_snapshot=UpgradeCompletionSnapshot(
            season_number=1,
            baseline_score=100,
            baseline_episode_upper_bound=4,
        ),
    )

    monkeypatch.setattr(
        "app.services.domain.subscription.upgrade_baseline_service.subscription_query_service.get_state",
        AsyncMock(return_value=state),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.completion_checker.library_service.get_present_episodes",
        AsyncMock(return_value={1, 2, 3, 4}),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.upgrade_baseline_service.library_service.get_episode_attributes",
        AsyncMock(return_value={1: [object()], 2: [object()], 3: [object()], 4: [object()]}),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.completion_checker.compute_preference_score_from_attrs",
        lambda attrs, quality_profile: (90, None),
    )

    reason = await subscription_completion_checker.resolve_tv_completion_state(_tv_subscription(upgrade_enabled=True), _tv_media(aired_episode_count=4))

    assert reason is None


@pytest.mark.asyncio
async def test_resolve_tv_completion_state_does_not_end_upgrade_before_full_season_is_present(monkeypatch):
    service = SubscriptionRunApplicationService()
    state = MediaSubscriptionState(
        sub_id="sub-tv",
        media_id=MediaID.parse("tmdb:tv:1"),
        media=_tv_media(),
        active=True,
        upgrade_completion_snapshot=UpgradeCompletionSnapshot(
            season_number=1,
            baseline_score=100,
            baseline_episode_upper_bound=4,
        ),
    )

    monkeypatch.setattr(
        "app.services.domain.subscription.upgrade_baseline_service.subscription_query_service.get_state",
        AsyncMock(return_value=state),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.completion_checker.library_service.get_present_episodes",
        AsyncMock(return_value={1, 2, 3, 4}),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.completion_checker.library_service.get_episode_attributes",
        AsyncMock(return_value={1: [object()], 2: [object()], 3: [object()], 4: [object()]}),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.completion_checker.compute_preference_score_from_attrs",
        lambda attrs, quality_profile: (100, None),
    )

    reason = await subscription_completion_checker.resolve_tv_completion_state(_tv_subscription(upgrade_enabled=True), _tv_media(aired_episode_count=4))

    assert reason is None


@pytest.mark.asyncio
async def test_resolve_tv_completion_state_ends_upgrade_when_full_season_is_present_and_baseline_met(monkeypatch):
    state = MediaSubscriptionState(
        sub_id="sub-tv",
        media_id=MediaID.parse("tmdb:tv:1"),
        media=_tv_media(),
        active=True,
        upgrade_completion_snapshot=UpgradeCompletionSnapshot(
            season_number=1,
            baseline_score=100,
            baseline_episode_upper_bound=4,
        ),
    )

    monkeypatch.setattr(
        "app.services.domain.subscription.upgrade_baseline_service.subscription_query_service.get_state",
        AsyncMock(return_value=state),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.completion_checker.library_service.get_present_episodes",
        AsyncMock(return_value=set(range(1, 13))),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.completion_checker.library_service.get_episode_attributes",
        AsyncMock(return_value={episode: [object()] for episode in range(1, 13)}),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.completion_checker.compute_preference_score_from_attrs",
        lambda attrs, quality_profile: (100, None),
    )

    reason = await subscription_completion_checker.resolve_tv_completion_state(
        _tv_subscription(upgrade_enabled=True),
        _tv_media(aired_episode_count=12),
    )

    assert reason == SubscriptionEndReason.TV_UPGRADE_COMPLETED


@pytest.mark.asyncio
async def test_resolve_tv_completion_state_does_not_treat_empty_target_filters_as_target_completion(monkeypatch):
    service = SubscriptionRunApplicationService()
    subscription = _tv_subscription(upgrade_enabled=True)
    subscription.target_filters = SubscriptionFilters()
    state = MediaSubscriptionState(
        sub_id="sub-tv",
        media_id=MediaID.parse("tmdb:tv:1"),
        media=_tv_media(),
        active=True,
        upgrade_completion_snapshot=UpgradeCompletionSnapshot(
            season_number=1,
            baseline_score=100,
            baseline_episode_upper_bound=4,
        ),
    )

    monkeypatch.setattr(
        "app.services.domain.subscription.upgrade_baseline_service.subscription_query_service.get_state",
        AsyncMock(return_value=state),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.completion_checker.library_service.get_present_episodes",
        AsyncMock(return_value={1, 2, 3, 4}),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.completion_checker.library_service.get_episode_attributes",
        AsyncMock(return_value={1: [object()], 2: [object()], 3: [object()], 4: [object()]}),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.completion_checker.compute_preference_score_from_attrs",
        lambda attrs, quality_profile: (100, None),
    )

    reason = await subscription_completion_checker.resolve_tv_completion_state(subscription, _tv_media(aired_episode_count=4))

    assert reason is None


@pytest.mark.asyncio
async def test_resolve_tv_completion_state_does_not_end_when_only_snapshot_range_is_met(monkeypatch):
    service = SubscriptionRunApplicationService()
    state = MediaSubscriptionState(
        sub_id="sub-tv",
        media_id=MediaID.parse("tmdb:tv:1"),
        media=_tv_media(),
        active=True,
        upgrade_completion_snapshot=UpgradeCompletionSnapshot(
            season_number=1,
            baseline_score=100,
            baseline_episode_upper_bound=4,
        ),
    )

    monkeypatch.setattr(
        "app.services.domain.subscription.upgrade_baseline_service.subscription_query_service.get_state",
        AsyncMock(return_value=state),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.completion_checker.library_service.get_present_episodes",
        AsyncMock(return_value={1, 2, 3, 4}),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.completion_checker.library_service.get_episode_attributes",
        AsyncMock(return_value={1: [object()], 2: [object()], 3: [object()], 4: [object()]}),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.completion_checker.compute_preference_score_from_attrs",
        lambda attrs, quality_profile: (100, None),
    )

    reason = await subscription_completion_checker.resolve_tv_completion_state(_tv_subscription(upgrade_enabled=True), _tv_media(aired_episode_count=5))

    assert reason is None


@pytest.mark.asyncio
async def test_upgrade_baseline_uses_subscription_quality_profile(monkeypatch):
    service = SubscriptionRunApplicationService()
    subscription = _tv_subscription(upgrade_enabled=True)
    subscription.quality_profile_id = "qp-custom"
    state = MediaSubscriptionState(
        sub_id="sub-tv",
        media_id=MediaID.parse("tmdb:tv:1"),
        media=_tv_media(),
        active=True,
        upgrade_completion_snapshot=None,
    )
    quality_profile = QualityProfile(name="Custom", ranking=QualityRankingConfig(), active_default=False)

    monkeypatch.setattr(
        "app.services.domain.subscription.upgrade_baseline_service.subscription_query_service.get_state",
        AsyncMock(return_value=state),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.completion_checker.library_service.get_episode_attributes",
        AsyncMock(return_value={1: [object()], 2: [object()], 3: [object()], 4: [object()]}),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.policy.settings_service.get_quality_profile",
        lambda profile_id: quality_profile if profile_id == "qp-custom" else None,
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.policy.settings_service.get_default_quality_profile",
        lambda: QualityProfile(name="Default", ranking=QualityRankingConfig(), active_default=True),
    )

    captured_profiles = []

    def _score(attrs, profile):
        captured_profiles.append(profile)
        return (100, None)

    monkeypatch.setattr(
        "app.services.domain.subscription.upgrade_baseline_service.compute_preference_score_from_attrs",
        _score,
    )

    snapshot = await subscription_upgrade_baseline_service.resolve_snapshot(subscription, _tv_media(aired_episode_count=4), 4)

    assert snapshot is not None
    assert captured_profiles
    assert all(profile is quality_profile for profile in captured_profiles)


@pytest.mark.asyncio
async def test_upgrade_baseline_uses_first_download_lock_mode(monkeypatch):
    service = SubscriptionRunApplicationService()
    subscription = _tv_subscription(upgrade_enabled=True)
    subscription.filters.upgrade_policy.lock_mode = "first_download"
    state = MediaSubscriptionState(
        sub_id="sub-tv",
        media_id=MediaID.parse("tmdb:tv:1"),
        media=_tv_media(),
        active=True,
        upgrade_completion_snapshot=None,
    )

    monkeypatch.setattr(
        "app.services.domain.subscription.upgrade_baseline_service.subscription_query_service.get_state",
        AsyncMock(return_value=state),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.upgrade_baseline_service.library_service.get_episode_attributes",
        AsyncMock(return_value={1: ["ep1"], 2: ["ep2"], 3: ["ep3"]}),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.upgrade_baseline_service.compute_preference_score_from_attrs",
        lambda attrs, quality_profile: (
            {"ep1": 80, "ep2": 120, "ep3": 100}[attrs],
            None,
        ),
    )

    snapshot = await subscription_upgrade_baseline_service.resolve_snapshot(subscription, _tv_media(aired_episode_count=3), 3)

    assert snapshot is not None
    assert snapshot.baseline_score == 80


@pytest.mark.asyncio
async def test_upgrade_baseline_uses_zero_threshold_when_lock_mode_is_off(monkeypatch):
    service = SubscriptionRunApplicationService()
    subscription = _tv_subscription(upgrade_enabled=True)
    subscription.filters.upgrade_policy.lock_mode = "off"
    state = MediaSubscriptionState(
        sub_id="sub-tv",
        media_id=MediaID.parse("tmdb:tv:1"),
        media=_tv_media(),
        active=True,
        upgrade_completion_snapshot=None,
    )

    monkeypatch.setattr(
        "app.services.domain.subscription.upgrade_baseline_service.subscription_query_service.get_state",
        AsyncMock(return_value=state),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.upgrade_baseline_service.library_service.get_episode_attributes",
        AsyncMock(return_value={1: ["ep1"], 2: ["ep2"]}),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.upgrade_baseline_service.compute_preference_score_from_attrs",
        lambda attrs, quality_profile: (95, None),
    )

    snapshot = await subscription_upgrade_baseline_service.resolve_snapshot(subscription, _tv_media(aired_episode_count=2), 2)

    assert snapshot is not None
    assert snapshot.baseline_score == 0


def test_upgrade_baseline_fingerprint_changes_when_upgrade_policy_changes():
    service = SubscriptionRunApplicationService()
    first = _tv_subscription(upgrade_enabled=True)
    second = _tv_subscription(upgrade_enabled=True)
    second.filters.upgrade_policy.lock_mode = "first_download"
    second.filters.upgrade_policy.min_upgrade_score_delta = 12

    first_fingerprint = subscription_upgrade_baseline_service.compute_config_fingerprint(first)
    second_fingerprint = subscription_upgrade_baseline_service.compute_config_fingerprint(second)

    assert first_fingerprint != second_fingerprint
