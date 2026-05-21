"""
text torrent textAPItext
"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.api.v1.commands.responses import CommandResponse
from app.schemas.exception.exceptions import RequestParamException
from app.schemas.domain.command import CommandCreateRequest, CommandRecord, CommandType, TaskTransferCommandRequestPayload
from app.services.application.commands.service import command_service

router = APIRouter()


class TransferRequest(BaseModel):
    task_id: str


@router.post("/transfer", response_model=CommandResponse)
async def transfer_torrent(body: TransferRequest) -> CommandResponse:
    """
    text command，text worker text.
    """
    task_id = body.task_id
    if not task_id:
        raise RequestParamException("task_id", str(task_id))
    command: CommandRecord = await command_service.create_command(
        CommandCreateRequest(
            type=CommandType.TASK_TRANSFER,
            payload=TaskTransferCommandRequestPayload(task_id=task_id),
        )
    )
    return CommandResponse(command=command)
