from fastapi import APIRouter
from pydantic import BaseModel

from app.api.v1.commands.responses import CommandResponse
from app.schemas.exception.exceptions import ResourceNotFoundException
from app.schemas.domain.command import CommandRecord
from app.services.application.commands.service import command_service

router = APIRouter()


class CommandDetailResponse(BaseModel):
    command: CommandRecord | None = None


@router.get("/{command_id}", response_model=CommandDetailResponse)
async def get_command(command_id: str) -> CommandDetailResponse:
    command = await command_service.get_command(command_id)
    return CommandDetailResponse(command=command)


@router.post("/{command_id}/cancel", response_model=CommandResponse)
async def cancel_command(command_id: str) -> CommandResponse:
    command = await command_service.cancel_command(command_id)
    if not command:
        raise ResourceNotFoundException("backendErrors.commandNotFound")
    return CommandResponse(command=command)
