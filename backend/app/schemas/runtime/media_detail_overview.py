from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.config import DirectoryConfig
from app.schemas.domain.filter_config import FilterConfig
from app.schemas.domain.media_subscription_state import SubscriptionMode
from app.schemas.domain.quality_profile import QualityProfile
from app.schemas.integration.site_models import SiteInfo
from app.schemas.media_id import MediaID
from app.schemas.runtime.library_overview import LibraryOverviewSnapshot


class MediaDetailSubscriptionSummary(BaseModel):
    subscribed: bool = False
    followed: bool = False
    subscription_mode: SubscriptionMode = SubscriptionMode.FIRST_RELEASE


class MediaDetailResourceDiscoverySummary(BaseModel):
    searched: bool = False
    search_state: Literal["idle", "searching", "ready"] = "idle"
    available_count: int = 0
    matched_by_id_count: int = 0
    matched_by_custom_rule_count: int = 0
    searched_at: float | None = None


class MediaDetailConfigValueSummary(BaseModel):
    id: str | None = None
    name: str = ""
    name_key: str | None = "common.notSet"
    name_params: dict[str, str] = Field(default_factory=dict)
    is_default: bool = False


class MediaDetailCustomRulesSummary(BaseModel):
    enabled: bool = False
    count: int = 0
    summary: str = ""
    summary_key: str = "common.notSet"
    summary_params: dict[str, str] = Field(default_factory=dict)


class MediaDetailCurrentConfigSummary(BaseModel):
    directory: MediaDetailConfigValueSummary
    filter: MediaDetailConfigValueSummary
    quality_profile: MediaDetailConfigValueSummary
    custom_rules: MediaDetailCustomRulesSummary


class MediaDetailActionReadinessItem(BaseModel):
    available: bool = True
    reason: str = ""
    reason_key: str = "actionPrerequisites.ready"
    reason_params: dict[str, str] = Field(default_factory=dict)
    target: str | None = None


class MediaDetailActionReadinessSummary(BaseModel):
    search: MediaDetailActionReadinessItem = Field(default_factory=MediaDetailActionReadinessItem)
    download: MediaDetailActionReadinessItem = Field(default_factory=MediaDetailActionReadinessItem)
    subscription: MediaDetailActionReadinessItem = Field(default_factory=MediaDetailActionReadinessItem)
    follow: MediaDetailActionReadinessItem = Field(default_factory=MediaDetailActionReadinessItem)


class MediaDetailOverviewSummary(BaseModel):
    subscription: MediaDetailSubscriptionSummary
    resource_discovery: MediaDetailResourceDiscoverySummary
    download_config: MediaDetailCurrentConfigSummary
    local_resources: LibraryOverviewSnapshot
    action_readiness: MediaDetailActionReadinessSummary = Field(default_factory=MediaDetailActionReadinessSummary)


class MediaDetailOverviewCatalogs(BaseModel):
    sites: list[SiteInfo] = Field(default_factory=list)
    filters: list[FilterConfig] = Field(default_factory=list)
    quality_profiles: list[QualityProfile] = Field(default_factory=list)
    directories: list[DirectoryConfig] = Field(default_factory=list)


class MediaDetailOverviewResponse(BaseModel):
    media_id: MediaID
    summary: MediaDetailOverviewSummary
    catalogs: MediaDetailOverviewCatalogs
