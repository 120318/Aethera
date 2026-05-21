from pathlib import Path

import pytest

from app.schemas.config import DirectoryConfig
from app.schemas.domain.library import LibraryFile
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.resource_attributes import PackageLayoutValue, ResourceAttributes
from app.schemas.media_id import MediaID
from app.services.domain.library.directory_change import (
    LibraryFileDirectoryChangeRequest,
    LibraryFileDirectoryChangeService,
)
from app.services.application.views.library.resource_list import (
    _LibraryActionAvailabilityContext,
    LibraryResourceListService,
)


def _library_file(file_id: str, *, task_id: str = "task-1", directory_id: str = "dir-old", path: str, file_name: str) -> LibraryFile:
    return LibraryFile(
        id=file_id,
        task_id=task_id,
        directory_id=directory_id,
        media_id=MediaID.parse("tmdb:movie:1"),
        path=path,
        file_name=file_name,
        file_size=1,
        file_index=0,
        created_at=1,
        resource_attributes=ResourceAttributes(package_layout=PackageLayoutValue.BDMV),
    )


@pytest.mark.asyncio
async def test_library_file_directory_change_blocks_when_download_task_exists(monkeypatch, tmp_path):
    source = DirectoryConfig(id="dir-old", name="Old", media_type=MediaType.movie, path=str(tmp_path / "old"))
    target = DirectoryConfig(id="dir-new", name="New", media_type=MediaType.movie, path=str(tmp_path / "new"))
    source_path = Path(source.path) / "Movie.mkv"
    source_path.parent.mkdir(parents=True)
    source_path.write_text("movie", encoding="utf-8")
    library_file = _library_file("file-1", path=source.path, file_name="Movie.mkv")

    monkeypatch.setattr(
        "app.services.domain.library.directory_change.settings_service.get_directory_by_id",
        lambda directory_id: source if directory_id == "dir-old" else target,
    )
    async def find_file_by_id(file_id):
        return library_file

    monkeypatch.setattr(
        "app.services.domain.library.directory_change.library_service.find_file_by_id",
        find_file_by_id,
    )

    async def get_tasks_by_ids(task_ids):
        return {"task-1": object()}

    monkeypatch.setattr(
        "app.services.domain.library.directory_change.download_service.get_tasks_by_ids",
        get_tasks_by_ids,
    )

    preview = await LibraryFileDirectoryChangeService().preview(
        "file-1",
        LibraryFileDirectoryChangeRequest(target_directory_id="dir-new"),
    )

    assert preview.ok is False
    assert "task_exists" in preview.blockers


@pytest.mark.asyncio
async def test_library_file_directory_change_moves_whole_package(monkeypatch, tmp_path):
    source = DirectoryConfig(id="dir-old", name="Old", media_type=MediaType.movie, path=str(tmp_path / "old"))
    target = DirectoryConfig(id="dir-new", name="New", media_type=MediaType.movie, path=str(tmp_path / "new"))
    source_root = Path(source.path) / "Movie" / "BDMV"
    source_root.mkdir(parents=True)
    index_file = source_root / "index.bdmv"
    stream_file = source_root / "STREAM" / "00001.m2ts"
    stream_file.parent.mkdir()
    index_file.write_text("index", encoding="utf-8")
    stream_file.write_text("stream", encoding="utf-8")
    files = [
        _library_file("file-1", path=str(source_root), file_name="index.bdmv"),
        _library_file("file-2", path=str(source_root / "STREAM"), file_name="00001.m2ts"),
    ]
    updates = []

    monkeypatch.setattr(
        "app.services.domain.library.directory_change.settings_service.get_directory_by_id",
        lambda directory_id: source if directory_id == "dir-old" else target,
    )
    async def find_file_by_id(file_id):
        return files[0]

    async def get_files_by_media(media_id):
        return files

    monkeypatch.setattr(
        "app.services.domain.library.directory_change.library_service.find_file_by_id",
        find_file_by_id,
    )
    monkeypatch.setattr(
        "app.services.domain.library.directory_change.library_service.get_files_by_media",
        get_files_by_media,
    )

    async def get_tasks_by_ids(task_ids):
        return {}

    async def update_file_location(file_id, *, directory_id, path, file_name):
        updates.append((file_id, directory_id, path, file_name))
        return True

    monkeypatch.setattr(
        "app.services.domain.library.directory_change.download_service.get_tasks_by_ids",
        get_tasks_by_ids,
    )
    monkeypatch.setattr(
        "app.services.domain.library.directory_change.library_service.update_file_location",
        update_file_location,
    )

    preview = await LibraryFileDirectoryChangeService().execute(
        "file-1",
        LibraryFileDirectoryChangeRequest(target_directory_id="dir-new", package_root=str(Path(source.path) / "Movie").strip("/")),
    )

    assert preview.ok is True
    assert preview.file_count == 2
    assert not index_file.exists()
    assert not stream_file.exists()
    assert Path(target.path, "Movie", "BDMV", "index.bdmv").exists()
    assert Path(target.path, "Movie", "BDMV", "STREAM", "00001.m2ts").exists()
    assert [item[0] for item in updates] == ["file-1", "file-2"]
    assert {item[1] for item in updates} == {"dir-new"}


def test_library_resource_change_directory_action_requires_deleted_task(tmp_path):
    source = DirectoryConfig(id="dir-old", name="Old", media_type=MediaType.movie, path=str(tmp_path / "old"))
    library_file = _library_file("file-1", path=source.path, file_name="Movie.mkv")
    service = LibraryResourceListService()
    context = _LibraryActionAvailabilityContext(
        media_server_open_enabled_directory_ids=set(),
        media_server_sync_enabled_directory_ids=set(),
        danmu_enabled_directory_ids=set(),
        danmu_media_available=False,
        existing_task_ids={"task-1"},
    )

    assert service._resolve_action_context([library_file], context) == (False, False, False, False)

    context = _LibraryActionAvailabilityContext(
        media_server_open_enabled_directory_ids=set(),
        media_server_sync_enabled_directory_ids=set(),
        danmu_enabled_directory_ids=set(),
        danmu_media_available=False,
        existing_task_ids=set(),
    )

    assert service._resolve_action_context([library_file], context) == (False, False, False, True)
