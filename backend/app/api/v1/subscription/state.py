from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.deps import MediaIDParam
from app.api.v1.subscription.season_context import require_subscription_season
from app.schemas.domain.media_subscription_state import (
    MediaSubscriptionStateView,
    SubscriptionStateUpdateRequest,
    resolve_target_filter_update,
    resolve_upgrade_policy_for_mode,
    resolve_view_subscription_mode,
)
from app.schemas.domain.media import MediaTarget
from app.schemas.media_id import MediaID
from app.schemas.runtime.subscription_lifecycle import SetSubscriptionStateCommand
from app.services.domain.subscription.command_service import subscription_command_service
from app.services.domain.subscription.query_service import subscription_query_service

router = APIRouter()


class SubscriptionStateResponse(BaseModel):
    data: MediaSubscriptionStateView


@router.get("/state", response_model=SubscriptionStateResponse)
async def get_subscription_state(
    mid: MediaID = Depends(MediaIDParam),
    season_number: Annotated[int | None, Query(gt=0)] = None,
) -> SubscriptionStateResponse:
    season = require_subscription_season(mid, season_number)
    view = await subscription_query_service.get_current(MediaTarget(media_id=mid, season_number=season))
    return SubscriptionStateResponse(data=view)


@router.put("/state", response_model=SubscriptionStateResponse)
async def put_subscription_state(
    body: SubscriptionStateUpdateRequest,
    mid: MediaID = Depends(MediaIDParam),
    season_number: Annotated[int | None, Query(gt=0)] = None,
) -> SubscriptionStateResponse:
    season = require_subscription_season(mid, season_number)
    target = MediaTarget(media_id=mid, season_number=season)
    existing = await subscription_query_service.get_state(target)
    requested_mode = body.subscription_mode or resolve_view_subscription_mode(mid, existing)
    next_target_filters, next_target_filter_config_id = resolve_target_filter_update(
        body=body,
        existing=existing,
        requested_mode=requested_mode,
    )
    change = await subscription_command_service.set_subscription_state(
        target,
        SetSubscriptionStateCommand(
            active=body.active,
            followed=body.followed,
            subscription_mode=requested_mode,
            upgrade_policy=resolve_upgrade_policy_for_mode(
                mid,
                requested_mode,
                requested_upgrade_policy=body.upgrade_policy,
                existing_upgrade_policy=existing.upgrade_policy if existing else None,
            ),
            target_filters=next_target_filters,
            target_filter_config_id=next_target_filter_config_id,
        ),
    )
    return SubscriptionStateResponse(data=change.view)
