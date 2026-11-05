from __future__ import annotations

from dataclasses import dataclass

from app.schemas.domain.library import LibraryFile


@dataclass(frozen=True)
class LibraryFileVersion:
    id: str
    task_id: str
    file_size: int | None
    file_index: int | None
    created_at: float


def library_file_version(library_file: LibraryFile) -> LibraryFileVersion:
    return LibraryFileVersion(
        id=library_file.id,
        task_id=library_file.task_id,
        file_size=library_file.file_size,
        file_index=library_file.file_index,
        created_at=library_file.created_at,
    )
