from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, func, select, update

from app.db.sql.models import LibraryFileORM
from app.db.sql.session import SessionLocal
from app.schemas.media_id import MediaID
from app.schemas.domain.library import LibraryFile
from app.schemas.runtime.media_management import MediaLibrarySummary
from app.utils.library_paths import split_library_storage_path


class LibraryFileRepository:
    @staticmethod
    def _to_model(row: LibraryFileORM) -> LibraryFile:
        return LibraryFile.model_validate(
            {
                "id": row.id,
                "task_id": row.task_id,
                "directory_id": row.directory_id,
                "media_id": row.media_id,
                "path": row.path,
                "file_name": row.file_name,
                "file_size": row.file_size,
                "file_index": row.file_index,
                "created_at": row.created_at,
                "resource_attributes": row.resource_attributes_json,
            }
        )

    async def get_all(self) -> list[LibraryFile]:
        with SessionLocal() as session:
            rows = session.execute(select(LibraryFileORM)).scalars().all()
            return [self._to_model(row) for row in rows]

    async def insert(self, file: LibraryFile) -> str:
        with SessionLocal() as session:
            session.add(
                LibraryFileORM(
                    id=file.id,
                    task_id=file.task_id,
                    directory_id=file.directory_id,
                    media_id=str(file.media_id) if file.media_id else None,
                    path=file.path,
                    file_name=file.file_name,
                    file_size=file.file_size,
                    file_index=file.file_index,
                    created_at=file.created_at,
                    resource_attributes_json=file.resource_attributes.model_dump(mode="json"),
                )
            )
            session.commit()
            return file.id

    async def find_one_by_id(self, file_id: str) -> LibraryFile | None:
        with SessionLocal() as session:
            row = session.get(LibraryFileORM, file_id)
            return self._to_model(row) if row else None

    async def find_by_task_id(self, task_id: str) -> list[LibraryFile]:
        with SessionLocal() as session:
            rows = session.execute(select(LibraryFileORM).where(LibraryFileORM.task_id == task_id)).scalars().all()
            return [self._to_model(row) for row in rows]

    async def find_by_task_ids(self, task_ids: list[str]) -> list[LibraryFile]:
        if not task_ids:
            return []
        with SessionLocal() as session:
            rows = session.execute(
                select(LibraryFileORM).where(LibraryFileORM.task_id.in_(task_ids))
            ).scalars().all()
            return [self._to_model(row) for row in rows]

    async def find_by_media_id(self, media_id: MediaID) -> list[LibraryFile]:
        with SessionLocal() as session:
            rows = session.execute(
                select(LibraryFileORM).where(LibraryFileORM.media_id == str(media_id))
            ).scalars().all()
            return [self._to_model(row) for row in rows]

    async def find_by_media_id_and_directory_ids(self, media_id: MediaID, directory_ids: list[str]) -> list[LibraryFile]:
        if not directory_ids:
            return []
        with SessionLocal() as session:
            rows = session.execute(
                select(LibraryFileORM).where(
                    LibraryFileORM.media_id == str(media_id),
                    LibraryFileORM.directory_id.in_(directory_ids),
                )
            ).scalars().all()
            return [self._to_model(row) for row in rows]

    async def find_by_media_ids(self, media_ids: list[MediaID]) -> list[LibraryFile]:
        values = [str(media_id) for media_id in media_ids]
        if not values:
            return []
        with SessionLocal() as session:
            rows = session.execute(
                select(LibraryFileORM).where(LibraryFileORM.media_id.in_(values))
            ).scalars().all()
            return [self._to_model(row) for row in rows]

    async def find_by_path(self, path: str) -> LibraryFile | None:
        normalized_dir, normalized_name = split_library_storage_path(path)
        with SessionLocal() as session:
            row = session.execute(
                select(LibraryFileORM).where(
                    LibraryFileORM.path == normalized_dir,
                    LibraryFileORM.file_name == normalized_name,
                )
            ).scalars().first()
            return self._to_model(row) if row else None

    async def find_by_ids(self, ids: list[str]) -> list[LibraryFile]:
        if not ids:
            return []
        with SessionLocal() as session:
            rows = session.execute(select(LibraryFileORM).where(LibraryFileORM.id.in_(ids))).scalars().all()
            return [self._to_model(row) for row in rows]

    async def find_by_directory_id(self, directory_id: str) -> list[LibraryFile]:
        with SessionLocal() as session:
            rows = session.execute(
                select(LibraryFileORM).where(LibraryFileORM.directory_id == directory_id)
            ).scalars().all()
            return [self._to_model(row) for row in rows]

    async def remove_by_task_id(self, task_id: str) -> int:
        with SessionLocal() as session:
            result = session.execute(delete(LibraryFileORM).where(LibraryFileORM.task_id == task_id))
            session.commit()
            return int(result.rowcount or 0)

    async def remove_by_ids(self, ids: list[str]) -> int:
        if not ids:
            return 0
        with SessionLocal() as session:
            result = session.execute(delete(LibraryFileORM).where(LibraryFileORM.id.in_(ids)))
            session.commit()
            return int(result.rowcount or 0)

    async def update_task_id(self, file_id: str, new_task_id: str) -> bool:
        with SessionLocal() as session:
            result = session.execute(
                update(LibraryFileORM).where(LibraryFileORM.id == file_id).values(task_id=new_task_id)
            )
            session.commit()
            return bool(result.rowcount)

    async def update_task_binding(self, file_id: str, *, task_id: str, directory_id: str) -> bool:
        with SessionLocal() as session:
            result = session.execute(
                update(LibraryFileORM)
                .where(LibraryFileORM.id == file_id)
                .values(task_id=task_id, directory_id=directory_id)
            )
            session.commit()
            return bool(result.rowcount)

    async def update_location(self, file_id: str, *, directory_id: str, path: str, file_name: str) -> bool:
        with SessionLocal() as session:
            result = session.execute(
                update(LibraryFileORM)
                .where(LibraryFileORM.id == file_id)
                .values(directory_id=directory_id, path=path, file_name=file_name)
            )
            session.commit()
            return bool(result.rowcount)

    async def count_by_directory_id(self, directory_id: str) -> int:
        return self.count_by_directory_id_sync(directory_id)

    def count_by_directory_id_sync(self, directory_id: str) -> int:
        with SessionLocal() as session:
            return int(
                session.execute(
                    select(func.count())
                    .select_from(LibraryFileORM)
                    .where(LibraryFileORM.directory_id == directory_id)
                ).scalar_one() or 0
            )

    async def list_media_ids_by_directory_ids(self, directory_ids: list[str]) -> list[MediaID]:
        if not directory_ids:
            return []
        with SessionLocal() as session:
            rows = session.execute(
                select(LibraryFileORM.media_id)
                .where(
                    LibraryFileORM.directory_id.in_(directory_ids),
                    LibraryFileORM.media_id.is_not(None),
                )
                .distinct()
            ).all()
            return [MediaID.parse(media_id) for media_id, in rows]

    async def list_media_ids(self) -> list[MediaID]:
        with SessionLocal() as session:
            rows = session.execute(
                select(LibraryFileORM.media_id)
                .where(LibraryFileORM.media_id.is_not(None))
                .distinct()
            ).all()
            return [MediaID.parse(media_id) for media_id, in rows]

    async def summarize_by_media_ids(self, media_ids: list[MediaID]) -> dict[str, MediaLibrarySummary]:
        if not media_ids:
            return {}
        media_id_values = [str(media_id) for media_id in media_ids]
        with SessionLocal() as session:
            rows = session.execute(
                select(
                    LibraryFileORM.id,
                    LibraryFileORM.file_size,
                    LibraryFileORM.created_at,
                    LibraryFileORM.media_id,
                )
                .select_from(LibraryFileORM)
                .where(LibraryFileORM.media_id.in_(media_id_values))
            ).all()

        summaries: dict[str, MediaLibrarySummary] = {}
        seen_file_ids: set[tuple[str, str]] = set()
        for file_id, file_size, created_at, media_id_value in rows:
            if not media_id_value:
                continue
            dedupe_key = (media_id_value, file_id)
            if dedupe_key in seen_file_ids:
                continue
            seen_file_ids.add(dedupe_key)

            created_at_value = datetime.fromtimestamp(created_at) if created_at is not None else None
            if media_id_value not in summaries:
                summaries[media_id_value] = MediaLibrarySummary(
                    media_id=media_id_value,
                    last_library_at=created_at_value,
                )
            summary = summaries[media_id_value]
            summary.library_count += 1
            summary.library_size += file_size or 0
            if created_at_value and (summary.last_library_at is None or created_at_value > summary.last_library_at):
                summary.last_library_at = created_at_value
        return summaries
