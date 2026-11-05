from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from app.schemas.config import DirectoryConfig
from app.schemas.domain.library import LibraryFile, LibraryFileArtifact
from app.schemas.exception.exceptions import ResourceNotFoundException
from app.services.config.settings_service import settings_service
from app.services.domain.library.artifact_paths import video_sidecar_suffix
from app.services.domain.library.operation_lock import library_file_operation_coordinator
from app.services.domain.library.service import library_service
from app.utils.fs_utils import ensure_directory
from app.utils.library_paths import build_library_file_path, split_library_storage_path


@dataclass(frozen=True)
class LibraryArtifactMove:
    source_path: Path
    target_path: Path
    artifact: LibraryFileArtifact


class LibraryFileRelocationService:
    def build_file_moves(
        self,
        files: list[LibraryFile],
        target_directory: DirectoryConfig,
        *,
        source_directory_fallback: DirectoryConfig | None = None,
    ) -> list[tuple[Path, Path, LibraryFile]]:
        target_base = build_library_file_path(target_directory.path).resolve(strict=False)
        moves: list[tuple[Path, Path, LibraryFile]] = []
        for file in files:
            source_directory = self._load_source_directory(file, source_directory_fallback)
            source_base = build_library_file_path(source_directory.path).resolve(strict=False)
            source_path = build_library_file_path(file.path, file.file_name).resolve(strict=False)
            try:
                suffix = source_path.relative_to(source_base)
            except ValueError:
                suffix = Path(file.file_name or source_path.name)
            moves.append((source_path, (target_base / suffix).resolve(strict=False), file))
        return moves

    async def build_artifact_moves(
        self,
        files: list[LibraryFile],
        target_directory: DirectoryConfig,
        *,
        source_directory_fallback: DirectoryConfig | None = None,
    ) -> list[LibraryArtifactMove]:
        file_moves = self.build_file_moves(
            files,
            target_directory,
            source_directory_fallback=source_directory_fallback,
        )
        artifacts = await library_service.get_artifacts_by_file_ids([file.id for file in files])
        artifacts_by_file_id: dict[str, list[LibraryFileArtifact]] = {}
        for artifact in artifacts:
            artifacts_by_file_id.setdefault(artifact.library_file_id, []).append(artifact)
        moves: list[LibraryArtifactMove] = []
        for source_video, target_video, library_file in file_moves:
            for artifact in artifacts_by_file_id.get(library_file.id, []):
                source_artifact = Path(artifact.expected_path).resolve(strict=False)
                suffix = video_sidecar_suffix(source_video, source_artifact)
                if suffix is None:
                    continue
                moves.append(
                    LibraryArtifactMove(
                        source_path=source_artifact,
                        target_path=target_video.with_name(f"{target_video.stem}{suffix}"),
                        artifact=artifact,
                    )
                )
        return moves

    async def move_files(
        self,
        files: list[LibraryFile],
        target_directory: DirectoryConfig,
        *,
        source_directory_fallback: DirectoryConfig | None = None,
    ) -> bool:
        async with library_file_operation_coordinator.lock([file.id for file in files]):
            return await self._move_files_locked(
                files,
                target_directory,
                source_directory_fallback=source_directory_fallback,
            )

    async def _move_files_locked(
        self,
        files: list[LibraryFile],
        target_directory: DirectoryConfig,
        *,
        source_directory_fallback: DirectoryConfig | None,
    ) -> bool:
        moves = self.build_file_moves(
            files,
            target_directory,
            source_directory_fallback=source_directory_fallback,
        )
        artifact_moves = await self.build_artifact_moves(
            files,
            target_directory,
            source_directory_fallback=source_directory_fallback,
        )
        if any(not source_path.exists() for source_path, _target_path, _file in moves):
            return False
        if any(source_path != target_path and target_path.exists() for source_path, target_path, _file in moves):
            return False
        if any(
            move.source_path != move.target_path and move.target_path.exists()
            for move in artifact_moves
        ):
            return False
        moved: list[tuple[Path, Path]] = []
        updated: list[LibraryFile] = []
        updated_artifacts: list[LibraryFileArtifact] = []
        try:
            for source_path, target_path, _file in moves:
                if source_path == target_path:
                    continue
                ensure_directory(target_path.parent)
                shutil.move(str(source_path), str(target_path))
                moved.append((source_path, target_path))
            for move in artifact_moves:
                if move.source_path == move.target_path or not move.source_path.exists():
                    continue
                ensure_directory(move.target_path.parent)
                shutil.move(str(move.source_path), str(move.target_path))
                moved.append((move.source_path, move.target_path))
            for _source_path, target_path, file in moves:
                next_path, next_name = split_library_storage_path(str(target_path))
                if not await library_service.update_file_location(
                    file.id,
                    directory_id=target_directory.id,
                    path=next_path,
                    file_name=next_name,
                ):
                    await self._rollback(moved, updated, updated_artifacts)
                    return False
                updated.append(file)
            for move in artifact_moves:
                if not await library_service.update_artifact_expected_path(
                    move.artifact.id,
                    str(move.target_path),
                ):
                    await self._rollback(moved, updated, updated_artifacts)
                    return False
                updated_artifacts.append(move.artifact)
        except OSError:
            await self._rollback(moved, updated, updated_artifacts)
            return False
        return True

    async def _rollback(
        self,
        moved: list[tuple[Path, Path]],
        updated: list[LibraryFile],
        updated_artifacts: list[LibraryFileArtifact],
    ) -> None:
        for artifact in reversed(updated_artifacts):
            await library_service.update_artifact_expected_path(artifact.id, artifact.expected_path)
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

    @staticmethod
    def _load_source_directory(
        library_file: LibraryFile,
        fallback: DirectoryConfig | None,
    ) -> DirectoryConfig:
        directory = settings_service.get_directory_by_id(library_file.directory_id)
        if directory and directory.enabled:
            return directory
        if fallback is not None:
            return fallback
        raise ResourceNotFoundException("backendErrors.directoryNotFound")


library_file_relocation_service = LibraryFileRelocationService()
