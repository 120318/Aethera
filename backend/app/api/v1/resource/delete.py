"""
text API text
"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.api.v1.commands.responses import CommandResponse
from app.schemas.exception.exceptions import RequestParamException
from app.schemas.domain.command import CommandCreateRequest, CommandRecord, CommandType, TaskDeleteCommandRequestPayload
from app.services.application.commands.service import command_service

router = APIRouter()


class DeleteRequest(BaseModel):
    torrent_hash: str | None = None
    action: str
    force: bool = False
    delete_files: bool = True


def _build_delete_command_request(task_id: str, body: DeleteRequest) -> CommandCreateRequest:
    if body.action not in ["torrent", "media", "both"]:
        raise RequestParamException("action", str(body.action))
    delete_library_files = body.action in ["media", "both"]
    delete_task = body.action in ["torrent", "both"]
    return CommandCreateRequest(
        type=CommandType.TASK_DELETE,
        payload=TaskDeleteCommandRequestPayload(
            task_id=task_id,
            force=body.force,
            delete_files=body.delete_files,
            delete_library_files=delete_library_files,
            delete_task=delete_task,
        ),
    )


@router.delete("/{torrent_hash}", response_model=CommandResponse)
async def delete_resource(torrent_hash: str, body: DeleteRequest) -> CommandResponse:
    if not torrent_hash:
        raise RequestParamException("torrent_hash", str(torrent_hash))
    command: CommandRecord = await command_service.create_command(_build_delete_command_request(torrent_hash, body))
    return CommandResponse(command=command)
