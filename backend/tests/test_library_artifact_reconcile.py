from datetime import datetime

import pytest

from app.schemas.domain.download import TaskContext, TaskData, TaskStatus
from app.schemas.domain.library import LibraryFile, LibraryFileArtifactStatus, LibraryFileArtifactType
from app.schemas.domain.media import MediaExecutionSnapshot
from app.schemas.domain.resource_attributes import ResourceAttributes
from app.schemas.domain.torrent import TorrentFileItem, TorrentMetadata
from app.schemas.media_id import MediaID
from app.services.domain.library.service import LibraryService


class FakeFileRepo:
    def __init__(self, files=None):
        self.files = list(files or [])
        self.removed_ids = []

    async def find_by_task_id(self, task_id):
        return [item for item in self.files if item.task_id == task_id]

    async def remove_by_ids(self, ids):
        self.removed_ids.extend(ids)
        self.files = [item for item in self.files if item.id not in ids]
        return len(ids)


class FakeEpisodeRepo:
    def __init__(self):
        self.removed_ids = []

    async def remove_by_file_ids(self, file_ids):
        self.removed_ids.extend(file_ids)
        return len(file_ids)


class FakeArtifactRepo:
    def __init__(self):
        self.removed_ids = []
        self.marked = []

    async def remove_by_library_file_ids(self, library_file_ids):
        self.removed_ids.extend(library_file_ids)
        return len(library_file_ids)

    async def upsert_expected(self, **kwargs):
        self.marked.append(kwargs)
        return {
            "id": "artifact-1",
            "library_file_id": kwargs["library_file_id"],
            "artifact_type": kwargs["artifact_type"],
            "expected_path": kwargs["expected_path"],
            "status": kwargs["status"],
            "created_at": 1.0,
            "updated_at": 1.0,
        }


def _task(media_id: MediaID) -> TaskData:
    return TaskData(
        id="task-1",
        torrent_hash="hash",
        media_id=media_id,
        status=TaskStatus.COMPLETED,
        context=TaskContext(
            download_url="https://example.test/torrent",
            directory_id="dir-1",
            media=MediaExecutionSnapshot(media_id=media_id, title="Show", year=2026, season_number=1),
            selected_files=[0, 1],
        ),
        metadata=TorrentMetadata(
            hash="hash",
            name="Show",
            size=2,
            files=[
                TorrentFileItem(index=0, filename="Show.S01E01.mkv", size=1),
                TorrentFileItem(index=1, filename="Show.S01E02.mkv", size=1),
            ],
        ),
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


@pytest.mark.asyncio
async def test_reconcile_task_primary_files_removes_missing_library_records_and_emits_event(tmp_path, monkeypatch):
    media_id = MediaID.parse("tmdb:tv:1")
    present = tmp_path / "Show.S01E01.mkv"
    present.write_text("video")
    missing = tmp_path / "Show.S01E02.mkv"
    file_repo = FakeFileRepo(
        [
            LibraryFile(
                id="file-1",
                task_id="task-1",
                directory_id="dir-1",
                media_id=media_id,
                path=str(tmp_path),
                file_name=present.name,
                file_size=1,
                created_at=1.0,
                resource_attributes=ResourceAttributes(seasons=[1], episodes=[1]),
            ),
            LibraryFile(
                id="file-2",
                task_id="task-1",
                directory_id="dir-1",
                media_id=media_id,
                path=str(tmp_path),
                file_name=missing.name,
                file_size=1,
                created_at=1.0,
                resource_attributes=ResourceAttributes(seasons=[1], episodes=[2]),
            ),
        ]
    )
    episode_repo = FakeEpisodeRepo()
    artifact_repo = FakeArtifactRepo()
    emitted = {}
    monkeypatch.setattr(
        "app.services.domain.library.service.event_service.emit_media",
        lambda event, meta=None: emitted.update({"event": event, "meta": meta}),
    )
    service = LibraryService(file_repo=file_repo, episode_repo=episode_repo, artifact_repo=artifact_repo)

    health = await service.reconcile_task_primary_files(_task(media_id))

    assert health.total_primary_count == 2
    assert health.existing_primary_count == 1
    assert file_repo.removed_ids == ["file-2"]
    assert episode_repo.removed_ids == ["file-2"]
    assert artifact_repo.removed_ids == ["file-2"]
    assert emitted["event"].type.value == "library.file.missing"
    assert emitted["meta"].path == str(missing)


@pytest.mark.asyncio
async def test_mark_artifact_upserts_expected_sidecar_state():
    artifact_repo = FakeArtifactRepo()
    service = LibraryService(file_repo=FakeFileRepo(), episode_repo=FakeEpisodeRepo(), artifact_repo=artifact_repo)

    await service.mark_artifact(
        library_file_id="file-1",
        artifact_type=LibraryFileArtifactType.danmu_xml,
        expected_path="/library/Show.S01E01.danmu.xml",
        status=LibraryFileArtifactStatus.succeeded,
    )

    assert artifact_repo.marked == [
        {
            "library_file_id": "file-1",
            "artifact_type": LibraryFileArtifactType.danmu_xml,
            "expected_path": "/library/Show.S01E01.danmu.xml",
            "status": LibraryFileArtifactStatus.succeeded,
            "last_error": None,
        }
    ]
