from pathlib import Path

from pydantic import BaseModel, Field

from app.schemas.config import Tag
from app.schemas.domain.library import (
    LibraryFile,
    LibraryFileArtifact,
    LibraryFileArtifactStatus,
    LibraryFileArtifactType,
    LibraryPackageSummary,
)
from app.schemas.domain.resource_attributes import ResourceAttributes, ResourceDisplayAttributes
from app.schemas.exception.exceptions import ResourceNotFoundException
from app.services.config.settings_service import settings_service
from app.services.domain.library.service import library_service
from app.services.domain.resource.tags import resolve_display_tags
from app.utils.library_paths import build_library_file_path, normalize_path_separators


class LibraryArtifactSummary(BaseModel):
    scraped: bool = False
    danmu: bool = False


class LibraryFileDisplay(LibraryFile):
    resource_attributes: ResourceDisplayAttributes
    directory_name: str
    artifact_summary: LibraryArtifactSummary = Field(default_factory=LibraryArtifactSummary)


class LibraryPackageSummaryDisplay(LibraryPackageSummary):
    resource_attributes: ResourceDisplayAttributes
    directory_name: str
    artifact_summary: LibraryArtifactSummary = Field(default_factory=LibraryArtifactSummary)


class LibraryFileDetailResponse(BaseModel):
    kind: str = "file"
    data: LibraryFileDisplay
    package: LibraryPackageSummaryDisplay | None = None


class LibraryResourceDetailService:
    def _build_display_attributes(self, attrs: ResourceAttributes, *, tags: list[Tag]) -> ResourceDisplayAttributes:
        return ResourceDisplayAttributes.model_validate(
            attrs.model_dump(mode="python") | {"tags": resolve_display_tags(attrs, tags=tags)}
        )

    async def get_file_detail(self, file_id: str) -> LibraryFileDetailResponse:
        file = await library_service.find_file_by_id(file_id)
        if not file:
            raise ResourceNotFoundException("backendErrors.resourceFileNotFound")
        tags = settings_service.list_tags()
        package = await library_service.find_package_for_file(file)
        package_file_ids = [item.id for item in package.files] if package else []
        artifact_file_ids = list({file.id, *package_file_ids})
        artifacts = await library_service.get_artifacts_by_file_ids(artifact_file_ids)
        file_path = self._library_file_path(file.path, file.file_name)
        package_paths = self._package_paths(package) if package else []
        normalized = normalize_path_separators(file.path or "")
        display_file = LibraryFileDisplay.model_validate(
            file.model_dump(mode="python") | {
                "path": f"/{normalized.lstrip('/')}" if normalized else "/",
                "directory_name": self._directory_name(file.directory_id),
                "resource_attributes": self._build_display_attributes(file.resource_attributes, tags=tags),
                "artifact_summary": self._artifact_summary(
                    [artifact for artifact in artifacts if artifact.library_file_id == file.id],
                    file_paths=[file_path],
                ),
            }
        )
        if package:
            display_package = LibraryPackageSummaryDisplay.model_validate(
                package.model_dump(mode="python") | {
                    "directory_name": self._directory_name(package.directory_id),
                    "resource_attributes": self._build_display_attributes(package.resource_attributes, tags=tags),
                    "artifact_summary": self._artifact_summary(artifacts, file_paths=package_paths),
                }
            )
            return LibraryFileDetailResponse(kind="package", data=display_file, package=display_package)
        return LibraryFileDetailResponse(data=display_file)

    def _artifact_summary(self, artifacts: list[LibraryFileArtifact], *, file_paths: list[Path]) -> LibraryArtifactSummary:
        return LibraryArtifactSummary(
            scraped=self._has_artifact(artifacts, LibraryFileArtifactType.nfo) or self._has_nfo_sidecar(file_paths),
            danmu=(
                self._has_artifact(artifacts, LibraryFileArtifactType.danmu_xml)
                or self._has_artifact(artifacts, LibraryFileArtifactType.danmu_ass)
                or self._has_danmu_sidecar(file_paths)
            ),
        )

    def _has_artifact(self, artifacts: list[LibraryFileArtifact], artifact_type: LibraryFileArtifactType) -> bool:
        for artifact in artifacts:
            if artifact.artifact_type != artifact_type:
                continue
            if artifact.status == LibraryFileArtifactStatus.succeeded:
                return True
            if artifact.expected_path and Path(artifact.expected_path).exists():
                return True
        return False

    def _has_nfo_sidecar(self, file_paths: list[Path]) -> bool:
        return any(path.exists() for path in self._nfo_sidecar_candidates(file_paths))

    def _has_danmu_sidecar(self, file_paths: list[Path]) -> bool:
        return any(path.exists() for path in self._danmu_sidecar_candidates(file_paths))

    def _nfo_sidecar_candidates(self, file_paths: list[Path]) -> set[Path]:
        candidates: set[Path] = set()
        for path in file_paths:
            if path.suffix:
                candidates.add(path.with_suffix(".nfo"))
            else:
                candidates.update({path / "movie.nfo", path / "tvshow.nfo", path / "season.nfo"})
            candidates.update(
                {
                    path.parent / "movie.nfo",
                    path.parent / "tvshow.nfo",
                    path.parent / "season.nfo",
                    path.parent.parent / "movie.nfo",
                    path.parent.parent / "tvshow.nfo",
                }
            )
        return candidates

    def _danmu_sidecar_candidates(self, file_paths: list[Path]) -> set[Path]:
        candidates: set[Path] = set()
        for path in file_paths:
            if not path.suffix:
                continue
            candidates.add(path.with_name(f"{path.stem}.danmu.xml"))
            candidates.add(path.with_name(f"{path.stem}.danmu.ass"))
        return candidates

    def _package_paths(self, package: LibraryPackageSummary) -> list[Path]:
        paths = [self._library_file_path(item.path, item.file_name) for item in package.files]
        if package.package_root:
            paths.append(build_library_file_path(package.package_root.strip("/")))
        return paths

    def _library_file_path(self, path: str, file_name: str | None) -> Path:
        normalized = normalize_path_separators(path or "")
        if normalized.startswith("/") and not Path(normalized).exists():
            normalized = normalized.lstrip("/")
        return build_library_file_path(normalized, file_name)

    def _directory_name(self, directory_id: str) -> str:
        directory = settings_service.get_directory_by_id(directory_id)
        return directory.name if directory else ""


library_resource_detail_service = LibraryResourceDetailService()
