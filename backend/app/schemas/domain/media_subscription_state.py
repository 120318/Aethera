from __future__ import annotations

import time
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.domain.media import MediaExecutionSnapshot
from app.schemas.domain.subscription import SubscriptionSearchWarning
from app.schemas.domain.subscription_filters import SubscriptionFilters, UpgradePolicy
from app.schemas.media_id import MediaID


class UpgradeCompletionSnapshot(BaseModel):
    season_number: int
    baseline_score: int
    baseline_episode_upper_bound: int
    config_fingerprint: str | None = None
    captured_at: float = Field(default_factory=lambda: time.time())


class SubscriptionEndTrigger(str, Enum):
    MANUAL = "manual"
    SYSTEM = "system"


class SubscriptionEndReason(str, Enum):
    MANUAL = "manual"
    MOVIE_LIBRARY_COMPLETED = "movie_library_completed"
    MOVIE_DOWNLOADING_COMPLETED = "movie_downloading_completed"
    MOVIE_TARGET_COMPLETED = "movie_target_completed"
    TV_COMPLETED = "tv_completed"
    TV_UPGRADE_COMPLETED = "tv_upgrade_completed"
    TV_TARGET_COMPLETED = "tv_target_completed"


class SubscriptionMode(str, Enum):
    FIRST_RELEASE = "first_release"
    CURRENT_AIRED_COMPLETE = "current_aired_complete"
    UPGRADE_CONTINUOUS = "upgrade_continuous"


class SubscriptionTargetFilterMode(str, Enum):
    PRESERVE = "preserve"
    PRESET = "preset"
    PRESET_OVERRIDE = "preset_override"
    CUSTOM = "custom"


def default_subscription_mode_for_media(media_id: MediaID) -> SubscriptionMode:
    if media_id.media_type.value == "movie":
        return SubscriptionMode.FIRST_RELEASE
    return SubscriptionMode.CURRENT_AIRED_COMPLETE


def resolve_subscription_mode(
    media_id: MediaID,
    upgrade_policy: UpgradePolicy | None,
) -> SubscriptionMode:
    if upgrade_policy and upgrade_policy.enabled:
        return SubscriptionMode.UPGRADE_CONTINUOUS
    return default_subscription_mode_for_media(media_id)


def resolve_upgrade_policy_for_mode(
    media_id: MediaID,
    mode: SubscriptionMode,
    *,
    requested_upgrade_policy: UpgradePolicy | None = None,
    existing_upgrade_policy: UpgradePolicy | None = None,
) -> UpgradePolicy | None:
    if mode != SubscriptionMode.UPGRADE_CONTINUOUS:
        return None
    if requested_upgrade_policy and requested_upgrade_policy.enabled:
        return requested_upgrade_policy
    if existing_upgrade_policy and existing_upgrade_policy.enabled:
        return existing_upgrade_policy
    if media_id.media_type.value == "movie":
        return UpgradePolicy(enabled=True)
    return UpgradePolicy(
        enabled=True,
        strategy="consistent_allow_temp",
        min_upgrade_score_delta=0,
        lock_mode="best_existing",
    )


class MediaSubscriptionState(BaseModel):
    sub_id: str
    media_id: MediaID
    media: MediaExecutionSnapshot | None = None
    season_number: int | None = None
    active: bool = False
    followed: bool = False
    subscription_mode: SubscriptionMode = SubscriptionMode.FIRST_RELEASE
    upgrade_policy: UpgradePolicy | None = None
    target_filters: SubscriptionFilters | None = None
    target_filter_config_id: str | None = None
    upgrade_completion_snapshot: UpgradeCompletionSnapshot | None = None
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())
    last_run_at: float | None = None
    follow_reminded_air_date: str | None = None
    follow_reminded_digital_release_date: str | None = None
    follow_reminded_physical_release_date: str | None = None
    follow_reminded_at: float | None = None
    follow_reminded_digital_release_at: float | None = None
    follow_reminded_physical_release_at: float | None = None
    warnings: list[SubscriptionSearchWarning] = Field(default_factory=list)


