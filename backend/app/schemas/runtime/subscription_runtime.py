from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from app.schemas.domain.media import MediaExecutionSnapshot
from app.schemas.domain.quality_profile import QualityProfile
from app.schemas.domain.subscription import Subscription, SubscriptionSearchWarning
from app.schemas.domain.subscription_filters import SubscriptionFilters
from app.schemas.domain.subscription_run_result import SubscriptionRunResponse


class SubscriptionRunOutcomeStatus(StrEnum):
    BUSY = "busy"
    INVALID = "invalid"
    SATISFIED = "satisfied"
    NO_RESOURCE = "no_resource"
    NO_MATCH = "no_match"
    NO_SELECTION = "no_selection"
    QUEUED = "queued"
    QUEUE_FAILED = "queue_failed"


class SubscriptionPlanningStatus(StrEnum):
    INVALID = "invalid"
    SATISFIED = "satisfied"
    READY = "ready"


class SubscriptionRunPlan(BaseModel):
    sub_id: str
    media: MediaExecutionSnapshot
    season_number: int | None = None
    correlation_id: str
    episode_mode: bool = True
    sites: list[str] | None = None
    filters: SubscriptionFilters | None = None
    quality_profile: QualityProfile | None = None
    target_episodes: set[int] = Field(default_factory=set)
    required_scores: dict[int, int] = Field(default_factory=dict)
    existing_disc_numbers: set[int] = Field(default_factory=set)

    @model_validator(mode="after")
    def validate_season_contract(self) -> "SubscriptionRunPlan":
        if self.episode_mode:
            if self.season_number is None or self.season_number <= 0:
                raise ValueError("episode_mode subscription run plan requires positive season_number")
        elif self.season_number is not None:
            raise ValueError("non-episode subscription run plan must not include season_number")
        return self


class SubscriptionRunPlanningResult(BaseModel):
    status: SubscriptionPlanningStatus
    plan: SubscriptionRunPlan | None = None
    message_key: str | None = None
    message_params: dict[str, str] = Field(default_factory=dict)
    correlation_id: str | None = None


class SubscriptionRunOutcome(BaseModel):
    status: SubscriptionRunOutcomeStatus
    response: SubscriptionRunResponse = Field(default_factory=SubscriptionRunResponse)
    plan: SubscriptionRunPlan | None = None
    message_key: str | None = None
    message_params: dict[str, str] = Field(default_factory=dict)
    correlation_id: str | None = None
    warnings: list[SubscriptionSearchWarning] = Field(default_factory=list)

    @property
    def should_emit_failed(self) -> bool:
        return self.status in {
            SubscriptionRunOutcomeStatus.INVALID,
            SubscriptionRunOutcomeStatus.QUEUE_FAILED,
        }

    @property
    def should_emit_completed(self) -> bool:
        return self.status == SubscriptionRunOutcomeStatus.QUEUED and self.response.added > 0


class SelectedSubscriptionResource(BaseModel):
    payload_name: str
    payload_size: int
    selected_files_count: int


class SubscriptionActionResult(BaseModel):
    subscription: Subscription
    became_active: bool = False
    became_inactive: bool = False
    follow_auto_enabled: bool = False
    should_refresh_profile: bool = False


class FollowActionResult(BaseModel):
    subscription: Subscription
    became_followed: bool = False
    became_unfollowed: bool = False
    should_refresh_profile: bool = False
