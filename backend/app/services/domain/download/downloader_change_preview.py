from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field

from app.schemas.config import DirectoryConfig, DownloaderConfig
from app.schemas.domain.download import DownloadInfo, TaskData
from app.schemas.domain.library import LibraryFile
from app.services.domain.library.service import library_service
from app.services.integration.download.client import DownloadClient
from app.services.integration.torrent.service import torrent_service
from app.utils.library_paths import build_download_path, build_library_file_path, to_download_relative_path


class TaskDownloaderChangeRequest(BaseModel):
    target_downloader_id: str
    target_directory_id: str
    cleanup_source_torrent: bool = True


class TaskDownloaderChangePreview(BaseModel):
    ok: bool
    task_id: str
    current_downloader_id: str | None = None
    target_downloader_id: str
    current_directory_id: str | None = None
    target_directory_id: str
    torrent_hash: str | None = None
    current_save_path: str | None = None
    target_save_path: str | None = None
    current_local_path: str | None = None
    target_local_path: str | None = None
    current_content_path: str | None = None
    target_content_path: str | None = None
    move_content: bool = True
    save_path_changed: bool = False
    has_library_files: bool = False
    hardlink_check_required: bool = False
    hardlink_check_passed: bool | None = None
    warnings: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)


async def build_change_preview(
    *,
    task: TaskData,
    target_downloader: DownloaderConfig,
    target_directory: DirectoryConfig,
    source_client: DownloadClient | None,
    target_client: DownloadClient,
) -> TaskDownloaderChangePreview:
    current_directory_id = task.context.directory_id if task.context else None
    current_save_path = task.save_path or ""
    target_save_path = to_download_relative_path(target_directory.download_path)
    current_local_path = build_download_path(current_save_path).resolve(strict=False)
    target_local_path = build_download_path(target_save_path).resolve(strict=False)
    preview = TaskDownloaderChangePreview(
        ok=True,
        task_id=task.id,
        current_downloader_id=task.downloader_id,
        target_downloader_id=target_downloader.id,
        current_directory_id=current_directory_id,
        target_directory_id=target_directory.id,
        torrent_hash=task.torrent_hash,
        current_save_path=current_save_path,
        target_save_path=target_save_path,
        current_local_path=str(current_local_path),
        target_local_path=str(target_local_path),
        move_content=bool(current_local_path != target_local_path),
        save_path_changed=current_save_path != target_save_path,
    )
    await _fill_preview(preview, task, target_downloader, target_directory, source_client, target_client)
    preview.ok = not preview.blockers
    return preview


