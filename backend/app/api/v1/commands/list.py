from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.schemas.domain.command import CommandRecord, CommandStatus
from app.services.application.commands.service import command_service

router = APIRouter()


class CommandListResponse(BaseModel):
    items: list[CommandRecord]


@router.get("/", response_model=CommandListResponse)
async def list_commands(
    limit: int = Query(20, ge=1, le=100),
    statuses: list[CommandStatus] | None = Query(None),
) -> CommandListResponse:
    commands = await command_service.list_recent_commands(limit=limit, statuses=statuses)
    return CommandListResponse(items=commands)
