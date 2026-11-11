from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator

from app.schemas.config import DanmuAddonConfig
from app.schemas.domain.library import LibraryFile, LibraryFileArtifactStatus, LibraryFileArtifactType
from app.schemas.exception import InvalidRequestException, ResourceNotFoundException
from app.services.application.workflows.danmu.duration_guard import danmu_duration_guard
from app.services.application.workflows.danmu.sidecar_outputs import expected_sidecar_paths, remove_outputs, write_outputs
from app.services.domain.library.file_version import LibraryFileVersion, library_file_version
from app.services.domain.library.operation_lock import library_file_operation_coordinator
from app.services.domain.library.service import library_service
from app.services.integration.danmu.models import DanmuFetchResult
from app.utils.library_paths import build_library_file_path


@dataclass(frozen=True)
class DanmuArtifactCommitResult:
    video_path: Path
    xml_path: Path | None = None
    ass_path: Path | None = None
    duration_mismatch: bool = False


class DanmuArtifactCommitter:
    async def mark_status(
        self,
        library_file: LibraryFile,
        expected_version: LibraryFileVersion,
        config: DanmuAddonConfig,
        status: LibraryFileArtifactStatus,
        *,
        last_error: str | None = None,
        ignore_stale: bool = False,
    ) -> None:
        try:
            async with self._current_target(
                library_file,
                expected_version,
            ) as (current_file, current_path):
                await self._mark_expected(
                    current_file,
                    current_path,
                    config,
                    status,
                    last_error=last_error,
                )
        except (InvalidRequestException, ResourceNotFoundException):
            if not ignore_stale:
                raise

    async def commit(
        self,
        library_file: LibraryFile,
        expected_version: LibraryFileVersion,
        result: DanmuFetchResult,
        config: DanmuAddonConfig,
    ) -> DanmuArtifactCommitResult:
        async with self._current_target(
            library_file,
            expected_version,
        ) as (current_file, current_path):
            if await danmu_duration_guard.has_duration_mismatch(current_path, result, config):
                remove_outputs(current_path, config)
                await self._mark_expected(
                    current_file,
                    current_path,
                    config,
                    LibraryFileArtifactStatus.skipped,
                    last_error="duration_mismatch",
                )
                return DanmuArtifactCommitResult(video_path=current_path, duration_mismatch=True)
            xml_path, ass_path = write_outputs(current_path, result, config)
            await self._mark_written(current_file, xml_path, ass_path)
            return DanmuArtifactCommitResult(
                video_path=current_path,
                xml_path=xml_path,
                ass_path=ass_path,
            )

    @asynccontextmanager
    async def _current_target(
        self,
        library_file: LibraryFile,
        expected_version: LibraryFileVersion,
    ) -> AsyncIterator[tuple[LibraryFile, Path]]:
        async with library_file_operation_coordinator.lock([library_file.id]):
            current_file = await library_service.find_file_by_id(library_file.id)
            if current_file is None or not library_service.is_primary_file(current_file):
                raise ResourceNotFoundException("backendErrors.resourceFileNotFound")
            if library_file_version(current_file) != expected_version:
                raise InvalidRequestException("backendErrors.danmuVideoChanged")
            current_path = build_library_file_path(current_file.path, current_file.file_name)
            if not current_path.is_file():
                raise ResourceNotFoundException("backendErrors.resourceFileNotFound")
            yield current_file, current_path

    @staticmethod
    async def _mark_expected(
        library_file: LibraryFile,
        video_path: Path,
        config: DanmuAddonConfig,
        status: LibraryFileArtifactStatus,
        *,
        last_error: str | None = None,
    ) -> None:
        for path in expected_sidecar_paths(video_path, config):
            artifact_type = LibraryFileArtifactType.danmu_xml if path.suffix == ".xml" else LibraryFileArtifactType.danmu_ass
            await library_service.mark_artifact(
                library_file_id=library_file.id,
                artifact_type=artifact_type,
                expected_path=str(path),
                status=status,
                last_error=last_error,
            )

    @staticmethod
    async def _mark_written(
        library_file: LibraryFile,
        xml_path: Path | None,
        ass_path: Path | None,
    ) -> None:
        if xml_path:
            await library_service.mark_artifact(
                library_file_id=library_file.id,
                artifact_type=LibraryFileArtifactType.danmu_xml,
                expected_path=str(xml_path),
                status=LibraryFileArtifactStatus.succeeded,
            )
        if ass_path:
            await library_service.mark_artifact(
                library_file_id=library_file.id,
                artifact_type=LibraryFileArtifactType.danmu_ass,
                expected_path=str(ass_path),
                status=LibraryFileArtifactStatus.succeeded,
            )


danmu_artifact_committer = DanmuArtifactCommitter()
