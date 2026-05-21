from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.api.v1.subscription.state import get_subscription_state, put_subscription_state
from app.schemas.domain.media_subscription_state import (
    MediaSubscriptionState,
    MediaSubscriptionStateView,
    SubscriptionMode,
    SubscriptionStateUpdateRequest,
    SubscriptionTargetFilterMode,
)
from app.schemas.domain.subscription_filters import SubscriptionFilters, UpgradePolicy
from app.schemas.media_id import MediaID
from app.schemas.runtime.subscription_lifecycle import SubscriptionChange


def _change(view: MediaSubscriptionStateView) -> SubscriptionChange:
    return SubscriptionChange(view=view)


@pytest.mark.asyncio
async def test_get_subscription_state_uses_query_service(monkeypatch):
    mid = MediaID.parse("tmdb:tv:1")
    get_current = AsyncMock(
        return_value=MediaSubscriptionStateView(
            sub_id="sub-1",
            media_id=mid,
            season_number=1,
            active=True,
            followed=True,
            subscription_mode=SubscriptionMode.CURRENT_AIRED_COMPLETE,
        )
    )
    monkeypatch.setattr("app.api.v1.subscription.state.subscription_query_service.get_current", get_current)

    response = await get_subscription_state(mid=mid, season_number=1)

    assert response.data.subscription_mode == SubscriptionMode.CURRENT_AIRED_COMPLETE
    target = get_current.await_args.args[0]
    assert target.media_id == mid
    assert target.season_number == 1


@pytest.mark.asyncio
async def test_put_subscription_state_builds_command_from_request(monkeypatch):
    mid = MediaID.parse("tmdb:tv:2")
    get_state = AsyncMock(return_value=None)
    set_state = AsyncMock(
        return_value=_change(
            MediaSubscriptionStateView(
                media_id=mid,
                season_number=1,
                active=True,
                followed=True,
                subscription_mode=SubscriptionMode.CURRENT_AIRED_COMPLETE,
            )
        )
    )
    monkeypatch.setattr("app.api.v1.subscription.state.subscription_query_service.get_state", get_state)
    monkeypatch.setattr("app.api.v1.subscription.state.subscription_command_service.set_subscription_state", set_state)

    response = await put_subscription_state(
        SubscriptionStateUpdateRequest(
            active=True,
            followed=True,
            subscription_mode=SubscriptionMode.CURRENT_AIRED_COMPLETE,
        ),
        mid=mid,
        season_number=1,
    )

    assert response.data.active is True
    target, command = set_state.await_args.args
    assert target.media_id == mid
    assert target.season_number == 1
    assert command.active is True
    assert command.followed is True
    assert command.subscription_mode == SubscriptionMode.CURRENT_AIRED_COMPLETE
    assert command.upgrade_policy is None
    assert command.media is None


@pytest.mark.asyncio
async def test_put_subscription_state_preserves_existing_target_filters_when_request_omits_them(monkeypatch):
    mid = MediaID.parse("tmdb:tv:3")
    existing = MediaSubscriptionState(
        sub_id="sub-1",
        media_id=mid,
        season_number=1,
        active=True,
        followed=True,
        subscription_mode=SubscriptionMode.UPGRADE_CONTINUOUS,
        upgrade_policy=UpgradePolicy(enabled=True),
        target_filters=SubscriptionFilters(resolution=["2160p"]),
        target_filter_config_id="filter-1",
    )
    monkeypatch.setattr("app.api.v1.subscription.state.subscription_query_service.get_state", AsyncMock(return_value=existing))
    set_state = AsyncMock(return_value=_change(MediaSubscriptionStateView(media_id=mid, season_number=1)))
    monkeypatch.setattr("app.api.v1.subscription.state.subscription_command_service.set_subscription_state", set_state)

    await put_subscription_state(
        SubscriptionStateUpdateRequest(
            active=True,
            followed=False,
            subscription_mode=SubscriptionMode.UPGRADE_CONTINUOUS,
        ),
        mid=mid,
        season_number=1,
    )

    command = set_state.await_args.args[1]
    assert command.target_filters == existing.target_filters
    assert command.target_filter_config_id == "filter-1"


