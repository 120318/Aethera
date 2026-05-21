from fastapi import APIRouter

from app.schemas.domain.command import CommandCreateRequest, CommandRecord
from app.api.v1.commands.responses import CommandResponse
from app.services.application.commands.service import command_service

router = APIRouter()


@router.post("/", response_model=CommandResponse)
async def create_command(body: CommandCreateRequest) -> CommandResponse:
    command: CommandRecord = await command_service.create_command(body)
    return CommandResponse(command=command)
