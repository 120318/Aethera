from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import MediaIDParam, require_tv_season
from app.api.v1.commands.responses import CommandResponse
from app.schemas.domain.command import CommandInitiator
from app.schemas.media_id import MediaID
from app.services.application.workflows.profile_refresh.service import profile_refresh_command_service

router = APIRouter()


@router.post("/profile-refresh", response_model=CommandResponse)
async def refresh_media_profile(
    mid: MediaID = Depends(MediaIDParam),
    season_number: Annotated[int | None, Query(gt=0)] = None,
) -> CommandResponse:
    command = await profile_refresh_command_service.enqueue(
        mid,
        season_number=require_tv_season(mid, season_number),
        initiator=CommandInitiator.MANUAL,
        force_requeue=True,
    )
    return CommandResponse(command=command)
