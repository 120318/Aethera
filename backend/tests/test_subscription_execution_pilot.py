from datetime import datetime, UTC
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.schemas.exception.exceptions import DownloadException
from app.schemas.domain.media import MediaExecutionSnapshot, MediaFullInfo, MediaSeasonInfo
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.quality_profile import QualityProfile
from app.schemas.domain.resource_attributes import ResourceAttributes
from app.schemas.domain.resource_search import Resource, ResourceSearchResult
from app.schemas.domain.subscription import Subscription, SubscriptionUnmatchedRule
from app.schemas.domain.subscription_filters import SubscriptionFilters, UpgradePolicy
from app.schemas.domain.torrent import TorrentFileItem, TorrentMetadata, TorrentPayload
from app.schemas.media_id import MediaID
from app.services.domain.resource.pilot_selection import finalize_pilot_resource, select_pilot_resources
from app.services.domain.resource.selection import ResourceSelectionPlan, partition_search_results, select_resources
from app.services.application.workflows.subscription.pilot import pilot_download_application_service
from app.services.domain.subscription.resource_run_plan_service import resource_run_plan_service
from app.services.application.workflows.subscription.run import SubscriptionRunApplicationService


@pytest.fixture(autouse=True)
def _default_effective_pilot_config(monkeypatch):
    async def fake_resolve_effective_config(_media_id, _media_type, *, season_number=None):
        _ = season_number
        return SimpleNamespace(
            directory_id="dir-default",
            filters=None,
            quality_profile_id=None,
            quality_profile=None,
            sites=None,
            unmatched_rules=[],
        )

    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.subscription_download_config_service.resolve_effective_config",
        fake_resolve_effective_config,
    )


@pytest.mark.asyncio
async def test_pilot_is_allowed_when_only_partial_prefix_is_occupied(monkeypatch):
    async def fake_present_episodes(media_id, season=None):
        return {3}

    async def fake_downloading_episodes(media_id, season=None):
        return set()

    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.library_service.get_present_episodes",
        fake_present_episodes,
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.download_service.list_active_episodes_by_media",
        fake_downloading_episodes,
    )

    await pilot_download_application_service._ensure_pilot_available(
        media_id=MediaID.parse("tmdb:tv:123"),
        season_number=1,
        target_episodes={1, 2, 3},
    )


@pytest.mark.asyncio
async def test_pilot_is_rejected_only_when_full_prefix_is_occupied(monkeypatch):
    async def fake_present_episodes(media_id, season=None):
        return {1, 3}

    async def fake_downloading_episodes(media_id, season=None):
        return {2}

    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.library_service.get_present_episodes",
        fake_present_episodes,
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.download_service.list_active_episodes_by_media",
        fake_downloading_episodes,
    )

    with pytest.raises(DownloadException) as exc_info:
        await pilot_download_application_service._ensure_pilot_available(
            media_id=MediaID.parse("tmdb:tv:123"),
            season_number=1,
            target_episodes={1, 2, 3},
        )
    assert exc_info.value.message_key == "backendErrors.pilotEpisodesAlreadyCovered"


def _build_resource(
    title: str,
    episodes: list[int] | None,
    seeders: int = 10,
    *,
    size: str = "1 GB",
    resolution: str = "2160p",
    hdr_type: str | None = None,
    sources: list[str] | None = None,
) -> Resource:
    return Resource(
        resources=ResourceSearchResult(
            id=title,
            title=title,
            site="test",
            category="tv",
            size=size,
            seeders=seeders,
            leechers=0,
            publish_date=datetime.now(UTC),
            download_url=f"https://example.com/{title}",
            result_id=title,
            matched_by_id=True,
        ),
        attrs=ResourceAttributes(
            title=title,
            seasons=[1],
            episodes=episodes or [],
            resolution=resolution,
            hdr_type=hdr_type,
            sources=sources or ["WEB-DL"],
        ),
    )


