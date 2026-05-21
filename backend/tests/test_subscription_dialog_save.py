from unittest.mock import AsyncMock, Mock

import pytest

from types import SimpleNamespace

from app.services.domain.subscription.command_service import SubscriptionCommandService
from app.schemas.domain.media import MediaExecutionSnapshot, MediaTarget
from app.schemas.domain.media_subscription_cycle import MediaSubscriptionCycle
from app.schemas.domain.media_subscription_settings import MediaSubscriptionSettings
from app.schemas.domain.media_subscription_state import MediaSubscriptionStateView, SubscriptionEndReason, SubscriptionEndTrigger, SubscriptionMode
from app.schemas.domain.subscription_filters import SubscriptionFilters, UpgradePolicy
from app.schemas.exception import DownloadException
from app.schemas.domain.media_subscription_state import MediaSubscriptionState
from app.schemas.media_id import MediaID


def _state(*, active: bool, followed: bool) -> MediaSubscriptionState:
    return MediaSubscriptionState(
        sub_id="sub-1",
        media_id=MediaID.parse("tmdb:tv:1"),
        active=active,
        followed=followed,
    )


def _media_snapshot(media_id: str = "tmdb:tv:1", season_number: int | None = 1) -> MediaExecutionSnapshot:
    return MediaExecutionSnapshot(
        media_id=MediaID.parse(media_id),
        season_number=season_number,
        title="Test Media",
        year=2024,
    )


def _view() -> MediaSubscriptionStateView:
    return MediaSubscriptionStateView(media_id=MediaID.parse("tmdb:tv:1"), season_number=1)


def test_validate_media_snapshot_target_rejects_mismatched_media_id():
    with pytest.raises(DownloadException, match="Sample"):
        SubscriptionCommandService.validate_media_snapshot_target(
            _media_snapshot(media_id="tmdb:tv:2"),
            MediaID.parse("tmdb:tv:1"),
            1,
        )


def test_validate_media_snapshot_target_rejects_mismatched_season_number():
    with pytest.raises(DownloadException, match="Sample"):
        SubscriptionCommandService.validate_media_snapshot_target(
            _media_snapshot(season_number=1),
            MediaID.parse("tmdb:tv:1"),
            2,
        )


def test_validate_media_snapshot_target_accepts_movie_without_season_number():
    SubscriptionCommandService.validate_media_snapshot_target(
        _media_snapshot(media_id="tmdb:movie:1", season_number=None),
        MediaID.parse("tmdb:movie:1"),
        None,
    )


@pytest.mark.asyncio
async def test_emit_post_save_events_manual_end_only_emits_ended_event(monkeypatch):
    previous = _state(active=True, followed=True)
    current = _state(active=False, followed=True)

    change = SubscriptionCommandService._build_change(previous, current, _view(), ended_cycle=True)

    assert len(change.events) == 1
    assert change.events[0].reason == SubscriptionEndReason.MANUAL
    assert change.events[0].trigger == SubscriptionEndTrigger.MANUAL


@pytest.mark.asyncio
async def test_emit_post_save_events_manual_end_still_emits_follow_change(monkeypatch):
    previous = _state(active=True, followed=True)
    current = _state(active=False, followed=False)

    change = SubscriptionCommandService._build_change(previous, current, _view(), ended_cycle=True)

    assert len(change.events) == 2
    assert change.events[0].reason == SubscriptionEndReason.MANUAL
    assert change.events[1].type.value == "follow_disabled"


@pytest.mark.asyncio
async def test_validate_activation_directory_uses_resolved_default_directory_when_request_is_empty(monkeypatch):
    mid = MediaID.parse("tmdb:tv:1")
    get_default_directory = Mock(return_value=SimpleNamespace(id="tv-default"))
    validate_subscription_directory = Mock()
    monkeypatch.setattr(
        "app.services.domain.subscription.command_service.subscription_download_config_service.get_default_directory",
        get_default_directory,
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.command_service.directory_service.validate_subscription_directory",
        validate_subscription_directory,
    )

    await SubscriptionCommandService()._validate_activation_directory(MediaTarget(media_id=mid, season_number=1), None)

    get_default_directory.assert_called_once_with(mid.media_type)
    validate_subscription_directory.assert_called_once_with("tv-default")


@pytest.mark.asyncio
async def test_validate_activation_directory_rejects_empty_request_when_no_default_directory(monkeypatch):
    mid = MediaID.parse("tmdb:tv:1")
    get_default_directory = Mock(return_value=None)
    monkeypatch.setattr(
        "app.services.domain.subscription.command_service.subscription_download_config_service.get_default_directory",
        get_default_directory,
    )

    def _raise_configuration(directory_id):
        from app.schemas.exception import ConfigurationException

        raise ConfigurationException("backendErrors.config.directoryIdRequired", params={"id": directory_id})

    monkeypatch.setattr(
        "app.services.domain.subscription.command_service.directory_service.validate_subscription_directory",
        _raise_configuration,
    )

    with pytest.raises(DownloadException) as exc_info:
        await SubscriptionCommandService()._validate_activation_directory(MediaTarget(media_id=mid, season_number=1), None)

    assert exc_info.value.message_key == "backendErrors.subscriptionCommandFailed"
    assert exc_info.value.params == {
        "reason_key": "backendErrors.config.directoryIdRequired",
        "reason_params": {"id": None},
    }
    get_default_directory.assert_called_once_with(mid.media_type)


