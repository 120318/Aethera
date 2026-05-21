from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.deps import OptionalMediaIDParam, require_tv_season
from app.schemas.media_id import MediaID
from app.schemas.domain.command import CommandRecord, CommandTargetType, CommandType
from app.services.application.commands.service import command_service

router = APIRouter()


class ActiveCommandListResponse(BaseModel):
    items: list[CommandRecord]


@router.get("/active", response_model=ActiveCommandListResponse)
async def list_active_commands(
    media_id: MediaID | None = Depends(OptionalMediaIDParam),
    season_number: int | None = Query(None, gt=0),
    target_type: CommandTargetType | None = Query(None),
    target_id: str | None = Query(None),
    target_ids: list[str] | None = Query(None),
    types: list[CommandType] | None = Query(None),
    command_types: list[CommandType] | None = Query(None),
) -> ActiveCommandListResponse:
    resolved_types = types or command_types
    if media_id:
        commands = await command_service.list_media_active_commands(
            media_id,
            season_number=require_tv_season(media_id, season_number),
            command_types=resolved_types,
        )
        return ActiveCommandListResponse(items=commands)

    resolved_target_ids = list(target_ids or [])
    if target_id:
        resolved_target_ids.append(target_id)
    commands = await command_service.list_active_commands(
        target_type=target_type,
        target_ids=resolved_target_ids or None,
        season_number=season_number,
        command_types=resolved_types,
    )
    return ActiveCommandListResponse(items=commands)