@pytest.mark.asyncio
async def test_pilot_can_combine_multiple_resources_to_cover_first_three_episodes(monkeypatch):
    service = SubscriptionRunApplicationService()
    resources = [
        _build_resource("pack-1-2", [1, 2], seeders=5),
        _build_resource("single-3", [3], seeders=8),
    ]

    async def fake_finalize(result, covered, payload=None):
        return object(), [], result

    monkeypatch.setattr("app.services.domain.resource.pilot_selection.finalize_pilot_resource", fake_finalize)
    monkeypatch.setattr(
        "app.services.domain.resource.pilot_selection.compute_preference_score",
        lambda result, filters: (10 if result.resources.title == "pack-1-2" else 9, None),
    )

    selected = await select_pilot_resources(
        resources,
        target_episodes={1, 2, 3},
    )

    assert selected is not None
    assert [item[2].resources.title for item in selected] == ["pack-1-2", "single-3"]


@pytest.mark.asyncio
async def test_pilot_prefers_higher_quality_combo_over_lower_quality_full_pack(monkeypatch):
    service = SubscriptionRunApplicationService()
    resources = [
        _build_resource("full-low", [1, 2, 3], seeders=20),
        _build_resource("pack-high-1-2", [1, 2], seeders=8),
        _build_resource("single-high-3", [3], seeders=8),
    ]

    async def fake_finalize(result, covered, payload=None):
        return object(), [], result

    def fake_score(result, filters):
        mapping = {
            "full-low": 5,
            "pack-high-1-2": 20,
            "single-high-3": 20,
        }
        return mapping[result.resources.title], None

    monkeypatch.setattr("app.services.domain.resource.pilot_selection.finalize_pilot_resource", fake_finalize)
    monkeypatch.setattr(
        "app.services.domain.resource.pilot_selection.compute_preference_score",
        fake_score,
    )

    selected = await select_pilot_resources(
        resources,
        target_episodes={1, 2, 3},
    )

    assert selected is not None
    assert [item[2].resources.title for item in selected] == ["pack-high-1-2", "single-high-3"]


@pytest.mark.asyncio
async def test_pilot_does_not_fetch_payload_during_selection_for_attrless_candidates(monkeypatch):
    service = SubscriptionRunApplicationService()
    resources = [
        _build_resource("full-unknown", None, seeders=20),
    ]

    async def fake_finalize(result, covered, payload=None):
        return object(), [], result

    async def fail_fetch_payload(_url):
        raise AssertionError("selection should not fetch payload for attrless pilot candidates")

    monkeypatch.setattr("app.services.domain.resource.pilot_selection.finalize_pilot_resource", fake_finalize)
    monkeypatch.setattr(
        "app.services.domain.resource.pilot_selection.fetch_torrent_payload",
        fail_fetch_payload,
    )

    selected = await select_pilot_resources(
        resources,
        target_episodes={1, 2, 3},
    )

    assert selected is not None
    assert [item[2].resources.title for item in selected] == ["full-unknown"]


@pytest.mark.asyncio
async def test_pilot_prefers_better_builtin_quality_before_seeders(monkeypatch):
    service = SubscriptionRunApplicationService()
    resources = [
        _build_resource("hdr-pack", [1, 2, 3], seeders=50, hdr_type="HDR10"),
        _build_resource("dv-pack", [1, 2, 3], seeders=5, hdr_type="Dolby Vision"),
    ]

    async def fake_finalize(result, covered, payload=None):
        return object(), [], result

    monkeypatch.setattr("app.services.domain.resource.pilot_selection.finalize_pilot_resource", fake_finalize)

    selected = await select_pilot_resources(
        resources,
        quality_profile=None,
        target_episodes={1, 2, 3},
    )

    assert selected is not None
    assert [item[2].resources.title for item in selected] == ["dv-pack"]


@pytest.mark.drift
@pytest.mark.asyncio
async def test_pilot_selection_skips_title_detected_disc_package(monkeypatch):
    service = SubscriptionRunApplicationService()
    resource = _build_resource("Show.S01.Disc.1.of.2.1080p.BluRay.AVC.DTS-HD.MA", [], sources=["BluRay"])
    resource.attrs.resource_form = "BluRay Disc"

    async def fail_finalize(*_args, **_kwargs):
        raise AssertionError("disc package should not reach pilot finalization")

    monkeypatch.setattr("app.services.domain.resource.pilot_selection.finalize_pilot_resource", fail_finalize)

    selected = await select_pilot_resources(
        [resource],
        target_episodes={1, 2, 3},
    )

    assert selected is None


