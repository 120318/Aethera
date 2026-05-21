import pytest

from app.schemas.domain.library import (
    LibraryFile,
    LibraryFileArtifact,
    LibraryFileArtifactStatus,
    LibraryFileArtifactType,
    LibraryPackageFileItem,
    LibraryPackageSummary,
)
from app.schemas.domain.resource_attributes import ResourceAttributes
from app.schemas.media_id import MediaID
from app.services.application.views.library import resource_detail


def _library_file(file_id: str) -> LibraryFile:
    return LibraryFile(
        id=file_id,
        task_id="task-1",
        directory_id="dir-1",
        media_id=MediaID.parse("tmdb:tv:1"),
        path="/library/Show",
        file_name=f"{file_id}.mkv",
        file_size=1,
        file_index=0,
        created_at=1.0,
        resource_attributes=ResourceAttributes(seasons=[1], episodes=[1]),
    )


def _library_file_at(file_id: str, path: str, file_name: str) -> LibraryFile:
    file = _library_file(file_id)
    return file.model_copy(update={"path": path, "file_name": file_name})


def _artifact(
    file_id: str,
    artifact_type: LibraryFileArtifactType,
    status: LibraryFileArtifactStatus = LibraryFileArtifactStatus.succeeded,
) -> LibraryFileArtifact:
    return LibraryFileArtifact(
        id=f"{file_id}-{artifact_type.value}",
        library_file_id=file_id,
        artifact_type=artifact_type,
        expected_path=f"/library/Show/{file_id}.{artifact_type.value}",
        status=status,
        created_at=1.0,
        updated_at=1.0,
    )


@pytest.mark.asyncio
async def test_file_detail_includes_succeeded_artifact_summary(monkeypatch):
    file = _library_file("file-1")

    async def find_file_by_id(_file_id):
        return file

    async def find_package_for_file(_file):
        return None

    async def get_artifacts_by_file_ids(file_ids):
        assert file_ids == ["file-1"]
        return [
            _artifact("file-1", LibraryFileArtifactType.nfo),
            _artifact("file-1", LibraryFileArtifactType.danmu_xml),
            _artifact("file-1", LibraryFileArtifactType.poster, LibraryFileArtifactStatus.pending),
        ]

    monkeypatch.setattr(resource_detail.library_service, "find_file_by_id", find_file_by_id)
    monkeypatch.setattr(resource_detail.library_service, "find_package_for_file", find_package_for_file)
    monkeypatch.setattr(resource_detail.library_service, "get_artifacts_by_file_ids", get_artifacts_by_file_ids)
    monkeypatch.setattr(resource_detail.settings_service, "list_tags", lambda: [])
    monkeypatch.setattr(resource_detail.settings_service, "get_directory_by_id", lambda _directory_id: None)

    detail = await resource_detail.library_resource_detail_service.get_file_detail("file-1")

    assert detail.data.artifact_summary.scraped is True
    assert detail.data.artifact_summary.danmu is True


@pytest.mark.asyncio
async def test_package_detail_aggregates_package_artifact_summary(monkeypatch):
    file = _library_file("file-1")
    package = LibraryPackageSummary(
        id="package-1",
        task_id="task-1",
        directory_id="dir-1",
        media_id=MediaID.parse("tmdb:tv:1"),
        file_name="Show",
        resource_title="Show",
        directory="Show",
        package_root="Show",
        file_count=2,
        total_size=2,
        created_at=1.0,
        resource_attributes=ResourceAttributes(seasons=[1]),
        files=[
            LibraryPackageFileItem(
                id="file-1",
                path="/library/Show",
                file_name="file-1.mkv",
                relative_path="file-1.mkv",
                file_size=1,
                file_index=0,
                is_anchor=True,
            ),
            LibraryPackageFileItem(
                id="file-2",
                path="/library/Show",
                file_name="file-2.mkv",
                relative_path="file-2.mkv",
                file_size=1,
                file_index=1,
            ),
        ],
    )

    async def find_file_by_id(_file_id):
        return file

    async def find_package_for_file(_file):
        return package

    async def get_artifacts_by_file_ids(file_ids):
        assert sorted(file_ids) == ["file-1", "file-2"]
        return [
            _artifact("file-1", LibraryFileArtifactType.nfo),
            _artifact("file-2", LibraryFileArtifactType.danmu_ass),
        ]

    monkeypatch.setattr(resource_detail.library_service, "find_file_by_id", find_file_by_id)
    monkeypatch.setattr(resource_detail.library_service, "find_package_for_file", find_package_for_file)
    monkeypatch.setattr(resource_detail.library_service, "get_artifacts_by_file_ids", get_artifacts_by_file_ids)
    monkeypatch.setattr(resource_detail.settings_service, "list_tags", lambda: [])
    monkeypatch.setattr(resource_detail.settings_service, "get_directory_by_id", lambda _directory_id: None)

    detail = await resource_detail.library_resource_detail_service.get_file_detail("file-1")

    assert detail.package is not None
    assert detail.data.artifact_summary.scraped is True
    assert detail.data.artifact_summary.danmu is False
    assert detail.package.artifact_summary.scraped is True
    assert detail.package.artifact_summary.danmu is True


@pytest.mark.asyncio
async def test_file_detail_detects_existing_sidecars_without_artifact_rows(tmp_path, monkeypatch):
    video = tmp_path / "Show.S01E01.mkv"
    video.write_text("video")
    video.with_suffix(".nfo").write_text("nfo")
    video.with_name("Show.S01E01.danmu.xml").write_text("danmu")
    file = _library_file_at("file-1", str(tmp_path), video.name)

    async def find_file_by_id(_file_id):
        return file

    async def find_package_for_file(_file):
        return None

    async def get_artifacts_by_file_ids(_file_ids):
        return []

    monkeypatch.setattr(resource_detail.library_service, "find_file_by_id", find_file_by_id)
    monkeypatch.setattr(resource_detail.library_service, "find_package_for_file", find_package_for_file)
    monkeypatch.setattr(resource_detail.library_service, "get_artifacts_by_file_ids", get_artifacts_by_file_ids)
    monkeypatch.setattr(resource_detail.settings_service, "list_tags", lambda: [])
    monkeypatch.setattr(resource_detail.settings_service, "get_directory_by_id", lambda _directory_id: None)

    detail = await resource_detail.library_resource_detail_service.get_file_detail("file-1")

    assert detail.data.artifact_summary.scraped is True
    assert detail.data.artifact_summary.danmu is True
