from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict

from app.api.deps import MediaIDParam
from app.api.v1.subscription.season_context import require_subscription_season
from app.schemas.domain.media_download_config import MediaDownloadConfigView
from app.schemas.domain.media import MediaTarget
from app.schemas.domain.media_subscription_state import MediaSubscriptionStateView, SubscriptionMode
from app.schemas.domain.subscription import SubscriptionUnmatchedRule
from app.schemas.domain.subscription_filters import SubscriptionFilters, UpgradePolicy
from app.schemas.media_id import MediaID
from app.schemas.runtime.subscription_lifecycle import SaveSubscriptionCommand
from app.services.domain.subscription.command_service import subscription_command_service

router = APIRouter()


class SubscriptionDialogSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
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

    def to_save_command(self) -> SaveSubscriptionCommand:
        return SaveSubscriptionCommand(
            active=self.active,
            followed=self.followed,
            subscription_mode=self.subscription_mode,
            upgrade_policy=self.upgrade_policy,
            target_filters=self.target_filters,
            target_filter_config_id=self.target_filter_config_id,
            directory_id=self.directory_id,
            filter_config_id=self.filter_config_id,
            quality_profile_id=self.quality_profile_id,
            filters=self.filters,
            sites=self.sites,
            unmatched_rules=self.unmatched_rules,
        )


class SubscriptionDialogSaveResponse(BaseModel):
    state: MediaSubscriptionStateView
    config: MediaDownloadConfigView


@router.put("/dialog-save", response_model=SubscriptionDialogSaveResponse)
async def save_subscription_dialog(
    body: SubscriptionDialogSaveRequest,
    mid: MediaID = Depends(MediaIDParam),
    season_number: Annotated[int | None, Query(gt=0)] = None,
) -> SubscriptionDialogSaveResponse:
    season = require_subscription_season(mid, season_number)
    change = await subscription_command_service.save_subscription(
        MediaTarget(media_id=mid, season_number=season),
        body.to_save_command(),
    )
    if change.config is None:
        raise RuntimeError("subscription config view is missing")
    return SubscriptionDialogSaveResponse(state=change.view, config=change.config)
