from __future__ import annotations

import json
import time
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

from app.schemas.domain.media import MediaExecutionSnapshot
from app.schemas.domain.subscription import SubscriptionUnmatchedRule
from app.schemas.domain.subscription_filters import SubscriptionFilters, UpgradePolicy
from app.schemas.media_id import MediaID
from app.schemas.domain.media_subscription_state import SubscriptionMode


class MediaSubscriptionSettings(BaseModel):
    sub_id: str = Field(default_factory=lambda: uuid4().hex)
    media_id: MediaID
    media: MediaExecutionSnapshot | None = None
    season_number: int | None = None
    followed: bool = False
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
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())

    @model_validator(mode="after")
    def strip_embedded_upgrade_policy(self) -> "MediaSubscriptionSettings":
        if self.filters and self.filters.upgrade_policy is not None:
            self.filters = self.filters.model_copy(update={"upgrade_policy": None})
        if self.target_filters and self.target_filters.upgrade_policy is not None:
            self.target_filters = self.target_filters.model_copy(update={"upgrade_policy": None})
        return self

    def compute_config_fingerprint(self) -> str:
        payload = {
            "season_number": self.season_number,
            "subscription_mode": self.subscription_mode.value,
            "upgrade_policy": self.upgrade_policy.model_dump(mode="json") if self.upgrade_policy else None,
            "target_filters": self.target_filters.model_dump(mode="json") if self.target_filters else None,
            "target_filter_config_id": self.target_filter_config_id,
            "directory_id": self.directory_id,
            "filter_config_id": self.filter_config_id,
            "quality_profile_id": self.quality_profile_id,
            "filters": self.filters.model_dump(mode="json") if self.filters else None,
            "sites": self.sites or [],
            "unmatched_rules": [rule.model_dump(mode="json") for rule in self.unmatched_rules],
        }
        return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


class MediaSubscriptionSettingsPatch(BaseModel):
    season_number: int | None = None
    followed: bool | None = None
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
    follow_reminded_air_date: str | None = None
    follow_reminded_digital_release_date: str | None = None
    follow_reminded_physical_release_date: str | None = None
    follow_reminded_at: float | None = None
    follow_reminded_digital_release_at: float | None = None
    follow_reminded_physical_release_at: float | None = None

    @model_validator(mode="after")
    def strip_embedded_upgrade_policy(self) -> "MediaSubscriptionSettingsPatch":
        if self.filters and self.filters.upgrade_policy is not None:
            self.filters = self.filters.model_copy(update={"upgrade_policy": None})
        if self.target_filters and self.target_filters.upgrade_policy is not None:
            self.target_filters = self.target_filters.model_copy(update={"upgrade_policy": None})
        return self
