from __future__ import annotations

from datetime import datetime

from sqlalchemy import desc, select

from app.db.sql.models import TaskStorageMigrationORM
from app.db.sql.session import SessionLocal
from app.schemas.domain.task_storage_migration import TaskStorageMigration, TaskStorageMigrationStatus


class TaskStorageMigrationRepository:
    @staticmethod
    def _to_model(row: TaskStorageMigrationORM) -> TaskStorageMigration:
        return TaskStorageMigration.model_validate(
            {
                "id": row.id,
                "action_id": row.action_id,
                "task_id": row.task_id,
                "torrent_hash": row.torrent_hash,
                "source_downloader_id": row.source_downloader_id,
                "target_downloader_id": row.target_downloader_id,
                "source_directory_id": row.source_directory_id,
                "target_directory_id": row.target_directory_id,
                "source_save_path": row.source_save_path,
                "target_save_path": row.target_save_path,
                "source_content_path": row.source_content_path,
                "target_content_path": row.target_content_path,
                "previous_task_status": row.previous_task_status,
                "move_content": bool(row.move_content),
                "cleanup_source_torrent": bool(row.cleanup_source_torrent),
                "phase": row.phase,
                "source_paused": bool(row.source_paused),
                "target_added_by_migration": bool(row.target_added_by_migration),
                "content_moved": bool(row.content_moved),
                "library_files_moved": bool(row.library_files_moved),
                "status": row.status,
                "reason": row.reason,
                "blockers": row.blockers_json or [],
                "warnings": row.warnings_json or [],
                "created_at": row.created_at,
                "updated_at": row.updated_at,
                "finalized_at": row.finalized_at,
            }
        )

    async def insert(self, migration: TaskStorageMigration) -> TaskStorageMigration:
        with SessionLocal() as session:
            row = TaskStorageMigrationORM(
                id=migration.id,
                action_id=migration.action_id,
                task_id=migration.task_id,
                torrent_hash=migration.torrent_hash,
                source_downloader_id=migration.source_downloader_id,
                target_downloader_id=migration.target_downloader_id,
                source_directory_id=migration.source_directory_id,
                target_directory_id=migration.target_directory_id,
                source_save_path=migration.source_save_path,
                target_save_path=migration.target_save_path,
                source_content_path=migration.source_content_path,
                target_content_path=migration.target_content_path,
                previous_task_status=migration.previous_task_status.value,
                move_content=1 if migration.move_content else 0,
                cleanup_source_torrent=1 if migration.cleanup_source_torrent else 0,
                phase=migration.phase.value,
                source_paused=1 if migration.source_paused else 0,
                target_added_by_migration=1 if migration.target_added_by_migration else 0,
                content_moved=1 if migration.content_moved else 0,
                library_files_moved=1 if migration.library_files_moved else 0,
                status=migration.status.value,
                reason=migration.reason,
                blockers_json=list(migration.blockers),
                warnings_json=list(migration.warnings),
                created_at=migration.created_at.isoformat(),
                updated_at=migration.updated_at.isoformat(),
                finalized_at=migration.finalized_at.isoformat() if migration.finalized_at else None,
            )
            session.add(row)
            session.commit()
        return migration

    async def update(self, migration: TaskStorageMigration) -> TaskStorageMigration:
        migration.updated_at = datetime.now()
        with SessionLocal() as session:
            row = session.get(TaskStorageMigrationORM, migration.id)
            if not row:
                return migration
            row.action_id = migration.action_id
            row.phase = migration.phase.value
            row.source_paused = 1 if migration.source_paused else 0
            row.target_added_by_migration = 1 if migration.target_added_by_migration else 0
            row.content_moved = 1 if migration.content_moved else 0
            row.library_files_moved = 1 if migration.library_files_moved else 0
            row.status = migration.status.value
            row.reason = migration.reason
            row.blockers_json = list(migration.blockers)
            row.warnings_json = list(migration.warnings)
            row.updated_at = migration.updated_at.isoformat()
            row.finalized_at = migration.finalized_at.isoformat() if migration.finalized_at else None
            session.commit()
        return migration

    async def find_active_by_task(self, task_id: str) -> TaskStorageMigration | None:
        with SessionLocal() as session:
            row = session.execute(
                select(TaskStorageMigrationORM)
                .where(TaskStorageMigrationORM.task_id == task_id)
                .where(TaskStorageMigrationORM.status.in_([TaskStorageMigrationStatus.PENDING.value, TaskStorageMigrationStatus.CHECKING.value]))
                .order_by(desc(TaskStorageMigrationORM.created_at))
            ).scalars().first()
            return self._to_model(row) if row else None

    async def list_active(self, limit: int = 100) -> list[TaskStorageMigration]:
        with SessionLocal() as session:
            rows = session.execute(
                select(TaskStorageMigrationORM)
                .where(TaskStorageMigrationORM.status.in_([TaskStorageMigrationStatus.PENDING.value, TaskStorageMigrationStatus.CHECKING.value]))
                .order_by(TaskStorageMigrationORM.updated_at)
                .limit(limit)
            ).scalars().all()
            return [self._to_model(row) for row in rows]
