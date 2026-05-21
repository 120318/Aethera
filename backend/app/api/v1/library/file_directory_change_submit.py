from fastapi import APIRouter
from pydantic import BaseModel

from app.api.v1.commands.responses import CommandResponse
from app.schemas.domain.command import CommandCreateRequest, CommandRecord, CommandType, LibraryFileStorageChangeCommandRequestPayload
from app.schemas.domain.media import MediaTarget
from app.services.application.commands.service import command_service

router = APIRouter()


class LibraryFileDirectoryChangeSubmitRequest(BaseModel):
    file_id: str
    target: MediaTarget
    target_directory_id: str
    package_root: str = ""


@router.post("/file/directory-change", response_model=CommandResponse)
async def submit_library_file_directory_change(body: LibraryFileDirectoryChangeSubmitRequest) -> CommandResponse:
    command: CommandRecord = await command_service.create_command(
        CommandCreateRequest(
            type=CommandType.LIBRARY_FILE_STORAGE_CHANGE,
            payload=LibraryFileStorageChangeCommandRequestPayload(
                file_id=body.file_id,
                target=body.target,
                target_directory_id=body.target_directory_id,
                package_root=body.package_root,
            ),
        )
    )
    return CommandResponse(command=command)
