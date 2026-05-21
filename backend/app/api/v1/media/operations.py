from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.deps import MediaIDParam, require_tv_season
from app.schemas.media_id import MediaID
from app.schemas.domain.command import CommandRecord
from app.services.application.commands.service import command_service

router = APIRouter()


class MediaOperationsResponse(BaseModel):
    commands: list[CommandRecord]


@router.get("/operations", response_model=MediaOperationsResponse)
async def get_media_operations(
    mid: MediaID = Depends(MediaIDParam),
    season_number: Annotated[int | None, Query(gt=0)] = None,
) -> MediaOperationsResponse:
    commands = await command_service.list_media_active_commands(
        mid,
        season_number=require_tv_season(mid, season_number),
    )
    return MediaOperationsResponse(commands=commands)
