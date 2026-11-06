from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.config import DirectoryConfig
from app.schemas.domain.library import LibraryFile
from app.schemas.exception.exceptions import ResourceNotFoundException
from app.services.config.settings_service import settings_service
from app.services.domain.download import download_service
from app.services.domain.library.relocation import library_file_relocation_service
from app.services.domain.library.service import library_service
from app.utils.library_paths import build_library_file_path


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
        if not await library_file_relocation_service.move_files(files, target_directory):
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
        artifact_moves = await library_file_relocation_service.build_artifact_moves(
            files,
            target_directory,
        )
        if any(move.source_path != move.target_path and move.target_path.exists() for move in artifact_moves):
            blockers.append("target_artifact_exists")
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
        target_paths = library_file_relocation_service.build_file_moves(files, target_directory)
        return any(source != target and target.exists() for source, target, _file in target_paths)

    def _load_directory(self, directory_id: str) -> DirectoryConfig:
        directory = settings_service.get_directory_by_id(directory_id)
        if not directory:
            raise ResourceNotFoundException("backendErrors.directoryNotFound")
        return directory


library_file_directory_change_service = LibraryFileDirectoryChangeService()
