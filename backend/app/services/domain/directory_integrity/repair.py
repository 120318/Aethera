from __future__ import annotations

import asyncio
import logging
import shutil
from pathlib import Path

from app.db.repositories.library_episode_repository import LibraryEpisodeRepository
from app.db.repositories.library_file_artifact_repository import LibraryFileArtifactRepository
from app.db.repositories.library_file_repository import LibraryFileRepository
from app.schemas.exception.base import AppException
from app.schemas.runtime.directory_integrity import DirectoryIntegrityIssueType, DirectoryIntegrityItem, DirectoryIntegrityRepairResult
from app.services.domain.download import download_service as default_download_service
from app.services.domain.transfer import transfer_service as default_transfer_service

logger = logging.getLogger("app.services.directory_integrity.repair")


class DirectoryIntegrityRepairExecutor:
    def __init__(self) -> None:
        self.library_repo = LibraryFileRepository()
        self.episode_repo = LibraryEpisodeRepository()
        self.artifact_repo = LibraryFileArtifactRepository()
        self.download_service = default_download_service
        self.transfer_service = default_transfer_service

    async def repair(self, items: list[DirectoryIntegrityItem]) -> DirectoryIntegrityRepairResult:
        repaired = 0
        failed = 0
        refreshed_task_ids: set[str] = set()
        for item in items:
            try:
                await self._repair_item(item)
                repaired += 1
                if item.task_id and self._repair_should_refresh_task_health(item):
                    refreshed_task_ids.add(item.task_id)
            except (AppException, OSError, RuntimeError, ValueError) as exc:
                failed += 1
                logger.warning("Failed to repair directory integrity item %s: %s", item.id, exc)
        for task_id in sorted(refreshed_task_ids):
            await self.download_service.refresh_completed_task_health(task_id)
        return DirectoryIntegrityRepairResult(
            requested_count=len(items),
            repaired_count=repaired,
            failed_count=failed,
        )

    async def _repair_item(self, item: DirectoryIntegrityItem) -> None:
        if item.issue_type in {
            DirectoryIntegrityIssueType.unmanaged_library_file,
            DirectoryIntegrityIssueType.unmanaged_download_entry,
        }:
            await asyncio.to_thread(self._delete_path, Path(item.path))
            return
        if self._should_remove_library_record(item):
            await self.episode_repo.remove_by_file_ids([item.library_file_id])
            await self.artifact_repo.remove_by_library_file_ids([item.library_file_id])
            await self.library_repo.remove_by_ids([item.library_file_id])
            return
        if item.issue_type == DirectoryIntegrityIssueType.task_missing_library_file and item.task_id:
            await self.transfer_service.perform_transfer_by_task_id(item.task_id)

    @staticmethod
    def _should_remove_library_record(item: DirectoryIntegrityItem) -> bool:
        return bool(
            item.library_file_id
            and item.issue_type
            in {
                DirectoryIntegrityIssueType.missing_library_file,
                DirectoryIntegrityIssueType.library_file_missing_task,
            }
        )

    @staticmethod
    def _repair_should_refresh_task_health(item: DirectoryIntegrityItem) -> bool:
        return item.issue_type in {
            DirectoryIntegrityIssueType.missing_download_file,
            DirectoryIntegrityIssueType.missing_downloader_torrent,
            DirectoryIntegrityIssueType.unhealthy_downloader_torrent,
        }

    @staticmethod
    def _delete_path(path: Path) -> None:
        if path.is_symlink():
            return
        if path.is_dir():
            shutil.rmtree(path)
            return
        if path.exists():
            path.unlink()