@pytest.mark.asyncio
async def test_put_subscription_state_clears_target_filters_when_switching_to_preset_only(monkeypatch):
    mid = MediaID.parse("tmdb:tv:4")
    existing = MediaSubscriptionState(
        sub_id="sub-1",
        media_id=mid,
        season_number=1,
        active=True,
        followed=True,
        subscription_mode=SubscriptionMode.UPGRADE_CONTINUOUS,
        upgrade_policy=UpgradePolicy(enabled=True),
        target_filters=SubscriptionFilters(resolution=["2160p"]),
        target_filter_config_id="filter-old",
    )
    monkeypatch.setattr("app.api.v1.subscription.state.subscription_query_service.get_state", AsyncMock(return_value=existing))
    set_state = AsyncMock(return_value=_change(MediaSubscriptionStateView(media_id=mid, season_number=1)))
    monkeypatch.setattr("app.api.v1.subscription.state.subscription_command_service.set_subscription_state", set_state)

    await put_subscription_state(
        SubscriptionStateUpdateRequest(
            active=True,
            followed=True,
            subscription_mode=SubscriptionMode.UPGRADE_CONTINUOUS,
            target_filter_mode=SubscriptionTargetFilterMode.PRESET,
            target_filter_config_id="filter-new",
        ),
        mid=mid,
        season_number=1,
    )

    command = set_state.await_args.args[1]
    assert command.target_filters is None
    assert command.target_filter_config_id == "filter-new"


@pytest.mark.asyncio
async def test_put_subscription_state_supports_target_preset_override_mode(monkeypatch):
    mid = MediaID.parse("tmdb:tv:5")
    existing = MediaSubscriptionState(
        sub_id="sub-1",
        media_id=mid,
        season_number=1,
        active=True,
        followed=True,
        subscription_mode=SubscriptionMode.UPGRADE_CONTINUOUS,
        upgrade_policy=UpgradePolicy(enabled=True),
    )
    monkeypatch.setattr("app.api.v1.subscription.state.subscription_query_service.get_state", AsyncMock(return_value=existing))
    set_state = AsyncMock(return_value=_change(MediaSubscriptionStateView(media_id=mid, season_number=1)))
    monkeypatch.setattr("app.api.v1.subscription.state.subscription_command_service.set_subscription_state", set_state)

    await put_subscription_state(
        SubscriptionStateUpdateRequest(
            active=True,
            followed=True,
            subscription_mode=SubscriptionMode.UPGRADE_CONTINUOUS,
            target_filter_mode=SubscriptionTargetFilterMode.PRESET_OVERRIDE,
            target_filter_config_id="filter-new",
            target_filters=SubscriptionFilters(resolution=["2160p"]),
        ),
        mid=mid,
        season_number=1,
    )

    command = set_state.await_args.args[1]
    assert command.target_filters == SubscriptionFilters(resolution=["2160p"])
    assert command.target_filter_config_id == "filter-new"


def test_subscription_state_request_requires_explicit_target_filter_mode_for_preset_update():
    with pytest.raises(ValidationError, match="target_filter_mode is required"):
        SubscriptionStateUpdateRequest(
            active=True,
            followed=True,
            subscription_mode=SubscriptionMode.UPGRADE_CONTINUOUS,
            target_filter_config_id="filter-new",
        )


def test_subscription_state_request_requires_explicit_target_filter_mode_for_custom_update():
    with pytest.raises(ValidationError, match="target_filter_mode is required"):
        SubscriptionStateUpdateRequest(
            active=True,
            followed=True,
            subscription_mode=SubscriptionMode.UPGRADE_CONTINUOUS,
            target_filters=SubscriptionFilters(resolution=["2160p"]),
        )
