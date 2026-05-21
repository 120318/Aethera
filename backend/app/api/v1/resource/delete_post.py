"""
text（POST text）API text
"""
from fastapi import APIRouter

from app.api.v1.resource.delete import DeleteRequest, _build_delete_command_request
from app.api.v1.commands.responses import CommandResponse
from app.schemas.exception.exceptions import RequestParamException
from app.schemas.domain.command import CommandRecord
from app.services.application.commands.service import command_service

router = APIRouter()


@router.post("/delete", response_model=CommandResponse)
async def delete_resource_post(body: DeleteRequest) -> CommandResponse:
    if not body.torrent_hash:
        raise RequestParamException("torrent_hash", str(body.torrent_hash))
    command: CommandRecord = await command_service.create_command(_build_delete_command_request(body.torrent_hash, body))
    return CommandResponse(command=command)