class MediaSubscriptionStatePatch(BaseModel):
    media: MediaExecutionSnapshot | None = None
    active: bool | None = None
    followed: bool | None = None
    subscription_mode: SubscriptionMode | None = None
    upgrade_policy: UpgradePolicy | None = None
    target_filters: SubscriptionFilters | None = None
    target_filter_config_id: str | None = None
    upgrade_completion_snapshot: UpgradeCompletionSnapshot | None = None
    last_run_at: float | None = None
    follow_reminded_air_date: str | None = None
    follow_reminded_digital_release_date: str | None = None
    follow_reminded_physical_release_date: str | None = None
    follow_reminded_at: float | None = None
    follow_reminded_digital_release_at: float | None = None
    follow_reminded_physical_release_at: float | None = None
    warnings: list[SubscriptionSearchWarning] | None = None


class SubscriptionStateUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active: bool
    followed: bool
    subscription_mode: SubscriptionMode | None = None
    upgrade_policy: UpgradePolicy | None = None
    target_filter_mode: SubscriptionTargetFilterMode | None = None
    target_filters: SubscriptionFilters | None = None
    target_filter_config_id: str | None = None

    @model_validator(mode="after")
    def validate_target_filter_mode(self) -> SubscriptionStateUpdateRequest:
        if self.target_filter_mode is None and (self.target_filters is not None or self.target_filter_config_id is not None):
            raise ValueError("target_filter_mode is required when updating target filters")
        return self


class MediaSubscriptionStateView(BaseModel):
    sub_id: str | None = None
    media_id: MediaID
    season_number: int | None = None
    active: bool = False
    followed: bool = False
    subscription_mode: SubscriptionMode = SubscriptionMode.FIRST_RELEASE
    upgrade_policy: UpgradePolicy | None = None
    target_filters: SubscriptionFilters | None = None
    target_filter_config_id: str | None = None
    last_run_at: float | None = None
    last_checked_at: float | None = None
    cycle_status: str | None = None
    ended_reason: SubscriptionEndReason | None = None
    ended_at: float | None = None
    warnings: list[SubscriptionSearchWarning] = Field(default_factory=list)


def resolve_view_subscription_mode(
    media_id: MediaID,
    state: MediaSubscriptionState | None,
) -> SubscriptionMode:
    if state and state.subscription_mode is not None:
        return state.subscription_mode
    return default_subscription_mode_for_media(media_id)


def resolve_target_filter_update(
    *,
    body: SubscriptionStateUpdateRequest,
    existing: MediaSubscriptionState | None,
    requested_mode: SubscriptionMode,
) -> tuple[SubscriptionFilters | None, str | None]:
    if requested_mode != SubscriptionMode.UPGRADE_CONTINUOUS:
        return None, None

    target_filter_mode = body.target_filter_mode or SubscriptionTargetFilterMode.PRESERVE
    if target_filter_mode == SubscriptionTargetFilterMode.PRESERVE:
        return (
            existing.target_filters if existing else None,
            existing.target_filter_config_id if existing else None,
        )
    if target_filter_mode == SubscriptionTargetFilterMode.PRESET:
        return None, body.target_filter_config_id
    if target_filter_mode == SubscriptionTargetFilterMode.PRESET_OVERRIDE:
        return body.target_filters, body.target_filter_config_id
    if target_filter_mode == SubscriptionTargetFilterMode.CUSTOM:
        return body.target_filters, None
    return (
        existing.target_filters if existing else None,
        existing.target_filter_config_id if existing else None,
    )


def build_subscription_state_view(
    *,
    media_id: MediaID,
    state: MediaSubscriptionState | None,
    cycle,
) -> MediaSubscriptionStateView:
    return MediaSubscriptionStateView(
        sub_id=state.sub_id if state else None,
        media_id=media_id,
        season_number=state.season_number if state else None,
        active=state.active if state else False,
        followed=state.followed if state else False,
        subscription_mode=resolve_view_subscription_mode(media_id, state),
        upgrade_policy=state.upgrade_policy if state else None,
        target_filters=state.target_filters if state else None,
        target_filter_config_id=state.target_filter_config_id if state else None,
        last_run_at=state.last_run_at if state else None,
        last_checked_at=state.last_run_at if state else None,
        cycle_status=cycle.status.value if cycle else None,
        ended_reason=cycle.ended_reason if cycle else None,
        ended_at=cycle.ended_at if cycle else None,
        warnings=list(state.warnings) if state else [],
    )
