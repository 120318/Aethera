from __future__ import annotations

import time
from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.domain.media import MediaExecutionSnapshot, MediaTarget
from app.schemas.domain.media_download_config import MediaDownloadConfigView
from app.schemas.domain.media_subscription_cycle import MediaSubscriptionCycle
from app.schemas.domain.media_subscription_settings import MediaSubscriptionSettings
from app.schemas.domain.media_subscription_state import (
    MediaSubscriptionState,
    MediaSubscriptionStateView,
    SubscriptionEndReason,
    SubscriptionEndTrigger,
    SubscriptionMode,
    UpgradeCompletionSnapshot,
)
from app.schemas.domain.subscription import Subscription, SubscriptionSearchWarning, SubscriptionUnmatchedRule
from app.schemas.domain.subscription_filters import SubscriptionFilters, UpgradePolicy


class SubscriptionAggregate(BaseModel):
    target: MediaTarget
    settings: MediaSubscriptionSettings | None = None
    active_cycle: MediaSubscriptionCycle | None = None
    latest_cycle: MediaSubscriptionCycle | None = None
    state: MediaSubscriptionState | None = None
    view: MediaSubscriptionStateView


class SaveSubscriptionCommand(BaseModel):
    active: bool
    followed: bool
    subscription_mode: SubscriptionMode | None = None
    upgrade_policy: UpgradePolicy | None = None
    target_filters: SubscriptionFilters | None = None
    target_filter_config_id: str | None = None
    directory_id: str | None = None
    filter_config_id: str | None = None
    quality_profile_id: str | None = None
    filters: SubscriptionFilters | None = None
    sites: list[str] | None = None
    unmatched_rules: list[SubscriptionUnmatchedRule] | None = None


class SetSubscriptionStateCommand(BaseModel):
    active: bool
    followed: bool
    media: MediaExecutionSnapshot | None = None
    subscription_mode: SubscriptionMode
    upgrade_policy: UpgradePolicy | None = None
    target_filters: SubscriptionFilters | None = None
    target_filter_config_id: str | None = None
    emit_events: bool = True


class EndSubscriptionCommand(BaseModel):
    sub_id: str | None = None
    trigger: SubscriptionEndTrigger
    reason: SubscriptionEndReason


class SubscriptionMutation(BaseModel):
    target: MediaTarget
    sub_id: str | None = None
    media: MediaExecutionSnapshot | None = None
    active: bool
    followed: bool
    subscription_mode: SubscriptionMode
    upgrade_policy: UpgradePolicy | None = None
    target_filters: SubscriptionFilters | None = None
    target_filter_config_id: str | None = None
    directory_id: str | None = None
    filter_config_id: str | None = None
    quality_profile_id: str | None = None
    filters: SubscriptionFilters | None = None
    sites: list[str] | None = None
    unmatched_rules: list[SubscriptionUnmatchedRule] = Field(default_factory=list)
    follow_reminded_air_date: str | None = None
    follow_reminded_digital_release_date: str | None = None
    follow_reminded_physical_release_date: str | None = None
    follow_reminded_at: float | None = None
    follow_reminded_digital_release_at: float | None = None
    follow_reminded_physical_release_at: float | None = None
    clear_completion_snapshot: bool = False
    end_trigger: SubscriptionEndTrigger = SubscriptionEndTrigger.MANUAL
    end_reason: SubscriptionEndReason = SubscriptionEndReason.MANUAL


class EndSubscriptionMutation(BaseModel):
    target: MediaTarget
    sub_id: str | None = None
    trigger: SubscriptionEndTrigger
    reason: SubscriptionEndReason


class SubscriptionRunRecord(BaseModel):
    sub_id: str
    target: MediaTarget
    checked_at: float = Field(default_factory=lambda: time.time())
    warnings: list[SubscriptionSearchWarning] = Field(default_factory=list)
    upgrade_snapshot: UpgradeCompletionSnapshot | None = None


class SubscriptionLifecycleEventType(StrEnum):
    SUBSCRIPTION_ENABLED = "subscription_enabled"
    SUBSCRIPTION_DISABLED = "subscription_disabled"
    FOLLOW_ENABLED = "follow_enabled"
    FOLLOW_DISABLED = "follow_disabled"
    SUBSCRIPTION_ENDED = "subscription_ended"


class SubscriptionLifecycleEventIntent(BaseModel):
    type: SubscriptionLifecycleEventType
    trigger: SubscriptionEndTrigger | None = None
    reason: SubscriptionEndReason | None = None


class SubscriptionChange(BaseModel):
    previous: MediaSubscriptionState | None = None
    current: MediaSubscriptionState | None = None
    view: MediaSubscriptionStateView
    config: MediaDownloadConfigView | None = None
    events: list[SubscriptionLifecycleEventIntent] = Field(default_factory=list)
    profile_activation_needed: bool = False


class SubscriptionCompletion(BaseModel):
    sub_id: str
    target: MediaTarget
    reason: SubscriptionEndReason
    upgrade_snapshot: UpgradeCompletionSnapshot | None = None


class ResourceRunSelection(BaseModel):
    checked: int = 0
    matched: int = 0
    warnings: list[SubscriptionSearchWarning] = Field(default_factory=list)
    selected: list = Field(default_factory=list)
