from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.v1.commands.responses import CommandResponse
from app.schemas.domain.command import CommandCreateRequest, CommandInitiator, CommandRecord, CommandType, MediaDeleteCommandRequestPayload
from app.schemas.domain.media import MediaTarget
from app.services.application.commands.service import command_service

router = APIRouter()


class DeleteMediaRequest(BaseModel):
    target: MediaTarget
    mode: Literal["tasks_only", "tasks_and_library"]
    force: bool = False
    delete_files: bool = True

@router.post("/manage/delete", response_model=CommandResponse)
async def delete_media_resources(payload: DeleteMediaRequest) -> CommandResponse:
    command: CommandRecord = await command_service.create_command(
        CommandCreateRequest(
            type=CommandType.MEDIA_DELETE,
            initiator=CommandInitiator.MANUAL,
            payload=MediaDeleteCommandRequestPayload(
                target=payload.target,
                mode=payload.mode,
                force=payload.force,
                delete_files=payload.delete_files,
            ),
        )
    )
    return CommandResponse(command=command)
