import os
import uuid

import pytest
from sqlalchemy import text

os.environ["DATA_PATH"] = f"/tmp/aethera-test-data-{uuid.uuid4()}"

from app.db.repositories.library_replace_repository import LibraryReplaceRepository
from app.db.sql.models import EventDispatchORM, EventORM, LibraryEpisodeORM, LibraryFileORM, LibraryMetaORM, TaskORM
from app.db.sql.session import SessionLocal
from app.schemas.media_id import MediaID
from app.schemas.domain.download import TransferFileResult
from app.schemas.domain.event import Event, EventType
from app.schemas.domain.library import LibraryFile
from app.schemas.domain.resource_attributes import ResourceAttributes
from app.schemas.domain.torrent import TorrentFileItem
from app.schemas.persistence.event_dispatch import EventDispatchRecord


pytestmark = [pytest.mark.aggregation]


@pytest.fixture(autouse=True)
def _fresh_library_tables():
    with SessionLocal() as session:
        session.execute(text("DELETE FROM library_episodes"))
        session.execute(text("DELETE FROM library_files"))
        session.execute(text("DELETE FROM library_meta"))
        session.execute(text("DELETE FROM tasks"))
        session.execute(text("DELETE FROM event_dispatches"))
        session.execute(text("DELETE FROM events"))
        session.commit()
    yield
    with SessionLocal() as session:
        session.execute(text("DELETE FROM library_episodes"))
        session.execute(text("DELETE FROM library_files"))
        session.execute(text("DELETE FROM library_meta"))
        session.execute(text("DELETE FROM tasks"))
        session.execute(text("DELETE FROM event_dispatches"))
        session.execute(text("DELETE FROM events"))
        session.commit()


@pytest.mark.asyncio
async def test_replace_task_entries_reconciles_same_path_conflicts_from_other_tasks():
    media_id = MediaID.parse("tmdb:movie:1")
    with SessionLocal() as session:
        session.add(
            LibraryMetaORM(
                media_id=str(media_id),
                status="planned",
                created_at=1000.0,
                updated_at=1000.0,
            )
        )
        session.add(
            LibraryFileORM(
                id="file-old",
                task_id="task-old",
                directory_id="dir-1",
                media_id=str(media_id),
                path="Movies/Test Movie (2024)",
                file_name="Test.Movie.2024.mkv",
                file_size=1000,
                file_index=0,
                created_at=1000.0,
                resource_attributes_json=ResourceAttributes(resolution="1080p").model_dump(mode="json"),
            )
        )
        session.add(
            LibraryEpisodeORM(
                media_id=str(media_id),
                season=1,
                episode=1,
                file_id="file-old",
                created_at=1000.0,
            )
        )
        session.commit()

    repo = LibraryReplaceRepository()
    await repo.replace_task_entries(
        "task-new",
        "dir-1",
        media_id,
        [
            TransferFileResult(
                source_path="/downloads/Test.Movie.2024.mkv",
                destination_path="/data/library/Movies/Test Movie (2024)/Test.Movie.2024.mkv",
                file_index=0,
                file_item=TorrentFileItem(
                    index=0,
                    filename="Test.Movie.2024.mkv",
                    size=1200,
                    attrs=ResourceAttributes(resolution="2160p"),
                ),
            )
        ],
        season=1,
    )

    with SessionLocal() as session:
        files = session.query(LibraryFileORM).all()
        episodes = session.query(LibraryEpisodeORM).all()

    assert len(files) == 1
    assert files[0].task_id == "task-new"
    assert files[0].path == "Movies/Test Movie (2024)"
    assert files[0].file_name == "Test.Movie.2024.mkv"
    assert files[0].resource_attributes_json["resolution"] == "2160p"
    assert len(episodes) == 0


@pytest.mark.asyncio
async def test_replace_task_entries_removes_explicit_replacement_files():
    media_id = MediaID.parse("tmdb:movie:1")
    replacement_data = {
        "id": "file-replaced",
        "task_id": "task-old",
        "directory_id": "dir-1",
        "media_id": str(media_id),
        "path": "Movies/Test Movie (2024)",
        "file_name": "Test.Movie.2024.1080p.mkv",
        "file_size": 1000,
        "file_index": 0,
        "created_at": 1000.0,
        "resource_attributes_json": ResourceAttributes(resolution="1080p").model_dump(mode="json"),
    }
    with SessionLocal() as session:
        session.add(LibraryFileORM(**replacement_data))
        session.add(
            LibraryEpisodeORM(
                media_id=str(media_id),
                season=1,
                episode=1,
                file_id="file-replaced",
                created_at=1000.0,
            )
        )
        session.commit()

    repo = LibraryReplaceRepository()
    replaced = await repo.replace_task_entries(
        "task-new",
        "dir-1",
        media_id,
        [
            TransferFileResult(
                source_path="/downloads/Test.Movie.2024.2160p.mkv",
                destination_path="/data/library/Movies/Test Movie (2024)/Test.Movie.2024.2160p.mkv",
                file_index=0,
                file_item=TorrentFileItem(
                    index=0,
                    filename="Test.Movie.2024.2160p.mkv",
                    size=2000,
                    attrs=ResourceAttributes(resolution="2160p"),
                ),
            )
        ],
        replacement_files=[
            LibraryFile.model_validate(
                {
                    "id": replacement_data["id"],
                    "task_id": replacement_data["task_id"],
                    "directory_id": replacement_data["directory_id"],
                    "media_id": replacement_data["media_id"],
                    "path": replacement_data["path"],
                    "file_name": replacement_data["file_name"],
                    "file_size": replacement_data["file_size"],
                    "file_index": replacement_data["file_index"],
                    "created_at": replacement_data["created_at"],
                    "resource_attributes": replacement_data["resource_attributes_json"],
                }
            )
        ],
    )

    with SessionLocal() as session:
        files = session.query(LibraryFileORM).all()
        episodes = session.query(LibraryEpisodeORM).all()

    assert [item.id for item in replaced] == ["file-replaced"]
    assert len(files) == 1
    assert files[0].task_id == "task-new"
    assert files[0].file_name == "Test.Movie.2024.2160p.mkv"
    assert episodes == []