@pytest.mark.drift
@pytest.mark.asyncio
async def test_pilot_finalization_skips_torrent_confirmed_disc_package():
    resource = _build_resource("unknown-title", None, sources=["BluRay"])
    metadata = TorrentMetadata(
        hash="hash",
        name="Show.S01.Disc.1.of.2",
        size=1,
        files=[],
        attrs=ResourceAttributes(
            title="Show.S01.Disc.1.of.2",
            seasons=[1],
            episodes=[],
            resource_form="BluRay Disc",
            resource_form_evidence="torrent_structure",
            disc_number=1,
            disc_total=2,
        ),
        coverage_kind="disc_package",
    )

    finalized = await finalize_pilot_resource(resource, {1, 2, 3}, TorrentPayload(metadata=metadata, blob=b"torrent"))

    assert finalized is None


@pytest.mark.asyncio
async def test_pilot_finalization_selects_only_missing_episode_files_from_pack():
    resource = _build_resource("show-pack-1-3", [1, 2, 3])
    files = [
        SimpleNamespace(get_episodes=lambda: {1}),
        SimpleNamespace(get_episodes=lambda: {2}),
        SimpleNamespace(get_episodes=lambda: {3}),
    ]
    payload = SimpleNamespace(
        metadata=SimpleNamespace(
            attrs=None,
            files=files,
            get_episodes=lambda: {1, 2, 3},
            name="show-pack-1-3",
            size=1,
        )
    )

    finalized = await finalize_pilot_resource(resource, {1}, payload)

    assert finalized is not None
    assert finalized[1] == [0]


@pytest.mark.asyncio
async def test_subscription_prefers_better_builtin_quality_before_seeders():
    service = SubscriptionRunApplicationService()
    resources = [
        _build_resource("webrip-high-seeders", [1], seeders=50, sources=["WEBRip"]),
        _build_resource("bluray-low-seeders", [1], seeders=5, sources=["BluRay"]),
    ]

    async def fake_fetch_payload(_url):
        file_item = SimpleNamespace(get_episodes=lambda: {1})
        metadata = SimpleNamespace(files=[file_item], get_episodes=lambda: {1}, name="payload", size=1)
        return SimpleNamespace(metadata=metadata)

    from app.services.domain.resource import selection as resource_selection_module

    original_fetch = resource_selection_module.fetch_torrent_payload
    resource_selection_module.fetch_torrent_payload = fake_fetch_payload

    try:
        selected = await select_resources(
            resources,
            episodes={1},
            filters=None,
            quality_profile=None,
            required_scores={},
            episode_mode=True,
        )
    finally:
        resource_selection_module.fetch_torrent_payload = original_fetch

    assert [item[2].resources.title for item in selected] == ["bluray-low-seeders"]


@pytest.mark.asyncio
async def test_subscription_selection_filters_zero_seeders_even_when_quality_is_better(monkeypatch):
    resources = [
        _build_resource("dv-zero-seeders", [1], seeders=0, hdr_type="Dolby Vision"),
        _build_resource("hdr-seeded", [1], seeders=3, hdr_type="HDR10"),
    ]

    async def fake_fetch_payload(result):
        file_item = SimpleNamespace(get_episodes=lambda: {1})
        metadata = SimpleNamespace(files=[file_item], get_episodes=lambda: {1}, name=result.title, size=1)
        return SimpleNamespace(metadata=metadata)

    monkeypatch.setattr("app.services.domain.resource.selection.fetch_torrent_payload", fake_fetch_payload)

    selected = await select_resources(
        resources,
        episodes={1},
        filters=None,
        quality_profile=None,
        required_scores={},
        episode_mode=True,
    )

    assert [item[2].resources.title for item in selected] == ["hdr-seeded"]


