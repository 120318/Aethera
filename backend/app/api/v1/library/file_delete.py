from fastapi import APIRouter
from pydantic import BaseModel

from app.api.v1.commands.responses import CommandResponse
from app.schemas.exception.exceptions import RequestParamException
from app.schemas.domain.command import CommandCreateRequest, CommandRecord, CommandType, LibraryFileDeleteCommandRequestPayload
from app.schemas.domain.media import MediaTarget
from app.services.application.commands.service import command_service

router = APIRouter()


class LibraryFileDeleteRequest(BaseModel):
    file_id: str
    target: MediaTarget
    force: bool = False
    package_root: str = ""


@router.post("/file/delete", response_model=CommandResponse)
async def delete_library_file(body: LibraryFileDeleteRequest) -> CommandResponse:
    if not body.file_id:
        raise RequestParamException("file_id", str(body.file_id))
    command: CommandRecord = await command_service.create_command(
        CommandCreateRequest(
            type=CommandType.LIBRARY_FILE_DELETE,
            payload=LibraryFileDeleteCommandRequestPayload(
                file_id=body.file_id,
                target=body.target,
                force=body.force,
                package_root=body.package_root,
            ),
        )
    )
    return CommandResponse(command=command)
