from __future__ import annotations

import shutil
from pathlib import Path

from app.schemas.config import DirectoryConfig
from app.schemas.domain.download import TaskData
from app.schemas.domain.library import LibraryFile
from app.schemas.domain.task_storage_migration import TaskStorageMigration
from app.services.domain.library.relocation import library_file_relocation_service
from app.utils.fs_utils import ensure_directory


def move_content_if_needed(*, move_content: bool, source_path: str | None, target_path: str | None) -> str | None:
    if not move_content:
        return None
    source = Path(source_path or "")
    target = Path(target_path or "")
    if not source.exists():
        return "source_content_missing"
    if target.exists():
        return None
    try:
        ensure_directory(target.parent)
        shutil.move(str(source), str(target))
    except OSError:
        return "content_move_failed"
    return None


def rollback_content_move_if_needed(migration: TaskStorageMigration) -> bool:
    if not migration.move_content or not migration.content_moved:
        return True
    source = Path(migration.source_content_path or "")
    target = Path(migration.target_content_path or "")
    if not target.exists() or source.exists():
        return True
    try:
        ensure_directory(source.parent)
        shutil.move(str(target), str(source))
    except OSError:
        return False
    return True


async def move_task_library_files(
    task: TaskData,
    library_files: list[LibraryFile],
    source_directory: DirectoryConfig,
    target_directory: DirectoryConfig,
) -> bool:
    del task
    return await library_file_relocation_service.move_files(
        library_files,
        target_directory,
        source_directory_fallback=source_directory,
    )