async def _fill_preview(
    preview: TaskDownloaderChangePreview,
    task: TaskData,
    target_downloader: DownloaderConfig,
    target_directory: DirectoryConfig,
    source_client: DownloadClient | None,
    target_client: DownloadClient,
) -> None:
    if not task.downloader_id:
        preview.blockers.append("task_downloader_missing")
    if not task.torrent_hash:
        preview.blockers.append("task_torrent_hash_missing")
    if not task.metadata:
        preview.blockers.append("task_metadata_missing")
    if target_directory.media_type != task.media_id.media_type:
        preview.blockers.append("media_type_mismatch")
    if not target_directory.download_path:
        preview.blockers.append("target_directory_download_path_missing")
    if target_directory.downloader_id and target_directory.downloader_id != target_downloader.id:
        preview.warnings.append("target_directory_bound_to_different_downloader")

    source_info = await source_client.get_torrent_info(task.torrent_hash) if source_client and task.torrent_hash else None
    same_downloader = task.downloader_id == target_downloader.id
    target_info = await target_client.get_torrent_info(task.torrent_hash) if task.torrent_hash else None
    if not source_info and not target_info:
        preview.blockers.append("torrent_missing_in_source_and_target")
    has_stored_torrent = bool(torrent_service.load_stored_blob(task.torrent_hash))
    if source_info and not target_info and source_client and not source_client.capabilities().can_export_torrent and not has_stored_torrent:
        preview.blockers.append("source_downloader_export_unsupported")
    if source_info and not target_client.capabilities().can_recheck:
        preview.blockers.append("target_downloader_recheck_unsupported")
    if source_info and task.metadata and task.context.selected_files and not target_client.capabilities().can_set_file_priority:
        preview.blockers.append("target_downloader_file_priority_unsupported")

    current_content = resolve_content_path(preview.current_local_path, source_info)
    target_content = _resolve_target_content_path(preview.target_local_path, current_content, None if same_downloader else target_info)
    if not source_info and target_info:
        current_content = None
        preview.move_content = False
    location_requires_aethera_move = target_client.capabilities().location_update_requires_aethera_move
    if same_downloader and not location_requires_aethera_move:
        preview.move_content = False
        if preview.save_path_changed and not target_client.capabilities().can_set_location:
            preview.blockers.append("target_downloader_location_change_unsupported")
    elif same_downloader and preview.save_path_changed and not target_client.capabilities().can_set_location:
        preview.blockers.append("target_downloader_location_change_unsupported")
    preview.current_content_path = str(current_content) if current_content else None
    preview.target_content_path = str(target_content) if target_content else None

    if target_info and not same_downloader:
        target_actual = build_download_path(target_info.save_path).resolve(strict=False)
        expected = build_download_path(preview.target_save_path).resolve(strict=False) if preview.target_save_path else None
        if expected and target_actual != expected:
            preview.blockers.append("target_torrent_save_path_conflict")

    target_path = Path(preview.target_local_path or "")
    check_path = target_path if target_path.exists() else target_path.parent
    if not check_path.exists() or not os.access(check_path, os.W_OK):
        preview.blockers.append("target_path_not_writable")

    library_files = await library_service.get_files_by_task(task.id)
    primary_library_files = [item for item in library_files if library_service.is_primary_file(item)]
    preview.has_library_files = bool(primary_library_files)
    library_move_required = any(item.directory_id != target_directory.id for item in primary_library_files)
    preview.hardlink_check_required = bool(primary_library_files and (preview.save_path_changed or library_move_required))
    if preview.hardlink_check_required:
        target_library_path = build_library_file_path(target_directory.path).resolve(strict=False)
        preview.hardlink_check_passed = _validate_hardlink_safe_move(task, primary_library_files, target_path, target_library_path)
        if not preview.hardlink_check_passed:
            preview.blockers.append("hardlink_cross_device_or_unmatched")


def resolve_content_path(save_path: str | None, info: DownloadInfo | None) -> Path | None:
    if info and info.content_path:
        return build_download_path(info.content_path).resolve(strict=False)
    if save_path:
        return build_download_path(save_path).resolve(strict=False)
    return None


def _resolve_target_content_path(target_save_path: str | None, source_content: Path | None, target_info: DownloadInfo | None) -> Path | None:
    if target_info and target_info.content_path:
        return build_download_path(target_info.content_path).resolve(strict=False)
    if not target_save_path:
        return None
    target_base = build_download_path(target_save_path).resolve(strict=False)
    if source_content and source_content.name:
        return target_base / source_content.name
    return target_base


def _validate_hardlink_safe_move(task: TaskData, library_files: list[LibraryFile], target_download_path: Path, target_library_path: Path) -> bool:
    if not target_download_path.exists() or not target_library_path.exists():
        return False
    try:
        current_device = build_download_path(task.save_path).resolve(strict=False).stat().st_dev
        target_download_device = target_download_path.stat().st_dev
        target_library_device = target_library_path.stat().st_dev
    except OSError:
        return False
    if current_device != target_download_device or current_device != target_library_device:
        return False
    for library_file in library_files:
        library_path = build_library_file_path(library_file.path, library_file.file_name)
        if not library_path.exists():
            return False
        try:
            if library_path.stat().st_dev != current_device:
                return False
        except OSError:
            return False
    return True
