from __future__ import annotations

import time
import uuid

from sqlalchemy import delete, select, update

from app.db.sql.models import LibraryFileArtifactORM
from app.db.sql.session import SessionLocal
from app.schemas.domain.library import LibraryFileArtifact, LibraryFileArtifactStatus, LibraryFileArtifactType


class LibraryFileArtifactRepository:
    @staticmethod
    def _to_model(row: LibraryFileArtifactORM) -> LibraryFileArtifact:
        return LibraryFileArtifact.model_validate(
            {
                "id": row.id,
                "library_file_id": row.library_file_id,
                "artifact_type": row.artifact_type,
                "expected_path": row.expected_path,
                "status": row.status,
                "last_success_at": row.last_success_at,
                "last_error": row.last_error,
                "next_retry_at": row.next_retry_at,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
        )

    async def find_by_library_file_ids(self, library_file_ids: list[str]) -> list[LibraryFileArtifact]:
        if not library_file_ids:
            return []
        with SessionLocal() as session:
            rows = session.execute(
                select(LibraryFileArtifactORM).where(LibraryFileArtifactORM.library_file_id.in_(library_file_ids))
            ).scalars().all()
            return [self._to_model(row) for row in rows]

    async def upsert_expected(
        self,
        *,
        library_file_id: str,
        artifact_type: LibraryFileArtifactType,
        expected_path: str,
        status: LibraryFileArtifactStatus,
        last_error: str | None = None,
    ) -> LibraryFileArtifact:
        now = time.time()
        with SessionLocal() as session:
            row = session.execute(
                select(LibraryFileArtifactORM).where(
                    LibraryFileArtifactORM.library_file_id == library_file_id,
                    LibraryFileArtifactORM.artifact_type == artifact_type.value,
                    LibraryFileArtifactORM.expected_path == expected_path,
                )
            ).scalars().first()
            if row is None:
                row = LibraryFileArtifactORM(
                    id=str(uuid.uuid4()),
                    library_file_id=library_file_id,
                    artifact_type=artifact_type.value,
                    expected_path=expected_path,
                    status=status.value,
                    last_success_at=now if status == LibraryFileArtifactStatus.succeeded else None,
                    last_error=last_error,
                    next_retry_at=None,
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
            else:
                row.status = status.value
                row.last_error = last_error
                row.updated_at = now
                row.next_retry_at = None
                if status == LibraryFileArtifactStatus.succeeded:
                    row.last_success_at = now
            session.commit()
            return self._to_model(row)

    async def mark_missing_by_paths(self, paths: list[str]) -> int:
        if not paths:
            return 0
        now = time.time()
        with SessionLocal() as session:
            result = session.execute(
                update(LibraryFileArtifactORM)
                .where(
                    LibraryFileArtifactORM.expected_path.in_(paths),
                    LibraryFileArtifactORM.status != LibraryFileArtifactStatus.pending.value,
                )
                .values(
                    status=LibraryFileArtifactStatus.pending.value,
                    last_error=None,
                    next_retry_at=None,
                    updated_at=now,
                )
            )
            session.commit()
            return int(result.rowcount or 0)

    async def remove_by_library_file_ids(self, library_file_ids: list[str]) -> int:
        if not library_file_ids:
            return 0
        with SessionLocal() as session:
            result = session.execute(
                delete(LibraryFileArtifactORM).where(LibraryFileArtifactORM.library_file_id.in_(library_file_ids))
            )
            session.commit()
            return int(result.rowcount or 0)
