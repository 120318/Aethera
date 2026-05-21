"""
textAPItext
"""
from fastapi import APIRouter

from app.api.v1.commands.responses import CommandResponse
from app.schemas.domain.command import CommandCreateRequest, CommandInitiator, CommandRecord
from app.schemas.domain.download import DownloadTaskCreateInput
from app.services.application.commands.service import command_service

router = APIRouter()

@router.post("/download", response_model=CommandResponse)
async def download(req: DownloadTaskCreateInput) -> CommandResponse:
    """
    text
    """
    command: CommandRecord = await command_service.create_command(
        CommandCreateRequest.from_task_create_input(req, initiator=CommandInitiator.MANUAL)
    )
    return CommandResponse(command=command)
