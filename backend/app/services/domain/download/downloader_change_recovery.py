from __future__ import annotations

import logging
from datetime import datetime

from app.schemas.domain.download import TaskData, TaskStatus
from app.schemas.domain.task_storage_migration import TaskStorageMigration, TaskStorageMigrationPhase, TaskStorageMigrationStatus
from app.services.domain.download.downloader_change_file_ops import rollback_content_move_if_needed
from app.services.domain.download.downloader_change_side_effects import emit_migration_failed, mark_migration_action_failed
from app.utils.library_paths import build_download_path


logger = logging.getLogger(__name__)


class TaskStorageMigrationRecovery:
    def __init__(self, *, task_repo, migration_repo, client_factory) -> None:
        self._task_repo = task_repo
        self._migration_repo = migration_repo
        self._client_factory = client_factory

    async def fail_migration(self, task: TaskData, migration: TaskStorageMigration, reason: str) -> None:
        if not rollback_content_move_if_needed(migration):
            logger.warning(
                "Failed to rollback content after storage migration failure: task_id=%s hash=%s reason=%s source=%s target=%s",
                task.id,
                migration.torrent_hash,
                reason,
                migration.source_content_path,
                migration.target_content_path,
            )
        await self._restore_same_downloader_location_if_needed(task, migration, reason)
        await self._cleanup_target_if_created(task, migration, reason)
        await self._mark_migration_failed(migration, reason)
        await self._restore_task_status_if_needed(task, migration)
        await self._resume_source_if_needed(task, migration, reason)
        mark_migration_action_failed(migration, reason)
        emit_migration_failed(task, migration, reason)

    async def _cleanup_target_if_created(self, task: TaskData, migration: TaskStorageMigration, reason: str) -> None:
        if not migration.target_added_by_migration:
            return
        target_client = self._client_factory.get_download_client(migration.target_downloader_id)
        if not await target_client.delete_torrent(migration.torrent_hash, delete_files=False):
            logger.warning(
                "Failed to cleanup target torrent after storage migration failure: task_id=%s hash=%s reason=%s target_downloader_id=%s",
                task.id,
                migration.torrent_hash,
                reason,
                migration.target_downloader_id,
            )

    async def _restore_same_downloader_location_if_needed(self, task: TaskData, migration: TaskStorageMigration, reason: str) -> None:
        if migration.source_downloader_id != migration.target_downloader_id:
            return
        if migration.source_save_path == migration.target_save_path:
            return
        source_client = self._client_factory.get_download_client(migration.source_downloader_id)
        source_location = str(build_download_path(migration.source_save_path).resolve(strict=False))
        if not await source_client.set_torrent_location([migration.torrent_hash], source_location):
            logger.warning(
                "Failed to restore torrent location after storage migration failure: task_id=%s hash=%s reason=%s source_save_path=%s",
                task.id,
                migration.torrent_hash,
                reason,
                migration.source_save_path,
            )

    async def _mark_migration_failed(self, migration: TaskStorageMigration, reason: str) -> None:
        if reason not in migration.blockers:
            migration.blockers.append(reason)
        migration.reason = reason
        migration.status = TaskStorageMigrationStatus.FAILED
        migration.phase = TaskStorageMigrationPhase.FAILED
        migration.finalized_at = datetime.now()
        await self._migration_repo.update(migration)

    async def _restore_task_status_if_needed(self, task: TaskData, migration: TaskStorageMigration) -> None:
        if task.status != TaskStatus.MIGRATING and task.status == migration.previous_task_status:
            return
        task.status = migration.previous_task_status
        task.updated_at = datetime.now()
        await self._task_repo.update_task(task)

    async def _resume_source_if_needed(self, task: TaskData, migration: TaskStorageMigration, reason: str) -> None:
        if not migration.source_paused or migration.previous_task_status == TaskStatus.PAUSED or not migration.source_downloader_id:
            return
        source_client = self._client_factory.get_download_client(migration.source_downloader_id)
        if not await source_client.start_torrents([migration.torrent_hash]):
            logger.warning("Failed to resume source torrent after storage migration failure: task_id=%s hash=%s reason=%s", task.id, migration.torrent_hash, reason)
