from __future__ import annotations

from datetime import datetime
import logging
from sqlalchemy import delete, desc, select, update

from app.db.sql.models import TaskORM
from app.db.sql.session import SessionLocal
from app.schemas.media_id import MediaID
from app.schemas.domain.download import TaskData, TaskFieldPatch, TaskStatus
from app.schemas.runtime.media_management import MediaTaskSummary

logger = logging.getLogger("app.db.task_repository")


class TaskRepository:
    """SQLite-backed task repository."""

    @staticmethod
    def _to_model(row: TaskORM) -> TaskData:
        payload = {
            "id": row.id,
            "media_id": row.media_id,
            "torrent_hash": row.torrent_hash,
            "status": row.status,
            "error_stage": row.error_stage,
            "progress": row.progress,
            "error_key": row.error_key,
            "error_params": row.error_params_json or {},
            "context": row.context_json,
            "downloader_id": row.downloader_id,
            "download_client": row.download_client,
            "download_client_url": row.download_client_url,
            "save_path": row.save_path,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "metadata": row.metadata_json,
        }
        return TaskData.model_validate(payload)

    def cond_id(self, task_id: str) -> str:
        return task_id

    async def get_all(self) -> list[TaskData]:
        with SessionLocal() as session:
            rows = session.execute(select(TaskORM).order_by(desc(TaskORM.updated_at))).scalars().all()
            return [self._to_model(row) for row in rows]

    async def find_by_id(self, task_id: str) -> TaskData | None:
        with SessionLocal() as session:
            row = session.get(TaskORM, task_id)
            return self._to_model(row) if row else None

    async def find_by_hash(self, torrent_hash: str) -> list[TaskData]:
        with SessionLocal() as session:
            rows = session.execute(
                select(TaskORM)
                .where(TaskORM.torrent_hash == torrent_hash)
                .order_by(desc(TaskORM.updated_at))
            ).scalars().all()
            return [self._to_model(row) for row in rows]

    async def find_by_hash_and_downloader(self, torrent_hash: str, downloader_id: str) -> list[TaskData]:
        with SessionLocal() as session:
            rows = session.execute(
                select(TaskORM)
                .where(TaskORM.torrent_hash == torrent_hash)
                .where(TaskORM.downloader_id == downloader_id)
                .order_by(desc(TaskORM.updated_at))
            ).scalars().all()
            return [self._to_model(row) for row in rows]

    async def find_non_void_by_hash_and_downloader(self, torrent_hash: str, downloader_id: str) -> TaskData | None:
        with SessionLocal() as session:
            rows = session.execute(
                select(TaskORM)
                .where(TaskORM.torrent_hash == torrent_hash)
                .where(TaskORM.downloader_id == downloader_id)
                .where(TaskORM.status != TaskStatus.VOID.value)
                .order_by(desc(TaskORM.updated_at))
                .limit(2)
            ).scalars().all()
            if len(rows) > 1:
                logger.warning(
                    "Expected at most one non-VOID task for downloader=%s hash=%s, found %d",
                    downloader_id,
                    torrent_hash,
                    len(rows),
                )
            row = rows[0] if rows else None
            return self._to_model(row) if row else None

    async def find_by_media_id(self, media_id: MediaID) -> list[TaskData]:
        with SessionLocal() as session:
            rows = session.execute(
                select(TaskORM)
                .where(TaskORM.media_id == str(media_id))
                .order_by(desc(TaskORM.updated_at))
            ).scalars().all()
            return [self._to_model(row) for row in rows]

    async def find_by_directory_id(self, directory_id: str) -> list[TaskData]:
        tasks = await self.get_all()
        return [task for task in tasks if task.context and task.context.directory_id == directory_id and task.status != TaskStatus.VOID]

    async def find_by_statuses(self, statuses: list[TaskStatus], limit: int | None = None, offset: int = 0) -> list[TaskData]:
        values = [s.value for s in statuses]
        with SessionLocal() as session:
            stmt = select(TaskORM).where(TaskORM.status.in_(values)).order_by(desc(TaskORM.updated_at))
            if offset:
                stmt = stmt.offset(offset)
            if limit is not None:
                stmt = stmt.limit(limit)
            rows = session.execute(stmt).scalars().all()
            return [self._to_model(row) for row in rows]

    async def find_by_ids(self, task_ids: list[str]) -> list[TaskData]:
        if not task_ids:
            return []
        with SessionLocal() as session:
            rows = session.execute(
                select(TaskORM).where(TaskORM.id.in_(task_ids)).order_by(desc(TaskORM.updated_at))
            ).scalars().all()
            return [self._to_model(row) for row in rows]

    async def insert(self, task: TaskData) -> str:
        with SessionLocal() as session:
            session.add(
                TaskORM(
                    id=task.id,
                    media_id=str(task.media_id),
                    provider=task.media_id.provider.value if task.media_id else None,
                    provider_item_id=task.media_id.id if task.media_id else None,
                    torrent_hash=task.torrent_hash,
                    status=task.status.value,
                    error_stage=task.error_stage.value if task.error_stage else None,
                    progress=task.progress,
                    error_key=task.error_key,
                    error_params_json=task.error_params,
                    context_json=task.context.model_dump(mode="json"),
                    downloader_id=task.downloader_id,
                    download_client=task.download_client,
                    download_client_url=task.download_client_url,
                    save_path=task.save_path,
                    created_at=task.created_at.isoformat(),
                    updated_at=task.updated_at.isoformat(),
                    metadata_json=task.metadata.model_dump(mode="json") if task.metadata else None,
                )
            )
            session.commit()
            return task.id

    async def update_task(self, task: TaskData) -> bool:
        return await self.update(task, self.cond_id(task.id))

    async def update(self, task: TaskData, cond: str) -> bool:
        task_id = cond
        values = {
            "media_id": str(task.media_id),
            "provider": task.media_id.provider.value if task.media_id else None,
            "provider_item_id": task.media_id.id if task.media_id else None,
            "torrent_hash": task.torrent_hash,
            "status": task.status.value,
            "error_stage": task.error_stage.value if task.error_stage else None,
            "progress": task.progress,
            "error_key": task.error_key,
            "error_params_json": task.error_params,
            "context_json": task.context.model_dump(mode="json"),
            "downloader_id": task.downloader_id,
            "download_client": task.download_client,
            "download_client_url": task.download_client_url,
            "save_path": task.save_path,
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat(),
            "metadata_json": task.metadata.model_dump(mode="json") if task.metadata else None,
        }
        with SessionLocal() as session:
            result = session.execute(update(TaskORM).where(TaskORM.id == task_id).values(**values))
            session.commit()
            return bool(result.rowcount)

    async def update_fields(self, fields: TaskFieldPatch, cond: str) -> bool:
        task_id = cond
        values = fields.model_dump(mode="json", exclude_unset=True)
        if "error_params" in values:
            values["error_params_json"] = values.pop("error_params")
        with SessionLocal() as session:
            result = session.execute(update(TaskORM).where(TaskORM.id == task_id).values(**values))
            session.commit()
            return bool(result.rowcount)

    async def delete_by_id(self, task_id: str) -> bool:
        with SessionLocal() as session:
            result = session.execute(delete(TaskORM).where(TaskORM.id == task_id))
            session.commit()
            return bool(result.rowcount)

    async def find_with_filters(
        self,
        status: list[str] | None = None,
        media_id: MediaID | None = None,
        start_time: float | None = None,
        end_time: float | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[TaskData]:
        with SessionLocal() as session:
            stmt = select(TaskORM)
            if media_id:
                stmt = stmt.where(TaskORM.media_id == str(media_id))
            if status:
                stmt = stmt.where(TaskORM.status.in_(status))
            if start_time:
                start_time_value = datetime.fromtimestamp(start_time).isoformat()
                stmt = stmt.where(TaskORM.updated_at >= start_time_value)
            if end_time:
                end_time_value = datetime.fromtimestamp(end_time).isoformat()
                stmt = stmt.where(TaskORM.updated_at <= end_time_value)
            stmt = stmt.order_by(desc(TaskORM.updated_at))
            if offset:
                stmt = stmt.offset(offset)
            if limit is not None:
                stmt = stmt.limit(limit)
            rows = session.execute(stmt).scalars().all()
            return [self._to_model(row) for row in rows]

    async def list_media_ids(self) -> list[MediaID]:
        with SessionLocal() as session:
            rows = session.execute(
                select(TaskORM.media_id).where(TaskORM.media_id.is_not(None)).distinct()
            ).scalars().all()
            return [MediaID.parse(media_id) for media_id in rows]

    async def summarize_by_media_ids(self, media_ids: list[MediaID]) -> dict[str, MediaTaskSummary]:
        if not media_ids:
            return {}
        media_id_values = [str(media_id) for media_id in media_ids]
        with SessionLocal() as session:
            rows = session.execute(
                select(
                    TaskORM.media_id,
                    TaskORM.status,
                    TaskORM.error_key,
                    TaskORM.error_params_json,
                    TaskORM.updated_at,
                )
                .where(TaskORM.media_id.in_(media_id_values))
                .order_by(TaskORM.media_id.asc(), desc(TaskORM.updated_at))
            ).all()

        summaries: dict[str, MediaTaskSummary] = {}
        for media_id_value, status, error_key, error_params, updated_at in rows:
            if media_id_value not in summaries:
                summaries[media_id_value] = MediaTaskSummary(
                    media_id=media_id_value,
                    last_task_at=datetime.fromisoformat(updated_at) if updated_at else None,
                    last_task_message_key=error_key or f"taskStatus.status.{status}",
                    last_task_message_params=error_params or {},
                )
            summary = summaries[media_id_value]
            summary.task_count += 1
            if status in {
                TaskStatus.PENDING.value,
                TaskStatus.DOWNLOADING.value,
                TaskStatus.PAUSED.value,
                TaskStatus.FINISHED.value,
                TaskStatus.TRANSFERRING.value,
            }:
                summary.active_task_count += 1
            if status == TaskStatus.ERROR.value:
                summary.error_task_count += 1
            if status in {TaskStatus.FILE_MISSING.value, TaskStatus.PARTIAL_MISSING.value}:
                summary.file_missing_task_count += 1
            if status == TaskStatus.SEEDING_ABSENT.value:
                summary.seeding_absent_task_count += 1
        return summaries
