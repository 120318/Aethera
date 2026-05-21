from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from app.schemas.config import DirectoryConfig, DownloaderConfig
from app.schemas.domain.download import TaskData, TaskStatus
from app.schemas.domain.task_storage_migration import TaskStorageMigration, TaskStorageMigrationPhase, TaskStorageMigrationStatus
from app.schemas.exception.exceptions import DownloadException, ResourceNotFoundException
from app.db.repositories.task_storage_migration_repository import TaskStorageMigrationRepository
from app.services.config.settings_service import settings_service
from app.services.domain.library.service import library_service
from app.services.domain.download.downloader_change_side_effects import (
    create_migration_action,
    emit_change_failed,
    emit_change_started,
    emit_change_succeeded,
    mark_migration_action_completed,
)
from app.services.domain.download.downloader_change_file_ops import (
    move_content_if_needed,
    move_task_library_files,
)
from app.services.domain.download.downloader_change_preview import (
    TaskDownloaderChangePreview,
    TaskDownloaderChangeRequest,
    build_change_preview,
    resolve_content_path,
)
from app.services.domain.download.downloader_change_recovery import TaskStorageMigrationRecovery
from app.services.integration.download.client import DownloadClient
from app.services.integration.torrent.service import torrent_service
from app.services.platform.domain_lock_service import domain_lock_service
from app.utils.library_paths import build_library_file_path


logger = logging.getLogger(__name__)


