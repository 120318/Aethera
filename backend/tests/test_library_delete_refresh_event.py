import os
import uuid
from unittest.mock import AsyncMock

import pytest

os.environ.setdefault("DATA_PATH", f"/tmp/aethera-test-data-{uuid.uuid4()}")

from app.schemas.domain.library import LibraryFile
from app.schemas.domain.media import MediaSimpleInfo
from app.schemas.domain.media_types import MediaType
from app.schemas.media_id import MediaID
from app.services.application.workflows.media_resource_deletion.service import MediaResourceDeletionService
from app.services.domain.library.service import LibraryService


class FakeEpisodeRepo:
    async def remove_by_file_ids(self, file_ids):
        return len(file_ids)


class FakeFileRepo:
    def __init__(self, files=None):
        self.files = files or []

    async def find_by_media_id(self, media_id):
        return [file for file in self.files if file.media_id == media_id]

    async def remove_by_ids(self, file_ids):
        return len(file_ids)


class FakeMetaRepo:
    def __init__(self):
        self.archived_media_id = None

    async def archive_by_media_id(self, media_id):
        self.archived_media_id = media_id
        return True


class FakeCleanup:
    def delete_files(self, files):
        return None


@pytest.mark.asyncio
async def test_delete_media_library_files_emits_delete_event_with_file_paths_when_root_unresolved(monkeypatch):
    media_id = MediaID.parse("tmdb:movie:1")
    library_file = LibraryFile(
        id="file-1",
        task_id="task-1",
        directory_id="dir-1",
        media_id=media_id,
        path="/library/Movie (2024)",
        file_name="Movie.mkv",
        file_size=10,
        created_at=1.0,
    )
    service = LibraryService(
        file_repo=FakeFileRepo([library_file]),
        episode_repo=FakeEpisodeRepo(),
        cleanup=FakeCleanup(),
    )
    emitted = {}

    monkeypatch.setattr(
        "app.services.domain.media.media_service.simple_info",
        AsyncMock(
            return_value=MediaSimpleInfo(
                media_id=media_id,
                media_type=MediaType.movie,
                title="Movie",
                year=2024,
            )
        ),
    )
    monkeypatch.setattr(
        "app.services.domain.library.deletion.event_service.emit_media",
        lambda event, meta=None: emitted.update({"event": event, "meta": meta}),
    )

    deleted_count = await service.delete_media_library_files(media_id)

    assert deleted_count == 1
    assert emitted["meta"].media_id == media_id
    assert emitted["meta"].paths == ["/library/Movie (2024)/Movie.mkv"]
    assert emitted["meta"].delete_scope == "file"
    assert emitted["meta"].media_root_dir is None


@pytest.mark.asyncio
async def test_delete_media_resources_leaves_profile_lifecycle_to_scheduler(monkeypatch):
    media_id = MediaID.parse("tmdb:movie:1")
    service = MediaResourceDeletionService()
    archive_mock = AsyncMock()

    monkeypatch.setattr(
        "app.services.application.workflows.media_resource_deletion.service.library_service.delete_media_library_files",
        AsyncMock(return_value=1),
    )
    monkeypatch.setattr(
        "app.services.application.workflows.media_resource_deletion.service.library_service.archive_media_entry",
        archive_mock,
    )
    monkeypatch.setattr(
        "app.services.application.workflows.media_resource_deletion.service.download_service.get_tasks",
        AsyncMock(return_value=[]),
    )

    deleted_tasks_count, deleted_library_files_count = await service.delete_media_resources(
        media_id,
        mode="tasks_and_library",
        delete_files=True,
        force=False,
    )

    assert deleted_tasks_count == 0
    assert deleted_library_files_count == 1
    archive_mock.assert_awaited_once_with(media_id)