@pytest.mark.asyncio
async def test_subscription_selection_prefers_seeders_over_stereo_channel_only_advantage(monkeypatch):
    resources = [
        _build_resource("longweb-stereo-low-seeders", [1], seeders=2, sources=["WEB-DL"]),
        _build_resource("adweb-unknown-channels-high-seeders", [1], seeders=20, sources=["WEB-DL"]),
    ]
    resources[0].attrs.video_codec = "HEVC"
    resources[0].attrs.audio_codec = "AAC"
    resources[0].attrs.audio_channels = "2.0"
    resources[1].attrs.video_codec = "HEVC"
    resources[1].attrs.audio_codec = "AAC"

    async def fake_fetch_payload(result):
        file_item = SimpleNamespace(get_episodes=lambda: {1})
        metadata = SimpleNamespace(files=[file_item], get_episodes=lambda: {1}, name=result.title, size=1)
        return SimpleNamespace(metadata=metadata)

    monkeypatch.setattr("app.services.domain.resource.selection.fetch_torrent_payload", fake_fetch_payload)

    selected = await select_resources(
        resources,
        episodes={1},
        filters=None,
        quality_profile=None,
        required_scores={},
        episode_mode=True,
    )

    assert [item[2].resources.title for item in selected] == ["adweb-unknown-channels-high-seeders"]


@pytest.mark.asyncio
async def test_subscription_selection_does_not_let_tiny_hdr_beat_healthy_2160p(monkeypatch):
    resources = [
        _build_resource("tiny-hdr-low-seeders", [1], seeders=2, size="2.0 GB", hdr_type="HDR10"),
        _build_resource("healthy-sdr-high-seeders", [1], seeders=20, size="8.0 GB"),
    ]
    for resource in resources:
        resource.attrs.video_codec = "HEVC"
        resource.attrs.audio_codec = "AAC"

    async def fake_fetch_payload(result):
        file_item = SimpleNamespace(get_episodes=lambda: {1})
        metadata = SimpleNamespace(files=[file_item], get_episodes=lambda: {1}, name=result.title, size=1)
        return SimpleNamespace(metadata=metadata)

    monkeypatch.setattr("app.services.domain.resource.selection.fetch_torrent_payload", fake_fetch_payload)

    selected = await select_resources(
        resources,
        episodes={1},
        filters=None,
        quality_profile=None,
        required_scores={},
        episode_mode=True,
    )

    assert [item[2].resources.title for item in selected] == ["healthy-sdr-high-seeders"]


@pytest.mark.asyncio
async def test_pilot_selection_filters_zero_seeders_even_when_quality_is_better(monkeypatch):
    resources = [
        _build_resource("dv-zero-seeders", [1, 2, 3], seeders=0, hdr_type="Dolby Vision"),
        _build_resource("hdr-seeded", [1, 2, 3], seeders=3, hdr_type="HDR10"),
    ]

    async def fake_finalize(result, covered, payload=None):
        return object(), [], result

    monkeypatch.setattr("app.services.domain.resource.pilot_selection.finalize_pilot_resource", fake_finalize)

    selected = await select_pilot_resources(resources, target_episodes={1, 2, 3})

    assert selected is not None
    assert [item[2].resources.title for item in selected] == ["hdr-seeded"]


def test_partition_search_results_filters_low_score_pack_in_consistent_skip_low_mode(monkeypatch):
    service = SubscriptionRunApplicationService()
    media = MediaExecutionSnapshot(
        media_id=MediaID.parse("tmdb:tv:123"),
        title="Test Show",
        media_type=MediaType.tv,
        year=2026,
        episodes_count=12,
        season_number=1,
    )
    plan = ResourceSelectionPlan(
        media_id=media.media_id,
        season_number=1,
        episode_mode=True,
        filters=SubscriptionFilters(
            upgrade_policy=UpgradePolicy(enabled=True, strategy="consistent_skip_low"),
        ),
        target_episodes={1, 2},
        required_scores={1: 100, 2: 100},
    )
    low_pack = ResourceSearchResult(
        id="low-pack",
        title="low-pack",
        site="test",
        category="tv",
        size="1 GB",
        seeders=10,
        leechers=0,
        publish_date=datetime.now(UTC),
        download_url="https://example.com/low-pack",
        result_id="low-pack",
        matched_by_id=True,
    )

    monkeypatch.setattr(
        "app.services.domain.resource.selection.resource_parser.parse",
        lambda title, desc="": ResourceAttributes(title=title, seasons=[1], episodes=[1, 2], sources=["WEB-DL"]),
    )
    monkeypatch.setattr(
        "app.services.domain.resource.selection.compute_preference_score",
        lambda result, quality_profile: (90, None),
    )

    standard_results, unmatched_results, has_any_id_match = partition_search_results(
        plan,
        [low_pack],
        unmatched_rules=None,
    )

    assert standard_results == []
    assert unmatched_results == []
    assert has_any_id_match is False


