from fastapi import APIRouter

from app.services.domain.download import download_service
from app.services.domain.download.downloader_change import (
    TaskDownloaderChangePreview,
    TaskDownloaderChangeRequest,
)

router = APIRouter()


@router.post("/{task_id}/downloader-change/preview", response_model=TaskDownloaderChangePreview)
async def preview_task_downloader_change(
    task_id: str,
    body: TaskDownloaderChangeRequest,
) -> TaskDownloaderChangePreview:
    return await download_service.preview_task_downloader_change(task_id, body)
