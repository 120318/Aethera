from __future__ import annotations

import time

from pydantic import BaseModel, Field, model_validator

from app.schemas.domain.quality_profile import QualityProfile
from app.schemas.domain.subscription import SubscriptionUnmatchedRule
from app.schemas.domain.subscription_filters import SubscriptionFilters
from app.schemas.media_id import MediaID


class MediaDownloadConfig(BaseModel):
    sub_id: str
    media_id: MediaID
    season_number: int | None = None
    directory_id: str | None = None
    filter_config_id: str | None = None
    quality_profile_id: str | None = None
    filters: SubscriptionFilters | None = None
    sites: list[str] | None = None
    unmatched_rules: list[SubscriptionUnmatchedRule] = Field(default_factory=list)
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())

    @model_validator(mode="after")
    def strip_upgrade_policy(self) -> "MediaDownloadConfig":
        if self.filters and self.filters.upgrade_policy is not None:
            self.filters = self.filters.model_copy(update={"upgrade_policy": None})
        return self


class MediaDownloadConfigPatch(BaseModel):
    directory_id: str | None = None
    filter_config_id: str | None = None
    quality_profile_id: str | None = None
    filters: SubscriptionFilters | None = None
    sites: list[str] | None = None
    unmatched_rules: list[SubscriptionUnmatchedRule] | None = None

    @model_validator(mode="after")
    def strip_upgrade_policy(self) -> "MediaDownloadConfigPatch":
        if self.filters and self.filters.upgrade_policy is not None:
            self.filters = self.filters.model_copy(update={"upgrade_policy": None})
        return self


class MediaDownloadConfigView(BaseModel):
    sub_id: str | None = None
    media_id: MediaID
    season_number: int | None = None
    directory_id: str | None = None
    filter_config_id: str | None = None
    quality_profile_id: str | None = None
    filters: SubscriptionFilters | None = None
    sites: list[str] | None = None
    unmatched_rules: list[SubscriptionUnmatchedRule] = Field(default_factory=list)


class EffectiveMediaDownloadConfig(BaseModel):
    media_id: MediaID
    season_number: int | None = None
    sub_id: str | None = None
    directory_id: str | None = None
    filter_config_id: str | None = None
    quality_profile_id: str | None = None
    filters: SubscriptionFilters | None = None
    has_custom_filter_override: bool = False
    sites: list[str] | None = None
    quality_profile: QualityProfile | None = None
    unmatched_rules: list[SubscriptionUnmatchedRule] = Field(default_factory=list)
    is_default_directory: bool = False
    is_default_filter: bool = False
    is_default_quality_profile: bool = False