@pytest.mark.asyncio
async def test_select_resources_uses_quality_upgrade_score_for_required_scores(monkeypatch):
    profile = QualityProfile(name="default")
    baseline = 604090403030200
    resources = [
        _build_resource("hdr-e10", [10], hdr_type="HDR"),
        _build_resource("dv-e10", [10], hdr_type="Dolby Vision"),
    ]

    async def fake_fetch(result):
        attrs = next(resource.attrs for resource in resources if resource.resources.id == result.id)
        return TorrentPayload(
            metadata=TorrentMetadata(
                hash=f"hash-{result.id}",
                name=result.title,
                size=1,
                attrs=attrs,
                files=[
                    TorrentFileItem(
                        index=0,
                        filename=f"{result.title}.mkv",
                        size=1,
                        attrs=attrs,
                    )
                ],
            ),
            blob=b"torrent",
        )

    monkeypatch.setattr("app.services.domain.resource.selection.fetch_torrent_payload", fake_fetch)

    selected = await select_resources(
        resources,
        episodes={10},
        filters=SubscriptionFilters(upgrade_policy=UpgradePolicy(enabled=True, strategy="consistent_skip_low")),
        quality_profile=profile,
        required_scores={10: baseline},
        episode_mode=True,
    )

    assert [item[2].resources.title for item in selected] == ["dv-e10"]


@pytest.mark.asyncio
async def test_run_plan_uses_quality_profile_from_filter_config_when_subscription_does_not_override(monkeypatch):
    service = SubscriptionRunApplicationService()
    media = MediaExecutionSnapshot(
        media_id=MediaID.parse("tmdb:tv:123"),
        title="Test Show",
        media_type=MediaType.tv,
        year=2026,
        episodes_count=12,
        season_number=1,
    )
    filters = SubscriptionFilters()
    quality_profile = QualityProfile(id="qp-from-filter", name="From Filter")
    subscription = Subscription(
        active=True,
        directory_id="dir-1",
        quality_profile_id=None,
        filter_config_id="filter-1",
        filters=SubscriptionFilters(),
        sub_id="sub-1",
        media_id=media.media_id,
        media=media,
        season_number=1,
        sites=[],
    )

    monkeypatch.setattr(
        "app.services.domain.subscription.policy.settings_service.get_quality_profile",
        lambda profile_id: quality_profile if profile_id == "qp-from-filter" else None,
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.policy.settings_service.get_default_quality_profile",
        lambda: QualityProfile(id="default-quality-profile", name="Default"),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.policy.settings_service.get_filter",
        lambda filter_id: SimpleNamespace(filters=filters, quality_profile_id="qp-from-filter") if filter_id == "filter-1" else None,
    )

    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.library_service.get_present_episodes",
        AsyncMock(return_value=set()),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.download_service.list_active_episodes_by_media",
        AsyncMock(return_value=set()),
    )

    plan = ((await resource_run_plan_service.build_subscription_plan(subscription)).plan)

    assert plan is not None
    assert plan.filters is filters
    assert plan.quality_profile is quality_profile
    assert plan.target_episodes == set(range(1, 13))


@pytest.mark.asyncio
async def test_run_plan_preserves_custom_filter_override_when_filter_config_is_present(monkeypatch):
    service = SubscriptionRunApplicationService()
    media = MediaExecutionSnapshot(
        media_id=MediaID.parse("tmdb:tv:123"),
        title="Test Show",
        media_type=MediaType.tv,
        year=2026,
        episodes_count=12,
        season_number=1,
    )
    custom_filters = SubscriptionFilters(resolution=["1080p"])
    preset_filters = SubscriptionFilters(resolution=["2160p"])
    subscription = Subscription(
        active=True,
        directory_id="dir-1",
        quality_profile_id=None,
        filter_config_id="filter-1",
        filters=custom_filters,
        sub_id="sub-1",
        media_id=media.media_id,
        media=media,
        season_number=1,
        sites=[],
    )

    monkeypatch.setattr(
        "app.services.domain.subscription.policy.settings_service.get_quality_profile",
        lambda profile_id: None,
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.policy.settings_service.get_default_quality_profile",
        lambda: QualityProfile(id="default-quality-profile", name="Default"),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.policy.settings_service.get_filter",
        lambda filter_id: SimpleNamespace(filters=preset_filters, quality_profile_id=None) if filter_id == "filter-1" else None,
    )

    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.library_service.get_present_episodes",
        AsyncMock(return_value=set()),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.resource_run_plan_service.download_service.list_active_episodes_by_media",
        AsyncMock(return_value=set()),
    )

    plan = ((await resource_run_plan_service.build_subscription_plan(subscription)).plan)

    assert plan is not None
    assert plan.filters is custom_filters
    assert plan.target_episodes == set(range(1, 13))


