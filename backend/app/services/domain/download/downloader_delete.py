from __future__ import annotations

from app.schemas.domain.download import TaskData
from app.schemas.exception.exceptions import DownloadException
from app.services.domain.download.download_file_ops import (
    delete_download_content_path,
    resolve_download_content_delete_target,
)
from app.services.integration.download.client import DownloadClient


async def delete_downloader_task(client: DownloadClient, task: TaskData, *, delete_files: bool = False) -> None:
    capabilities = client.capabilities()
    if delete_files and not capabilities.can_delete_files:
        raise DownloadException("backendErrors.downloaderDeleteFilesUnsupported")
    if delete_files and capabilities.delete_files_requires_aethera:
        await _delete_with_aethera_managed_files(client, task)
        return
    if not await client.delete_torrent(task.torrent_hash, delete_files=delete_files):
        raise DownloadException("backendErrors.downloaderDeleteFailed")


async def _delete_with_aethera_managed_files(client: DownloadClient, task: TaskData) -> None:
    info = await client.get_torrent_info(task.torrent_hash)
    target = resolve_download_content_delete_target(task, info)
    if not target:
        raise DownloadException("backendErrors.downloaderDeleteFilesUnsupported")
    if not await client.delete_torrent(task.torrent_hash, delete_files=False):
        raise DownloadException("backendErrors.downloaderDeleteFailed")
    if not delete_download_content_path(target):
        raise DownloadException("backendErrors.downloaderDeleteFilesUnsupported")
