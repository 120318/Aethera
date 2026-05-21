import os
import uuid
from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest

pytestmark = [pytest.mark.drift, pytest.mark.health]

os.environ.setdefault("DATA_PATH", f"/tmp/aethera-test-data-{uuid.uuid4()}")

from app.schemas.media_id import MediaID
from app.schemas.domain.download import TaskContext, TaskData, TaskStatus
from app.schemas.domain.library import LibraryFile
from app.schemas.domain.media import EpisodeInfo, MediaExecutionSnapshot, MediaFullInfo, MediaSeasonInfo
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.resource_attributes import ResourceAttributes
from app.schemas.domain.resource_search import Resource, ResourceSearchResult
from app.schemas.domain.subscription import Subscription
from app.schemas.domain.subscription_filters import SubscriptionFilters, UpgradePolicy
from app.schemas.domain.torrent import TorrentFileItem, TorrentMetadata, TorrentPayload
from app.services.domain.download import download_service
from app.services.domain.resource.selection import ResourceSelectionPlan, partition_search_results, select_resources
from app.services.application.workflows.subscription.run import SubscriptionRunApplicationService
from app.services.domain.subscription.resource_run_plan_service import resource_run_plan_service


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
