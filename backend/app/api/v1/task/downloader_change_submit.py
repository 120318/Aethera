from fastapi import APIRouter

from app.schemas.domain.command import (
    CommandCreateRequest,
    CommandInitiator,
    CommandRecord,
    CommandType,
    TaskStorageChangeCommandRequestPayload,
)
from app.services.application.commands.service import command_service
from app.services.domain.download.downloader_change import TaskDownloaderChangeRequest

router = APIRouter()


@router.post("/{task_id}/downloader-change", response_model=CommandRecord)
async def change_task_downloader(
    task_id: str,
    body: TaskDownloaderChangeRequest,
) -> CommandRecord:
    return await command_service.create_command(
        CommandCreateRequest(
            type=CommandType.TASK_STORAGE_CHANGE,
            initiator=CommandInitiator.MANUAL,
            payload=TaskStorageChangeCommandRequestPayload(
                task_id=task_id,
                target_downloader_id=body.target_downloader_id,
                target_directory_id=body.target_directory_id,
                cleanup_source_torrent=body.cleanup_source_torrent,
            ),
        )
    )