@pytest.mark.asyncio
async def test_replace_task_entries_registers_multi_episode_file():
    media_id = MediaID.parse("tmdb:tv:1")
    repo = LibraryReplaceRepository()

    await repo.replace_task_entries(
        "task-new",
        "dir-1",
        media_id,
        [
            TransferFileResult(
                source_path="/downloads/Friends.S10E17E18.mkv",
                destination_path="/data/library/TV/Friends (1994)/Season 10/Friends - S10E17E18.mkv",
                file_index=0,
                file_item=TorrentFileItem(
                    index=0,
                    filename="Friends.S10E17E18.mkv",
                    size=2000,
                    attrs=ResourceAttributes(seasons=[10], episodes=[17, 18], resolution="1080p"),
                ),
                episode_number=17,
                episode_numbers=[17, 18],
            )
        ],
        season=10,
    )

    with SessionLocal() as session:
        files = session.query(LibraryFileORM).all()
        episodes = session.query(LibraryEpisodeORM).order_by(LibraryEpisodeORM.episode.asc()).all()

    assert len(files) == 1
    assert files[0].file_name == "Friends - S10E17E18.mkv"
    assert files[0].resource_attributes_json["episodes"] == [17, 18]
    assert [(item.season, item.episode, item.file_id) for item in episodes] == [
        (10, 17, files[0].id),
        (10, 18, files[0].id),
    ]


@pytest.mark.asyncio
async def test_incremental_replace_records_imported_indices_in_same_transaction():
    media_id = MediaID.parse("tmdb:tv:1")
    with SessionLocal.begin() as session:
        session.add(TaskORM(
            id="task-new",
            media_id=str(media_id),
            provider="tmdb",
            provider_item_id="1",
            torrent_hash="hash",
            status="downloading",
            progress=0.5,
            error_params_json={},
            context_json={"imported_file_indices": [2]},
            created_at="2026-01-01T00:00:00",
            updated_at="2026-01-01T00:00:00",
        ))

    result = TransferFileResult(
        source_path="/downloads/E2.mkv",
        destination_path="/data/library/TV/Show/Season 01/Show - S01E02.mkv",
        file_index=5,
        file_item=TorrentFileItem(
            index=5,
            filename="E2.mkv",
            size=2000,
            attrs=ResourceAttributes(seasons=[1], episodes=[2], resolution="1080p"),
        ),
        episode_number=2,
        episode_numbers=[2],
    )
    repo = LibraryReplaceRepository()
    await repo.replace_task_entries(
        "task-new",
        "dir-1",
        media_id,
        [result],
        season=1,
        incremental=True,
        imported_file_indices=[5, 2],
        completion_event=Event(id="event-1", type=EventType.MEDIA_IMPORT_COMPLETED, task_id="task-new"),
        dispatch_records=[EventDispatchRecord(
            id="dispatch-1",
            event_id="event-1",
            consumer_name="test-consumer",
        )],
    )

    with SessionLocal() as session:
        task = session.get(TaskORM, "task-new")
        files = session.query(LibraryFileORM).filter_by(task_id="task-new").all()
        event = session.get(EventORM, "event-1")
        dispatch = session.get(EventDispatchORM, "dispatch-1")
    assert task.context_json["imported_file_indices"] == [2, 5]
    assert [item.file_index for item in files] == [5]
    assert event.task_id == "task-new"
    assert dispatch.event_id == "event-1"

    with pytest.raises(ValueError, match="Task not found"):
        await repo.replace_task_entries(
            "missing-task",
            "dir-1",
            media_id,
            [result.model_copy(update={"destination_path": "/data/library/TV/Show/Season 01/Show - S01E03.mkv"})],
            season=1,
            incremental=True,
            imported_file_indices=[9],
        )
    with SessionLocal() as session:
        assert session.query(LibraryFileORM).filter_by(task_id="missing-task").count() == 0
