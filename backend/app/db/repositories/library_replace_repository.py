from __future__ import annotations

import time
import uuid
from pathlib import Path

from sqlalchemy import delete, select, tuple_

from app.db.sql.models import LibraryEpisodeORM, LibraryFileORM, LibraryMetaORM
from app.db.sql.session import SessionLocal
from app.schemas.media_id import MediaID
from app.schemas.domain.download import TransferFileResult
from app.schemas.domain.library import LibraryFile
from app.schemas.domain.resource_attributes import ResourceAttributes
from app.utils.library_paths import build_library_file_path, split_library_storage_path


class LibraryReplaceRepository:
    async def replace_task_entries(
        self,
        task_id: str,
        directory_id: str,
        media_id: MediaID,
        transfer_results: list[TransferFileResult],
        season: int | None = None,
        replacement_files: list[LibraryFile] | None = None,
    ) -> list[LibraryFile]:
        existing_files = await self._find_existing_files(task_id)
        conflicting_files = await self._find_conflicting_files(task_id, transfer_results)
        replacement_files = replacement_files or []
        existing_file_ids = [library_file.id for library_file in existing_files if library_file.id]
        conflicting_file_ids = [library_file.id for library_file in conflicting_files if library_file.id]
        replacement_file_ids = [library_file.id for library_file in replacement_files if library_file.id]
        existing_paths = {
            build_library_file_path(library_file.path, library_file.file_name): library_file
            for library_file in [*existing_files, *conflicting_files, *replacement_files]
        }

        with SessionLocal.begin() as session:
            self._upsert_library_meta(session, media_id)

            if existing_file_ids:
                session.execute(delete(LibraryEpisodeORM).where(LibraryEpisodeORM.file_id.in_(existing_file_ids)))
                session.execute(delete(LibraryFileORM).where(LibraryFileORM.task_id == task_id))
            if conflicting_file_ids:
                session.execute(delete(LibraryEpisodeORM).where(LibraryEpisodeORM.file_id.in_(conflicting_file_ids)))
                session.execute(delete(LibraryFileORM).where(LibraryFileORM.id.in_(conflicting_file_ids)))
            if replacement_file_ids:
                session.execute(delete(LibraryEpisodeORM).where(LibraryEpisodeORM.file_id.in_(replacement_file_ids)))
                session.execute(delete(LibraryFileORM).where(LibraryFileORM.id.in_(replacement_file_ids)))

            for transfer_result in transfer_results:
                self._insert_transfer_result(
                    session,
                    task_id,
                    directory_id,
                    media_id,
                    transfer_result,
                    season,
                    existing_paths,
                )

        return self._merge_library_files(existing_files, conflicting_files, replacement_files)

    async def _find_existing_files(self, task_id: str) -> list[LibraryFile]:
        with SessionLocal() as session:
            rows = session.execute(select(LibraryFileORM).where(LibraryFileORM.task_id == task_id)).scalars().all()
            return [
                LibraryFile.model_validate(
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
                for row in rows
            ]

    async def _find_conflicting_files(
        self,
        task_id: str,
        transfer_results: list[TransferFileResult],
    ) -> list[LibraryFile]:
        path_keys = []
        for transfer_result in transfer_results:
            normalized_dir, normalized_name = split_library_storage_path(transfer_result.destination_path)
            path_keys.append((normalized_dir, normalized_name))
        if not path_keys:
            return []

        with SessionLocal() as session:
            rows = (
                session.execute(
                    select(LibraryFileORM).where(
                        LibraryFileORM.task_id != task_id,
                        tuple_(LibraryFileORM.path, LibraryFileORM.file_name).in_(path_keys),
                    )
                )
                .scalars()
                .all()
            )
            return [
                LibraryFile.model_validate(
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
                for row in rows
            ]

    def _merge_library_files(
        self,
        existing_files: list[LibraryFile],
        conflicting_files: list[LibraryFile],
        replacement_files: list[LibraryFile],
    ) -> list[LibraryFile]:
        merged: dict[str, LibraryFile] = {}
        for library_file in [*existing_files, *conflicting_files, *replacement_files]:
            if library_file.id:
                merged[library_file.id] = library_file
        return list(merged.values())

    def _upsert_library_meta(self, session, media_id: MediaID) -> None:
        media_id_str = str(media_id)
        row = session.execute(select(LibraryMetaORM).where(LibraryMetaORM.media_id == media_id_str)).scalars().first()
        now = time.time()
        if row is None:
            session.add(
                LibraryMetaORM(
                    media_id=media_id_str,
                    status="planned",
                    created_at=now,
                    updated_at=now,
                )
            )
            return
        row.updated_at = now

    def _insert_transfer_result(
        self,
        session,
        task_id: str,
        directory_id: str,
        media_id: MediaID,
        transfer_result: TransferFileResult,
        season: int | None,
        existing_paths: dict[Path, LibraryFile],
    ) -> None:
        file_item = transfer_result.file_item
        if season is not None:
            if not file_item.attrs:
                file_item.attrs = ResourceAttributes()
            file_item.attrs.seasons = [season]

        destination_path = Path(transfer_result.destination_path)
        final_path, final_file_name = split_library_storage_path(str(destination_path))

        existing_file = existing_paths[destination_path] if destination_path in existing_paths else None
        file_id = existing_file.id if existing_file else str(uuid.uuid4())
        resource_attributes = file_item.attrs if file_item.attrs else ResourceAttributes()

        session.add(
            LibraryFileORM(
                id=file_id,
                task_id=task_id,
                directory_id=directory_id,
                media_id=str(media_id),
                path=final_path,
                file_name=final_file_name,
                file_size=file_item.size,
                file_index=transfer_result.file_index,
                created_at=time.time(),
                resource_attributes_json=resource_attributes.model_dump(mode="json"),
            )
        )

        episode_numbers = transfer_result.episode_numbers or ([transfer_result.episode_number] if transfer_result.episode_number else [])
        if episode_numbers and season is not None:
            now = time.time()
            for episode_number in sorted({int(episode) for episode in episode_numbers if int(episode) > 0}):
                session.add(
                    LibraryEpisodeORM(
                        media_id=str(media_id),
                        season=season,
                        episode=episode_number,
                        file_id=file_id,
                        created_at=now,
                    )
                )