@pytest.mark.asyncio
async def test_execute_pilot_episode_fills_missing_tv_episode_count(monkeypatch):
    service = SubscriptionRunApplicationService()
    media = MediaExecutionSnapshot(
        media_id=MediaID.parse("tmdb:tv:123"),
        title="Test Show",
        year=2026,
        season_number=1,
    )
    media_detail = MediaFullInfo(
        media_id=media.media_id,
        title="Test Show",
        year=2026,
        media_type=MediaType.tv,
        seasons=[MediaSeasonInfo(season_number=1, episode_count=2)],
    )
    resource = Resource(
        resources=ResourceSearchResult(
            id="show-pack",
            title="show-pack",
            site="test",
            category="tv",
            size="1 GB",
            seeders=10,
            leechers=0,
            publish_date=datetime.now(UTC),
            download_url="https://example.com/show-pack",
            result_id="show-pack",
            matched_by_id=True,
        ),
        attrs=ResourceAttributes(
            title="show-pack",
            seasons=[1],
            episodes=[1, 2],
            resolution="1080p",
            sources=["WEB-DL"],
        ),
    )
    payload = SimpleNamespace(metadata=SimpleNamespace(files=[], get_episodes=lambda: {1, 2}, size=1))

    class _Lock:
        async def __aenter__(self):
            return True

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.domain_lock_service.acquire_media_acquire",
        lambda _media_id: _Lock(),
    )
    monkeypatch.setattr(
        "app.services.domain.media.media_service.execution_snapshot_service.profile_service.cached_info",
        AsyncMock(return_value=media_detail),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.settings_service.get_default_quality_profile",
        lambda: QualityProfile(id="qp-default", name="Default"),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.library_service.get_present_episodes",
        AsyncMock(return_value=set()),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.download_service.list_active_episodes_by_media",
        AsyncMock(return_value=set()),
    )
    search_media = AsyncMock(return_value=[resource.resources])
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.resource_search_service.search_media",
        search_media,
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.partition_search_results",
        lambda plan, search_results, unmatched_rules=None: ([resource], [], True),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.select_pilot_resources",
        AsyncMock(return_value=[(payload, [], resource)]),
    )
    create_download_mock = AsyncMock(return_value=SimpleNamespace(id="task-1"))
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.download_service.create_download",
        create_download_mock,
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.media_service.upsert_active_profile_from_identity",
        AsyncMock(),
    )

    created = await pilot_download_application_service.execute(
        media=media,
        season_number=1,
    )

    assert created == 1
    assert search_media.await_args.args[0].media.episodes_count == 2
    create_download_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_pilot_episode_targets_only_missing_prefix_episodes(monkeypatch):
    media = MediaExecutionSnapshot(
        media_id=MediaID.parse("tmdb:tv:123"),
        title="Test Show",
        year=2026,
        media_type=MediaType.tv,
        season_number=1,
        episodes_count=12,
    )
    resource = _build_resource("show-pack-1-3", [1, 2, 3])
    payload = SimpleNamespace(metadata=SimpleNamespace(files=[], get_episodes=lambda: {1, 2, 3}, size=1))

    class _Lock:
        async def __aenter__(self):
            return True

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.domain_lock_service.acquire_media_acquire",
        lambda _media_id: _Lock(),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.settings_service.get_default_quality_profile",
        lambda: QualityProfile(id="qp-default", name="Default"),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.library_service.get_present_episodes",
        AsyncMock(return_value={2, 3}),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.download_service.list_active_episodes_by_media",
        AsyncMock(return_value=set()),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.resource_search_service.search_media",
        AsyncMock(return_value=[resource.resources]),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.partition_search_results",
        lambda plan, search_results, unmatched_rules=None: ([resource], [], True),
    )
    select_pilot = AsyncMock(return_value=[(payload, [], resource)])
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.select_pilot_resources",
        select_pilot,
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.download_service.create_download",
        AsyncMock(return_value=SimpleNamespace(id="task-1")),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.media_service.upsert_active_profile_from_identity",
        AsyncMock(),
    )

    created = await pilot_download_application_service.execute(
        media=media,
        season_number=1,
    )

    assert created == 1
    assert select_pilot.await_args.kwargs["target_episodes"] == {1}


