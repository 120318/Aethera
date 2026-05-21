from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.repositories.library_file_repository import LibraryFileRepository
from app.db.repositories.media_subscription_settings_repository import MediaSubscriptionSettingsRepository
from app.db.repositories.task_repository import TaskRepository
from app.schemas.config import DirectoryConfig
from app.schemas.domain.download import TaskStatus
from app.schemas.exception.exceptions import DownloadException
from app.services.config.settings_service import settings_service
from app.services.domain.download import download_service
from app.services.domain.download.downloader_change import TaskDownloaderChangeRequest


class DirectoryMigrationRequest(BaseModel):
    target_directory_id: str
    target_downloader_id: str | None = None


class DirectoryMigrationPreview(BaseModel):
    ok: bool
    source_directory_id: str
    target_directory_id: str
    target_downloader_id: str
    task_count: int = 0
    library_file_count: int = 0
    subscription_count: int = 0
    migratable_task_count: int = 0
    blocked_task_count: int = 0
    migratable_subscription_count: int = 0
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DirectoryMigrationDomainService:
    def __init__(self) -> None:
        self._task_repo = TaskRepository()
        self._library_repo = LibraryFileRepository()
        self._subscription_repo = MediaSubscriptionSettingsRepository()

    async def preview(self, source_directory_id: str, request: DirectoryMigrationRequest) -> DirectoryMigrationPreview:
        source_directory = self._load_directory(source_directory_id)
        target_directory = self._load_directory(request.target_directory_id)
        target_downloader_id = request.target_downloader_id or target_directory.downloader_id or ""
        preview = DirectoryMigrationPreview(
            ok=True,
            source_directory_id=source_directory.id,
            target_directory_id=target_directory.id,
            target_downloader_id=target_downloader_id,
        )
        if source_directory.id == target_directory.id:
            preview.blockers.append("same_directory")
        if source_directory.media_type != target_directory.media_type:
            preview.blockers.append("media_type_mismatch")
        if not target_downloader_id:
            preview.blockers.append("target_downloader_missing")
        if not target_directory.download_path:
            preview.blockers.append("target_directory_download_path_missing")
        if not target_directory.path:
            preview.blockers.append("target_directory_path_missing")
        target_downloader = self._load_downloader(target_downloader_id) if target_downloader_id else None
        if target_downloader_id and not target_downloader:
            preview.blockers.append("target_downloader_not_found")

        tasks = await self._task_repo.find_by_directory_id(source_directory.id)
        library_files = await self._library_repo.find_by_directory_id(source_directory.id)
        subscription_count = await self._subscription_repo.count_by_directory_id(source_directory.id)
        preview.task_count = len(tasks)
        preview.library_file_count = len(library_files)
        preview.subscription_count = subscription_count
        preview.migratable_subscription_count = subscription_count
        task_ids = {task.id for task in tasks}
        orphan_library_files = [library_file for library_file in library_files if library_file.task_id not in task_ids]
        if orphan_library_files:
            preview.warnings.append("library_only_files_not_migrated_by_task")
            preview.blockers.append("library_only_files_not_migrated_by_task")

        fatal_task_preview_blockers = {
            "same_directory",
            "media_type_mismatch",
            "target_downloader_missing",
            "target_downloader_not_found",
            "target_directory_download_path_missing",
            "target_directory_path_missing",
        }
        if any(blocker in fatal_task_preview_blockers for blocker in preview.blockers):
            preview.blocked_task_count = len([task for task in tasks if task.status != TaskStatus.MIGRATING])
            preview.ok = False
            return preview

        for task in tasks:
            if task.status == TaskStatus.MIGRATING:
                preview.blocked_task_count += 1
                continue
            if not target_downloader_id:
                preview.blocked_task_count += 1
                continue
            task_preview = await self.preview_task(task.id, target_downloader_id, target_directory.id)
            if task_preview.ok:
                preview.migratable_task_count += 1
            else:
                preview.blocked_task_count += 1
                for blocker in task_preview.blockers:
                    marker = f"{task.id}:{blocker}"
                    if marker not in preview.blockers:
                        preview.blockers.append(marker)

        preview.ok = not preview.blockers and (preview.migratable_task_count > 0 or preview.migratable_subscription_count > 0)
        if preview.task_count == 0 and preview.subscription_count == 0:
            preview.blockers.append("no_tasks_in_directory")
            preview.ok = False
        if preview.task_count == 0 and preview.library_file_count > 0:
            if "library_only_files_not_migrated_by_task" not in preview.blockers:
                preview.blockers.append("library_only_files_not_migrated_by_task")
            preview.ok = False
        return preview

    async def migratable_task_ids(self, source_directory_id: str, preview: DirectoryMigrationPreview) -> list[str]:
        task_ids = []
        tasks = await self._task_repo.find_by_directory_id(source_directory_id)
        for task in tasks:
            if task.status == TaskStatus.MIGRATING:
                continue
            task_preview = await self.preview_task(task.id, preview.target_downloader_id, preview.target_directory_id)
            if task_preview.ok:
                task_ids.append(task.id)
        return task_ids

    async def migrate_subscriptions(self, source_directory_id: str, target_directory_id: str) -> int:
        return await self._subscription_repo.update_directory_id(source_directory_id, target_directory_id)

    async def preview_task(self, task_id: str, target_downloader_id: str, target_directory_id: str):
        return await download_service.preview_task_downloader_change(
            task_id,
            TaskDownloaderChangeRequest(
                target_downloader_id=target_downloader_id,
                target_directory_id=target_directory_id,
            ),
        )

    @staticmethod
    def _load_directory(directory_id: str) -> DirectoryConfig:
        directory = settings_service.get_directory_by_id(directory_id)
        if not directory or not directory.enabled:
            raise DownloadException("backendErrors.config.directoryNotFound")
        return directory

    @staticmethod
    def _load_downloader(downloader_id: str):
        return next((item for item in settings_service.list_downloaders() if item.id == downloader_id and item.enabled), None)


directory_migration_domain_service = DirectoryMigrationDomainService()
