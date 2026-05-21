import time
from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.domain.media import MediaExecutionSnapshot
from app.schemas.media_id import MediaID
from app.schemas.domain.resource_filters import ResourceUnmatchedRule
from app.schemas.domain.subscription_filters import SubscriptionFilters


class SubscriptionUnmatchedRule(ResourceUnmatchedRule):
    pass


class SubscriptionSearchWarningType(str, Enum):
    NO_ID_MATCH = "no_id_match_title_only"
    HIGHER_QUALITY_UNMATCHED = "higher_quality_unmatched"


class SubscriptionSearchWarning(BaseModel):
    type: SubscriptionSearchWarningType
    message_key: str
    message_params: dict[str, str] = Field(default_factory=dict)
    created_at: float = Field(default_factory=lambda: time.time())


class Subscription(BaseModel):
    sub_id: str
    media_id: MediaID
    media: MediaExecutionSnapshot
    season_number: int | None = None
    sites: list[str] | None = None
    torznab_feed: str | None = None
    filters: SubscriptionFilters | None = None
    target_filters: SubscriptionFilters | None = None
    target_filter_config_id: str | None = None
    filter_config_id: str | None = None
    quality_profile_id: str | None = None
    directory_id: str | None = None
    followed: bool = False
    active: bool = True
    created_at: float = Field(default_factory=lambda: time.time())
    last_run_at: float | None = None
    follow_reminded_air_date: str | None = None
    follow_reminded_digital_release_date: str | None = None
    follow_reminded_physical_release_date: str | None = None
    follow_reminded_at: float | None = None
    follow_reminded_digital_release_at: float | None = None
    follow_reminded_physical_release_at: float | None = None
    unmatched_rules: list[SubscriptionUnmatchedRule] = Field(default_factory=list)
    warnings: list[SubscriptionSearchWarning] = Field(default_factory=list)
