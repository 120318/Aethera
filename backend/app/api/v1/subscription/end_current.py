from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict

from app.api.deps import MediaIDParam
from app.api.v1.subscription.season_context import require_subscription_season
from app.api.v1.subscription.state import SubscriptionStateResponse
from app.schemas.domain.media import MediaTarget
from app.schemas.domain.media_subscription_state import SubscriptionEndReason, SubscriptionEndTrigger
from app.schemas.exception import InvalidRequestException
from app.schemas.media_id import MediaID
from app.schemas.runtime.subscription_lifecycle import EndSubscriptionCommand
from app.services.domain.subscription.command_service import subscription_command_service

router = APIRouter()


class EndCurrentSubscriptionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: SubscriptionEndReason = SubscriptionEndReason.MANUAL


@router.post("/end-current", response_model=SubscriptionStateResponse)
async def end_current_subscription(
    body: EndCurrentSubscriptionRequest,
    mid: MediaID = Depends(MediaIDParam),
    season_number: Annotated[int | None, Query(gt=0)] = None,
) -> SubscriptionStateResponse:
    if body.reason != SubscriptionEndReason.MANUAL:
        raise InvalidRequestException("backendErrors.subscriptionEndReasonInvalid")
    season = require_subscription_season(mid, season_number)
    change = await subscription_command_service.end_subscription(
        MediaTarget(media_id=mid, season_number=season),
        EndSubscriptionCommand(
            trigger=SubscriptionEndTrigger.MANUAL,
            reason=SubscriptionEndReason.MANUAL,
        ),
    )
    return SubscriptionStateResponse(data=change.view)