@pytest.mark.asyncio
async def test_execute_pilot_episode_uses_effective_download_config(monkeypatch):
    media = MediaExecutionSnapshot(
        media_id=MediaID.parse("tmdb:tv:287641"),
        title="Dazzling",
        year=2026,
        media_type=MediaType.tv,
        season_number=1,
        episodes_count=30,
    )
    resource = _build_resource("Dazzling S01E01-E03 2160p WEB-DL", [1, 2, 3])
    payload = SimpleNamespace(metadata=SimpleNamespace(files=[], get_episodes=lambda: {1, 2, 3}, size=1))
    effective_filters = SubscriptionFilters(resolution=["2160p"], exclude_keywords=["去头尾"])
    effective_quality = QualityProfile(id="qp-effective", name="Effective")
    effective_rule = SubscriptionUnmatchedRule(sites=["site-effective"], pattern="Dazzling S01")

    class _Lock:
        async def __aenter__(self):
            return True

        async def __aexit__(self, exc_type, exc, tb):
            return False

    async def fake_resolve_effective_config(media_id, media_type, *, season_number=None):
        assert media_id == media.media_id
        assert media_type == MediaType.tv
        assert season_number == 1
        return SimpleNamespace(
            directory_id="tv-default",
            filters=effective_filters,
            quality_profile_id=effective_quality.id,
            quality_profile=effective_quality,
            sites=["site-effective"],
            unmatched_rules=[effective_rule],
        )

    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.subscription_download_config_service.resolve_effective_config",
        fake_resolve_effective_config,
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.domain_lock_service.acquire_media_acquire",
        lambda _media_id: _Lock(),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.settings_service.get_quality_profile",
        lambda profile_id: effective_quality if profile_id == effective_quality.id else None,
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.library_service.get_present_episodes",
        AsyncMock(return_value=set()),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.download_service.list_active_episodes_by_media",
        AsyncMock(return_value=set()),
    )
    search_media = AsyncMock(return_value=[resource.resources])
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.resource_search_service.search_media",
        search_media,
    )

    captured = {}

    def fake_partition(plan, search_results, unmatched_rules=None):
        captured["plan"] = plan
        captured["unmatched_rules"] = unmatched_rules
        return [resource], [], True

    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.partition_search_results",
        fake_partition,
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.select_pilot_resources",
        AsyncMock(return_value=[(payload, [], resource)]),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.download_service.create_download",
        AsyncMock(return_value=SimpleNamespace(id="task-1")),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.media_service.upsert_active_profile_from_identity",
        AsyncMock(),
    )

    created = await pilot_download_application_service.execute(
        media=media,
        season_number=1,
    )

    assert created == 1
    assert search_media.await_args.args[0].indexers == ["site-effective"]
    assert captured["plan"].filters is effective_filters
    assert captured["plan"].quality_profile is effective_quality
    assert captured["unmatched_rules"] == [effective_rule]


