from __future__ import annotations

import shutil
from pathlib import Path

from pydantic import BaseModel, Field

from app.schemas.config import DirectoryConfig
from app.schemas.domain.library import LibraryFile
from app.schemas.exception.exceptions import ResourceNotFoundException
from app.services.config.settings_service import settings_service
from app.services.domain.download import download_service
from app.services.domain.library.service import library_service
from app.utils.fs_utils import ensure_directory
from app.utils.library_paths import build_library_file_path, split_library_storage_path


class LibraryFileDirectoryChangeRequest(BaseModel):
    target_directory_id: str
    package_root: str = ""


class LibraryFileDirectoryChangePreview(BaseModel):
    ok: bool = False
    blockers: list[str] = Field(default_factory=list)
    file_id: str
    package_root: str = ""
    file_count: int = 0
    source_directory_id: str = ""
    target_directory_id: str = ""
    target_directory_name: str = ""


class LibraryFileDirectoryChangeService:
    async def preview(
        self,
        file_id: str,
        request: LibraryFileDirectoryChangeRequest,
    ) -> LibraryFileDirectoryChangePreview:
        files = await self._resolve_files(file_id, request.package_root)
        source_file = files[0]
        target_directory = self._load_directory(request.target_directory_id)
        preview = LibraryFileDirectoryChangePreview(
            file_id=source_file.id,
            package_root=request.package_root,
            file_count=len(files),
            source_directory_id=source_file.directory_id,
            target_directory_id=target_directory.id,
            target_directory_name=target_directory.name,
        )
        await self._validate(files, target_directory, preview)
        return preview

    async def execute(
        self,
        file_id: str,
        request: LibraryFileDirectoryChangeRequest,
    ) -> LibraryFileDirectoryChangePreview:
        preview = await self.preview(file_id, request)
        if not preview.ok:
            return preview
        files = await self._resolve_files(file_id, request.package_root)
        target_directory = self._load_directory(request.target_directory_id)
        if not await self._move_files(files, target_directory):
            preview.ok = False
            preview.blockers.append("library_file_move_failed")
        return preview

    async def _resolve_files(self, file_id: str, package_root: str) -> list[LibraryFile]:
        library_file = await library_service.find_file_by_id(file_id)
        if not library_file:
            raise ResourceNotFoundException("backendErrors.resourceFileNotFound")
        if not package_root:
            return [library_file]
        media_files = await library_service.get_files_by_media(library_file.media_id)
        files = [
            item
            for item in media_files
            if item.task_id == library_file.task_id and library_service.matches_package_root(item, package_root)
        ]
        return files or [library_file]

    async def _validate(
        self,
        files: list[LibraryFile],
        target_directory: DirectoryConfig,
        preview: LibraryFileDirectoryChangePreview,
    ) -> None:
        blockers: list[str] = []
        if not target_directory.enabled:
            blockers.append("target_directory_not_enabled")
        if any(file.directory_id == target_directory.id for file in files):
            blockers.append("same_directory")
        if any(file.media_id.media_type != target_directory.media_type for file in files):
            blockers.append("media_type_mismatch")
        if await self._validate_existing_tasks(files):
            blockers.append("task_exists")
        if self._has_missing_source(files):
            blockers.append("source_file_missing")
        if self._has_target_conflicts(files, target_directory):
            blockers.append("target_file_exists")
        preview.blockers = blockers
        preview.ok = not blockers

    async def _validate_existing_tasks(self, files: list[LibraryFile]) -> bool:
        task_ids = sorted({file.task_id for file in files if file.task_id})
        if not task_ids:
            return False
        existing = await download_service.get_tasks_by_ids(task_ids)
        return bool(existing)

    def _has_missing_source(self, files: list[LibraryFile]) -> bool:
        return any(not build_library_file_path(file.path, file.file_name).exists() for file in files)

    def _has_target_conflicts(self, files: list[LibraryFile], target_directory: DirectoryConfig) -> bool:
        target_paths = self._build_moves(files, target_directory)
        return any(source != target and target.exists() for source, target, _file in target_paths)

    def _build_moves(self, files: list[LibraryFile], target_directory: DirectoryConfig) -> list[tuple[Path, Path, LibraryFile]]:
        target_base = build_library_file_path(target_directory.path).resolve(strict=False)
        moves: list[tuple[Path, Path, LibraryFile]] = []
        for file in files:
            source_directory = self._load_directory(file.directory_id)
            source_base = build_library_file_path(source_directory.path).resolve(strict=False)
            source_path = build_library_file_path(file.path, file.file_name).resolve(strict=False)
            try:
                suffix = source_path.relative_to(source_base)
            except ValueError:
                suffix = Path(file.file_name or source_path.name)
            moves.append((source_path, (target_base / suffix).resolve(strict=False), file))
        return moves

    async def _move_files(self, files: list[LibraryFile], target_directory: DirectoryConfig) -> bool:
        moves = self._build_moves(files, target_directory)
        moved: list[tuple[Path, Path]] = []
        updated: list[LibraryFile] = []
        try:
            for source_path, target_path, _file in moves:
                if source_path == target_path:
                    continue
                ensure_directory(target_path.parent)
                shutil.move(str(source_path), str(target_path))
                moved.append((source_path, target_path))
            for _source_path, target_path, file in moves:
                next_path, next_name = split_library_storage_path(str(target_path))
                if not await library_service.update_file_location(
                    file.id,
                    directory_id=target_directory.id,
                    path=next_path,
                    file_name=next_name,
                ):
                    await self._rollback(moved, updated)
                    return False
                updated.append(file)
        except OSError:
            await self._rollback(moved, updated)
            return False
        return True

    async def _rollback(self, moved: list[tuple[Path, Path]], updated: list[LibraryFile]) -> None:
        for file in reversed(updated):
            await library_service.update_file_location(
                file.id,
                directory_id=file.directory_id,
                path=file.path,
                file_name=file.file_name,
            )
        for source_path, target_path in reversed(moved):
            if target_path.exists() and not source_path.exists():
                ensure_directory(source_path.parent)
                shutil.move(str(target_path), str(source_path))

    def _load_directory(self, directory_id: str) -> DirectoryConfig:
        directory = settings_service.get_directory_by_id(directory_id)
        if not directory:
            raise ResourceNotFoundException("backendErrors.directoryNotFound")
        return directory


library_file_directory_change_service = LibraryFileDirectoryChangeService()
