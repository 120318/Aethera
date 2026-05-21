from __future__ import annotations

import shutil
from pathlib import Path

from app.schemas.config import DirectoryConfig
from app.schemas.domain.download import TaskData
from app.schemas.domain.library import LibraryFile
from app.schemas.domain.task_storage_migration import TaskStorageMigration
from app.services.config.settings_service import settings_service
from app.services.domain.library.service import library_service
from app.utils.fs_utils import ensure_directory
from app.utils.library_paths import build_library_file_path, split_library_storage_path


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
    target_base = build_library_file_path(target_directory.path).resolve(strict=False)
    moves: list[tuple[Path, Path]] = []
    updates: list[tuple[LibraryFile, str, str | None]] = []
    for library_file in library_files:
        if library_file.directory_id == target_directory.id:
            continue
        library_source_directory = _load_library_file_directory(library_file, fallback=source_directory)
        source_base = build_library_file_path(library_source_directory.path).resolve(strict=False)
        source_path = build_library_file_path(library_file.path, library_file.file_name).resolve(strict=False)
        if not source_path.exists():
            return False
        try:
            suffix = source_path.relative_to(source_base)
        except ValueError:
            suffix = Path(library_file.file_name or source_path.name)
        target_path = (target_base / suffix).resolve(strict=False)
        if source_path != target_path and target_path.exists():
            return False
        next_path, next_name = split_library_storage_path(str(target_path))
        moves.append((source_path, target_path))
        updates.append((library_file, next_path, next_name))

    moved: list[tuple[Path, Path]] = []
    updated: list[LibraryFile] = []
    try:
        for source_path, target_path in moves:
            if source_path == target_path:
                continue
            ensure_directory(target_path.parent)
            shutil.move(str(source_path), str(target_path))
            moved.append((source_path, target_path))
        for library_file, next_path, next_name in updates:
            if not await library_service.update_file_location(
                library_file.id,
                directory_id=target_directory.id,
                path=next_path,
                file_name=next_name,
            ):
                await _rollback_library_file_moves(moved, updated)
                return False
            updated.append(library_file)
    except OSError:
        await _rollback_library_file_moves(moved, updated)
        return False
    return True


def _load_library_file_directory(library_file: LibraryFile, *, fallback: DirectoryConfig) -> DirectoryConfig:
    if library_file.directory_id:
        directory = settings_service.get_directory_by_id(library_file.directory_id)
        if directory and directory.enabled:
            return directory
    return fallback


async def _rollback_library_file_moves(moved: list[tuple[Path, Path]], updated: list[LibraryFile]) -> None:
    for library_file in reversed(updated):
        await library_service.update_file_location(
            library_file.id,
            directory_id=library_file.directory_id,
            path=library_file.path,
            file_name=library_file.file_name,
        )
    for source_path, target_path in reversed(moved):
        if target_path.exists() and not source_path.exists():
            ensure_directory(source_path.parent)
            shutil.move(str(target_path), str(source_path))