@pytest.mark.asyncio
async def test_execute_pilot_episode_supports_movie_quick_download(monkeypatch):
    service = SubscriptionRunApplicationService()
    media = MediaExecutionSnapshot(media_id=MediaID.parse("tmdb:movie:1"), title="Test Movie", year=2024)
    movie_info = MediaExecutionSnapshot(
        media_id=media.media_id,
        title="Test Movie",
        media_type=MediaType.movie,
        year=2024,
    )
    resource = Resource(
        resources=ResourceSearchResult(
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
        ),
        attrs=ResourceAttributes(
            title="movie-pack",
            episodes=[],
            resolution="2160p",
            sources=["BluRay"],
        ),
    )
    payload = SimpleNamespace(metadata=SimpleNamespace(files=[], get_episodes=lambda: set(), size=1))

    class _Lock:
        async def __aenter__(self):
            return True

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.domain_lock_service.acquire_media_acquire",
        lambda _media_id: _Lock(),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.media_service.simple_info",
        AsyncMock(return_value=movie_info),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.settings_service.get_default_quality_profile",
        lambda: QualityProfile(id="qp-default", name="Default"),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.resource_search_service.search_media",
        AsyncMock(return_value=[resource.resources]),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.partition_search_results",
        lambda plan, search_results, unmatched_rules=None: ([resource], [], True),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.select_download_resources",
        AsyncMock(return_value=[(payload, [], resource)]),
    )
    create_download_mock = AsyncMock(return_value=SimpleNamespace(id="task-1"))
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.download_service.create_download",
        create_download_mock,
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.media_service.upsert_active_profile_from_identity",
        AsyncMock(),
    )

    created = await pilot_download_application_service.execute(
        media=media,
    )

    assert created == 1
    create_download_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_pilot_episode_rejects_movie_when_already_in_library(monkeypatch):
    service = SubscriptionRunApplicationService()
    media = MediaExecutionSnapshot(media_id=MediaID.parse("tmdb:movie:2"), title="Existing Movie", year=2024)
    movie_info = MediaExecutionSnapshot(
        media_id=media.media_id,
        title="Existing Movie",
        media_type=MediaType.movie,
        year=2024,
    )

    class _Lock:
        async def __aenter__(self):
            return True

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.domain_lock_service.acquire_media_acquire",
        lambda _media_id: _Lock(),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.media_service.simple_info",
        AsyncMock(return_value=movie_info),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.library_service.get_files_by_media",
        AsyncMock(return_value=[object()]),
    )

    with pytest.raises(DownloadException) as exc_info:
        await pilot_download_application_service.execute(
            media=media,
        )
    assert exc_info.value.message_key == "backendErrors.movieAlreadyInLibrary"


@pytest.mark.asyncio
async def test_execute_pilot_episode_rejects_movie_when_already_downloading(monkeypatch):
    service = SubscriptionRunApplicationService()
    media = MediaExecutionSnapshot(media_id=MediaID.parse("tmdb:movie:3"), title="Downloading Movie", year=2024)
    movie_info = MediaExecutionSnapshot(
        media_id=media.media_id,
        title="Downloading Movie",
        media_type=MediaType.movie,
        year=2024,
    )

    class _Lock:
        async def __aenter__(self):
            return True

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.domain_lock_service.acquire_media_acquire",
        lambda _media_id: _Lock(),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.media_service.simple_info",
        AsyncMock(return_value=movie_info),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.library_service.get_files_by_media",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.subscription.pilot.download_service.get_tasks",
        AsyncMock(return_value=[object()]),
    )

    with pytest.raises(DownloadException) as exc_info:
        await pilot_download_application_service.execute(
            media=media,
        )
    assert exc_info.value.message_key == "backendErrors.movieAlreadyDownloading"


@pytest.mark.asyncio
async def test_tv_disc_package_requires_explicit_resource_form_filter(monkeypatch):
    resource = _build_resource(
        "Show.S01.Disc.1.of.2.1080p.BluRay.AVC.DTS-HD.MA",
        [],
        sources=["BluRay"],
    )
    metadata = TorrentMetadata(
        hash="hash",
        name=resource.resources.title,
        size=1,
        files=[],
        attrs=ResourceAttributes(
            title=resource.resources.title,
            seasons=[1],
            episodes=[],
            sources=["BluRay"],
            resource_form="BluRay Disc",
            disc_number=1,
            disc_total=2,
        ),
        coverage_kind="disc_package",
    )

    async def fake_fetch_payload(_result):
        return TorrentPayload(metadata=metadata, blob=b"torrent")

    monkeypatch.setattr(
        "app.services.domain.resource.selection.fetch_torrent_payload",
        fake_fetch_payload,
    )

    selected_without_filter = await select_resources(
        [resource],
        episodes={1, 2, 3},
        filters=None,
        episode_mode=True,
    )
    selected_with_filter = await select_resources(
        [resource],
        episodes={1, 2, 3},
        filters=SubscriptionFilters(resource_kind=["original_disc"], resource_form=["BluRay Disc"]),
        episode_mode=True,
    )

    assert selected_without_filter == []
    assert len(selected_with_filter) == 1
    assert selected_with_filter[0][1] == []