class TaskDownloaderChangeService:
    def __init__(self, repo, client_factory) -> None:
        self._repo = repo
        self._client_factory = client_factory
        self._migration_repo = TaskStorageMigrationRepository()
        self._recovery = TaskStorageMigrationRecovery(task_repo=repo, migration_repo=self._migration_repo, client_factory=client_factory)

    async def preview(self, task_id: str, request: TaskDownloaderChangeRequest) -> TaskDownloaderChangePreview:
        task = await self._load_task(task_id)
        target_downloader = self._load_downloader(request.target_downloader_id)
        target_directory = self._load_directory(request.target_directory_id)
        return await build_change_preview(
            task=task,
            target_downloader=target_downloader,
            target_directory=target_directory,
            source_client=self._load_task_client(task),
            target_client=self._client_factory.get_download_client(target_downloader.id),
        )

    async def execute(self, task_id: str, request: TaskDownloaderChangeRequest) -> TaskDownloaderChangePreview:
        async with domain_lock_service.acquire_task_op(task_id) as acquired:
            if not acquired:
                raise DownloadException("backendErrors.taskBusy")
            task = await self._load_task(task_id)
            active_migration = await self._migration_repo.find_active_by_task(task.id)
            if active_migration or task.status == TaskStatus.MIGRATING:
                preview = await self.preview(task_id, request)
                return self._mark_failed(preview, task, "migration_already_active")
            target_downloader = self._load_downloader(request.target_downloader_id)
            target_directory = self._load_directory(request.target_directory_id)
            preview = await self.preview(task_id, request)
            if not preview.ok:
                return self._mark_failed(preview, task, "preview_blocked")

            lock_keys = self._storage_lock_keys(preview)
            async with domain_lock_service.acquire_storage_ops(lock_keys) as storage_acquired:
                if not storage_acquired:
                    return self._mark_failed(preview, task, "storage_busy")
                return await self._execute_locked(task, target_downloader, target_directory, preview, request)

    async def _execute_locked(
        self,
        task: TaskData,
        target_downloader: DownloaderConfig,
        target_directory: DirectoryConfig,
        preview: TaskDownloaderChangePreview,
        request: TaskDownloaderChangeRequest,
    ) -> TaskDownloaderChangePreview:
        source_client = self._load_task_client(task)
        target_client = self._client_factory.get_download_client(target_downloader.id)
        same_downloader = task.downloader_id == target_downloader.id
        source_info = await source_client.get_torrent_info(task.torrent_hash) if source_client else None
        target_info = await target_client.get_torrent_info(task.torrent_hash)

        migration = TaskStorageMigration(
            task_id=task.id,
            torrent_hash=task.torrent_hash,
            source_downloader_id=task.downloader_id or "",
            target_downloader_id=target_downloader.id,
            source_directory_id=task.context.directory_id or "",
            target_directory_id=target_directory.id,
            source_save_path=task.save_path or "",
            target_save_path=preview.target_save_path or "",
            source_content_path=preview.current_content_path,
            target_content_path=preview.target_content_path,
            previous_task_status=task.status,
            move_content=preview.move_content,
            cleanup_source_torrent=request.cleanup_source_torrent,
            status=TaskStorageMigrationStatus.PENDING,
            phase=TaskStorageMigrationPhase.PREPARED,
        )
        migration.action_id = create_migration_action(task, migration)
        await self._migration_repo.insert(migration)

        if source_client and source_info and not await source_client.pause_torrents([task.torrent_hash]):
            await self._recovery.fail_migration(task, migration, "source_pause_failed")
            return self._mark_recovered_failed(preview, "source_pause_failed")
        if source_client and source_info:
            migration.source_paused = True
            migration.phase = TaskStorageMigrationPhase.SOURCE_PAUSED
            await self._migration_repo.update(migration)

        torrent_blob = None
        if not target_info:
            if not source_client:
                await self._recovery.fail_migration(task, migration, "source_downloader_missing")
                return self._mark_recovered_failed(preview, "source_downloader_missing")
            torrent_blob = torrent_service.load_stored_blob(task.torrent_hash)
            if not torrent_blob:
                torrent_blob = await source_client.export_torrent(task.torrent_hash)
            if not torrent_blob:
                await self._recovery.fail_migration(task, migration, "source_torrent_export_failed")
                return self._mark_recovered_failed(preview, "source_torrent_export_failed")

        if not target_info and torrent_blob:
            result = await target_client.add_torrent_file(
                torrent_data=torrent_blob,
                save_path=target_directory.download_path,
                category=target_directory.download_category,
                file_priorities=self._build_file_priorities(task),
                torrent_hash=task.torrent_hash,
                tags=source_info.tags if source_info and source_info.tags else None,
                is_paused=True,
            )
            if not result.success:
                await self._recovery.fail_migration(task, migration, "target_add_torrent_failed")
                return self._mark_recovered_failed(preview, "target_add_torrent_failed")
            migration.target_added_by_migration = True
            migration.phase = TaskStorageMigrationPhase.TARGET_READY
            await self._migration_repo.update(migration)
        elif target_info:
            migration.phase = TaskStorageMigrationPhase.TARGET_READY
            await self._migration_repo.update(migration)

        if not await self._sync_target_file_priorities(target_client, task):
            await self._recovery.fail_migration(task, migration, "target_file_priority_sync_failed")
            return self._mark_recovered_failed(preview, "target_file_priority_sync_failed")
        target_info = await target_client.get_torrent_info(task.torrent_hash)
        if not target_info:
            await self._recovery.fail_migration(task, migration, "target_torrent_missing_after_add")
            return self._mark_recovered_failed(preview, "target_torrent_missing_after_add")

        move_error = move_content_if_needed(
            move_content=preview.move_content,
            source_path=preview.current_content_path,
            target_path=preview.target_content_path,
        )
        if move_error:
            preview.blockers.append(move_error)
            preview.ok = False
        if preview.blockers:
            await self._recovery.fail_migration(task, migration, "content_move_failed")
            return self._mark_recovered_failed(preview, "content_move_failed")
        if preview.move_content and preview.current_content_path and preview.target_content_path and Path(preview.target_content_path).exists():
            migration.content_moved = True
            migration.phase = TaskStorageMigrationPhase.CONTENT_MOVED
            await self._migration_repo.update(migration)

        if same_downloader and migration.source_save_path != migration.target_save_path:
            if not await target_client.set_torrent_location([task.torrent_hash], target_directory.download_path):
                await self._recovery.fail_migration(task, migration, "target_location_update_failed")
                return self._mark_recovered_failed(preview, "target_location_update_failed")

        if not await target_client.recheck_torrents([task.torrent_hash]):
            await self._recovery.fail_migration(task, migration, "target_recheck_failed")
            return self._mark_recovered_failed(preview, "target_recheck_failed")

        migration.status = TaskStorageMigrationStatus.CHECKING
        migration.phase = TaskStorageMigrationPhase.CHECKING
        await self._migration_repo.update(migration)

        task.status = TaskStatus.MIGRATING
        task.updated_at = datetime.now()
        await self._repo.update_task(task)
        emit_change_started(task, migration)
        preview.ok = True
        return preview

    async def finalize_active_migrations(self, limit: int = 100) -> int:
        updated = 0
        migrations = await self._migration_repo.list_active(limit=limit)
        for migration in migrations:
            if await self._finalize_migration(migration):
                updated += 1
        return updated

    async def _finalize_migration(self, migration: TaskStorageMigration) -> bool:
        async with domain_lock_service.acquire_task_op(migration.task_id) as acquired:
            if not acquired:
                return False
            async with domain_lock_service.acquire_storage_ops(self._migration_storage_lock_keys(migration)) as storage_acquired:
                if not storage_acquired:
                    return False
                task = await self._load_task(migration.task_id)
                target_client = self._client_factory.get_download_client(migration.target_downloader_id)
                target_info = await target_client.get_torrent_info(migration.torrent_hash)
                if not target_info:
                    await self._recovery.fail_migration(task, migration, "target_torrent_missing")
                    return True
                state = (target_info.state or "").lower()
                allow_paused_incomplete = (
                    migration.previous_task_status == TaskStatus.PAUSED
                    and target_info.progress is not None
                    and target_info.progress < 0.999
                    and ("paused" in state or "stopped" in state)
                )
                if not allow_paused_incomplete and (target_info.progress is None or target_info.progress < 0.999):
                    if migration.previous_task_status in {TaskStatus.PENDING, TaskStatus.DOWNLOADING} and ("paused" in state or "stopped" in state):
                        await target_client.start_torrents([migration.torrent_hash])
                    if self._is_target_error_state(state):
                        await self._recovery.fail_migration(task, migration, "target_recheck_failed")
                        return True
                    if self._can_finalize_active_incomplete(migration.previous_task_status, state):
                        pass
                    else:
                        migration.status = TaskStorageMigrationStatus.CHECKING
                        await self._migration_repo.update(migration)
                        return False
                target_content = resolve_content_path(migration.target_save_path, target_info)
                if target_content and not target_content.exists():
                    await self._recovery.fail_migration(task, migration, "target_content_missing")
                    return True
                library_files = await library_service.get_files_by_task(task.id)
                primary_library_files = [item for item in library_files if library_service.is_primary_file(item)]
                for library_file in primary_library_files:
                    library_path = build_library_file_path(library_file.path, library_file.file_name)
                    if not library_path.exists():
                        await self._recovery.fail_migration(task, migration, "library_file_missing")
                        return True
                target_directory_config = self._load_directory(migration.target_directory_id)
                source_directory = self._load_directory(migration.source_directory_id)
                migration.phase = TaskStorageMigrationPhase.COMMITTING
                await self._migration_repo.update(migration)
                if not await move_task_library_files(task, library_files, source_directory, target_directory_config):
                    await self._recovery.fail_migration(task, migration, "library_file_move_failed")
                    return True
                if library_files:
                    migration.library_files_moved = True
                    await self._migration_repo.update(migration)
                if migration.cleanup_source_torrent and migration.source_downloader_id != migration.target_downloader_id:
                    source_client = self._client_factory.get_download_client(migration.source_downloader_id)
                    if not await source_client.delete_torrent(migration.torrent_hash, delete_files=False):
                        migration.warnings.append("source_torrent_cleanup_failed")
                        logger.warning(
                            "Failed to cleanup source torrent after storage migration; migration will finalize: task_id=%s hash=%s source_downloader_id=%s",
                            task.id,
                            migration.torrent_hash,
                            migration.source_downloader_id,
                        )

                target_downloader = self._load_downloader(migration.target_downloader_id)
                task.downloader_id = migration.target_downloader_id
                task.save_path = migration.target_save_path
                task.context.directory_id = migration.target_directory_id
                task.download_client = target_downloader.name or target_downloader.id
                task.download_client_url = target_downloader.url
                task.status = self._status_after_finalize(migration.previous_task_status, target_info.progress)
                if task.status == TaskStatus.FINISHED:
                    task.progress = 1.0
                elif target_info.progress is not None:
                    task.progress = target_info.progress
                task.updated_at = datetime.now()
                await self._repo.update_task(task)

                migration.status = TaskStorageMigrationStatus.FINALIZED
                migration.phase = TaskStorageMigrationPhase.FINALIZED
                migration.finalized_at = datetime.now()
                await self._migration_repo.update(migration)
                mark_migration_action_completed(migration)
                if self._should_start_target_after_finalize(migration.previous_task_status):
                    if not await target_client.start_torrents([migration.torrent_hash]):
                        logger.warning("Failed to start target torrent after storage migration: task_id=%s hash=%s", task.id, migration.torrent_hash)
                emit_change_succeeded(task, migration)
                return True

    def _load_task_client(self, task: TaskData) -> DownloadClient | None:
        if not task.downloader_id:
            return None
        return self._client_factory.get_download_client(task.downloader_id)

    async def _load_task(self, task_id: str) -> TaskData:
        task = await self._repo.find_by_id(task_id)
        if not task:
            raise ResourceNotFoundException("backendErrors.taskNotFound")
        return task

    @staticmethod
    def _load_downloader(downloader_id: str) -> DownloaderConfig:
        downloader = next((item for item in settings_service.list_downloaders() if item.id == downloader_id and item.enabled), None)
        if not downloader:
            raise DownloadException("backendErrors.config.downloaderNotFound")
        return downloader

    @staticmethod
    def _load_directory(directory_id: str) -> DirectoryConfig:
        directory = settings_service.get_directory_by_id(directory_id)
        if not directory or not directory.enabled:
            raise DownloadException("backendErrors.config.directoryNotFound")
        return directory

    @staticmethod
    def _build_file_priorities(task: TaskData) -> list[int] | None:
        files = task.metadata.files if task.metadata else []
        if not files:
            return None
        selected = set(task.context.selected_files or [])
        if not selected:
            return [1 for _ in files]
        return [1 if index in selected else 0 for index, _ in enumerate(files)]

    async def _sync_target_file_priorities(self, target_client: DownloadClient, task: TaskData) -> bool:
        file_priorities = self._build_file_priorities(task)
        if not file_priorities:
            return True
        unselected = [index for index, priority in enumerate(file_priorities) if priority <= 0]
        selected = [index for index, priority in enumerate(file_priorities) if priority > 0]
        if unselected and not await target_client.set_file_priority(task.torrent_hash, unselected, 0):
            return False
        if selected and not await target_client.set_file_priority(task.torrent_hash, selected, 1):
            return False
        return True

    def _mark_failed(self, preview: TaskDownloaderChangePreview, task: TaskData, reason: str) -> TaskDownloaderChangePreview:
        if reason not in preview.blockers:
            preview.blockers.append(reason)
        preview.ok = False
        emit_change_failed(task, preview, reason)
        return preview

    @staticmethod
    def _mark_recovered_failed(preview: TaskDownloaderChangePreview, reason: str) -> TaskDownloaderChangePreview:
        if reason not in preview.blockers:
            preview.blockers.append(reason)
        preview.ok = False
        return preview

    @staticmethod
    def _status_after_finalize(previous: TaskStatus, progress: float | None) -> TaskStatus:
        if previous in {
            TaskStatus.COMPLETED,
            TaskStatus.PARTIAL_MISSING,
            TaskStatus.SEEDING_ABSENT,
            TaskStatus.FILE_MISSING,
        }:
            return previous
        if progress is not None and progress >= 0.999:
            return TaskStatus.FINISHED
        if previous == TaskStatus.PENDING:
            return TaskStatus.DOWNLOADING
        if previous == TaskStatus.DOWNLOADING:
            return TaskStatus.DOWNLOADING
        if previous == TaskStatus.MIGRATING:
            return TaskStatus.FINISHED
        return previous

    @staticmethod
    def _should_start_target_after_finalize(previous: TaskStatus) -> bool:
        return previous != TaskStatus.PAUSED

    @staticmethod
    def _is_target_error_state(state: str) -> bool:
        return any(marker in state for marker in ("error", "missing"))

    @staticmethod
    def _can_finalize_active_incomplete(previous: TaskStatus, state: str) -> bool:
        return previous in {TaskStatus.PENDING, TaskStatus.DOWNLOADING} and "checking" not in state

    @staticmethod
    def _storage_lock_keys(preview: TaskDownloaderChangePreview) -> list[str]:
        return [
            f"directory:{preview.current_directory_id or ''}",
            f"directory:{preview.target_directory_id or ''}",
            f"path:{preview.current_local_path or ''}",
            f"path:{preview.target_local_path or ''}",
        ]

    @staticmethod
    def _migration_storage_lock_keys(migration: TaskStorageMigration) -> list[str]:
        return [
            f"directory:{migration.source_directory_id}",
            f"directory:{migration.target_directory_id}",
            f"path:{migration.source_save_path}",
            f"path:{migration.target_save_path}",
        ]