@pytest.mark.asyncio
async def test_ensure_active_profile_for_followed_subscription_state(monkeypatch):
    activate_existing_profile = AsyncMock()
    monkeypatch.setattr(
        "app.services.domain.media.media_service.activate_existing_profile",
        activate_existing_profile,
    )
    state = _state(active=False, followed=True)

    await SubscriptionCommandService._ensure_active_profile(state)

    activate_existing_profile.assert_awaited_once_with(state.media_id)


@pytest.mark.asyncio
async def test_ensure_active_profile_skips_unmanaged_subscription_state(monkeypatch):
    activate_existing_profile = AsyncMock()
    monkeypatch.setattr(
        "app.services.domain.media.media_service.activate_existing_profile",
        activate_existing_profile,
    )

    await SubscriptionCommandService._ensure_active_profile(_state(active=False, followed=False))

    activate_existing_profile.assert_not_awaited()


def test_normalize_filters_strips_embedded_upgrade_policy():
    filters = SubscriptionFilters(
        resolution=["1080p"],
        upgrade_policy=UpgradePolicy(enabled=True),
    )

    normalized = SubscriptionCommandService.normalize_filters(filters)

    assert normalized is not None
    assert normalized.resolution == ["1080p"]
    assert normalized.upgrade_policy is None


def test_should_clear_upgrade_snapshot_when_existing_snapshot_has_no_fingerprint():
    mid = MediaID.parse("tmdb:tv:1")
    next_fingerprint = MediaSubscriptionSettings(
        media_id=mid,
        season_number=1,
        sub_id="sub-1",
        followed=True,
        subscription_mode=SubscriptionMode.UPGRADE_CONTINUOUS,
        upgrade_policy=UpgradePolicy(enabled=True),
        target_filters=None,
        target_filter_config_id=None,
        directory_id="dir-1",
        filter_config_id=None,
        quality_profile_id=None,
        filters=None,
        sites=["site-a"],
        unmatched_rules=[],
    ).compute_config_fingerprint()
    cycle = MediaSubscriptionCycle(
        cycle_id="cycle-1",
        media_id=mid,
        sub_id="sub-1",
        status="active",
        started_at=1.0,
        completion_snapshot={"season_number": 1, "baseline_score": 100, "baseline_episode_upper_bound": 4},
        config_fingerprint="old-fingerprint",
        created_at=1.0,
        updated_at=1.0,
    )

    should_clear = SubscriptionCommandService.should_clear_upgrade_snapshot(
        previous_active=True,
        next_active=True,
        existing_upgrade_policy=UpgradePolicy(enabled=True),
        next_upgrade_policy=UpgradePolicy(enabled=True),
        active_cycle=cycle,
        next_config_fingerprint=next_fingerprint,
    )

    assert should_clear is True


def test_should_clear_upgrade_snapshot_when_upgrade_config_fingerprint_changes():
    mid = MediaID.parse("tmdb:tv:1")
    old_fingerprint = MediaSubscriptionSettings(
        media_id=mid,
        season_number=1,
        sub_id="sub-1",
        followed=True,
        subscription_mode=SubscriptionMode.UPGRADE_CONTINUOUS,
        upgrade_policy=UpgradePolicy(enabled=True, min_upgrade_score_delta=0),
        target_filters=None,
        target_filter_config_id=None,
        directory_id="dir-1",
        filter_config_id=None,
        quality_profile_id=None,
        filters=None,
        sites=["site-a"],
        unmatched_rules=[],
    ).compute_config_fingerprint()
    next_fingerprint = MediaSubscriptionSettings(
        media_id=mid,
        season_number=1,
        sub_id="sub-1",
        followed=True,
        subscription_mode=SubscriptionMode.UPGRADE_CONTINUOUS,
        upgrade_policy=UpgradePolicy(enabled=True, min_upgrade_score_delta=12),
        target_filters=None,
        target_filter_config_id=None,
        directory_id="dir-1",
        filter_config_id=None,
        quality_profile_id=None,
        filters=None,
        sites=["site-a"],
        unmatched_rules=[],
    ).compute_config_fingerprint()
    cycle = MediaSubscriptionCycle(
        cycle_id="cycle-1",
        media_id=mid,
        sub_id="sub-1",
        status="active",
        started_at=1.0,
        completion_snapshot={
            "season_number": 1,
            "baseline_score": 100,
            "baseline_episode_upper_bound": 4,
            "config_fingerprint": old_fingerprint,
        },
        config_fingerprint=old_fingerprint,
        created_at=1.0,
        updated_at=1.0,
    )

    should_clear = SubscriptionCommandService.should_clear_upgrade_snapshot(
        previous_active=True,
        next_active=True,
        existing_upgrade_policy=UpgradePolicy(enabled=True, min_upgrade_score_delta=0),
        next_upgrade_policy=UpgradePolicy(enabled=True, min_upgrade_score_delta=12),
        active_cycle=cycle,
        next_config_fingerprint=next_fingerprint,
    )

    assert should_clear is True
