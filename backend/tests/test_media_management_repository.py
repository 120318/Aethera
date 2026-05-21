import os
import uuid

import pytest
from sqlalchemy import text

os.environ["DATA_PATH"] = f"/tmp/aethera-test-data-{uuid.uuid4()}"

from app.db.repositories.media_management_repository import ACTIVE_TASK_STATUSES, media_management_repository
from app.db.sql.models import (
    EventORM,
    LibraryFileArtifactORM,
    LibraryFileORM,
    ManagedMediaProfileORM,
    MediaSubscriptionCycleORM,
    MediaSubscriptionSettingsORM,
    TaskORM,
)
from app.db.sql.session import SessionLocal, engine
from app.schemas.domain.download import TaskStatus
from app.schemas.domain.library import LibraryFileArtifactStatus, LibraryFileArtifactType


pytestmark = [pytest.mark.aggregation]


def _insert_profile(session, media_id: str, title: str, year: int, *, media_type: str = "tv") -> None:
    session.add(
        ManagedMediaProfileORM(
            media_id=media_id,
            media_type=media_type,
            title=title,
            original_title=None,
            poster_path=None,
            backdrop_path=None,
            logo_path=None,
            year=year,
            overview=None,
            genres_json=[],
            imdb_id=None,
            douban_id=None,
            tmdb_id=None,
            tvdb_id=None,
            actors_json=[],
            directors_json=[],
            studios_json=[],
            duration=None,
            rating_count=None,
            vote_average=None,
            vote_count=None,
            rating_source=None,
            release_date=None,
            seasons_count=None,
            episodes_count=None,
            status=None,
            original_language=None,
            is_active=1,
            last_seen_at=1000.0,
            inactive_since=None,
            detail_ready=1,
            simple_info_updated_at=1000.0,
            detail_updated_at=1000.0,
            schedule_updated_at=1000.0,
            created_at=1000.0,
            updated_at=1000.0,
        )
    )


def _insert_subscription(session, media_id: str, *, active: bool, followed: bool, season_number: int = 0) -> None:
    sub_id = f"sub-{media_id}-{season_number}"
    session.add(
        MediaSubscriptionSettingsORM(
            sub_id=sub_id,
            media_id=media_id,
            season_number=season_number,
            sites_json=None,
            filters_json=None,
            filter_config_id=None,
            directory_id="dir-1" if active else None,
            followed=1 if followed else 0,
            subscription_mode="active" if active else "follow",
            upgrade_policy_json=None,
            target_filters_json=None,
            target_filter_config_id=None,
            quality_profile_id=None,
            unmatched_rules_json=[],
            created_at=1000.0,
            updated_at=1000.0,
            follow_reminded_air_date=None,
            follow_reminded_at=None,
        )
    )
    if active:
        session.add(
            MediaSubscriptionCycleORM(
                cycle_id=f"cycle-{media_id}-{season_number}",
                media_id=media_id,
                season_number=season_number,
                sub_id=sub_id,
                status="active",
                started_at=1000.0,
                last_checked_at=None,
                ended_at=None,
                ended_reason=None,
                ended_trigger=None,
                warnings_json=[],
                completion_snapshot_json=None,
                config_fingerprint=None,
                created_at=1000.0,
                updated_at=1000.0,
            )
        )


def _insert_task(session, media_id: str, task_id: str, status: str, updated_at: str) -> None:
    session.add(
        TaskORM(
            id=task_id,
            media_id=media_id,
            provider=None,
            provider_item_id=None,
            torrent_hash=f"hash-{task_id}",
            status=status,
            error_stage=None,
            progress=1.0,
            error_key=None,
            context_json={
                "download_url": "https://example.com/file.torrent",
                "directory_id": "dir-1",
                "media": {"media_id": media_id, "title": "Title", "year": 2024},
            },
            downloader_id="downloader-1",
            download_client=None,
            download_client_url=None,
            save_path=None,
            created_at=updated_at,
            updated_at=updated_at,
            metadata_json=None,
        )
    )


def _insert_event(
    session,
    media_id: str,
    event_type: str,
    level: str,
    message: str,
    ts: str,
    *,
    season_number: int | None = None,
) -> None:
    session.add(
        EventORM(
            id=f"event-{media_id}-{season_number}-{event_type}-{level}",
            ts=ts,
            type=event_type,
            level=level,
            message_key=message,
            message_params_json={},
            search_text="",
            media_id=media_id,
            media_season_number=season_number,
            media_title="Title",
            media_year=2024,
            task_id=None,
            subscription_id=None,
            actor="system",
            source="base",
            addon_id=None,
            addon_name=None,
            entities_json=[],
            meta_json={},
            correlation_id=None,
            action_id=None,
        )
    )


def _insert_library_file(session, media_id: str, file_id: str, created_at: float = 1000.0) -> None:
    session.add(
        LibraryFileORM(
            id=file_id,
            task_id=f"task-{file_id}",
            directory_id="dir-1",
            media_id=media_id,
            path="/library",
            file_name=f"{file_id}.mkv",
            file_size=1024,
            file_index=0,
            created_at=created_at,
            resource_attributes_json={},
        )
    )


def _insert_artifact(
    session,
    file_id: str,
    artifact_id: str,
    *,
    status: LibraryFileArtifactStatus,
    updated_at: float,
    last_success_at: float | None = None,
) -> None:
    session.add(
        LibraryFileArtifactORM(
            id=artifact_id,
            library_file_id=file_id,
            artifact_type=LibraryFileArtifactType.nfo.value,
            expected_path=f"/library/{artifact_id}.nfo",
            status=status.value,
            last_success_at=last_success_at,
            last_error=None,
            next_retry_at=None,
            created_at=updated_at,
            updated_at=updated_at,
        )
    )


@pytest.fixture(autouse=True)
def _fresh_database():
    with SessionLocal() as session:
        session.execute(text("DELETE FROM events"))
        session.execute(text("DELETE FROM library_file_artifacts"))
        session.execute(text("DELETE FROM library_episodes"))
        session.execute(text("DELETE FROM library_files"))
        session.execute(text("DELETE FROM tasks"))
        session.execute(text("DELETE FROM media_subscription_cycles"))
        session.execute(text("DELETE FROM media_subscription_settings"))
        session.execute(text("DELETE FROM managed_media_profiles"))
        session.commit()
    engine.dispose()
    yield
    with SessionLocal() as session:
        session.execute(text("DELETE FROM events"))
        session.execute(text("DELETE FROM library_file_artifacts"))
        session.execute(text("DELETE FROM library_episodes"))
        session.execute(text("DELETE FROM library_files"))
        session.execute(text("DELETE FROM tasks"))
        session.execute(text("DELETE FROM media_subscription_cycles"))
        session.execute(text("DELETE FROM media_subscription_settings"))
        session.execute(text("DELETE FROM managed_media_profiles"))
        session.commit()


def test_media_management_repository_filters_issues_and_prefers_business_events():
    with SessionLocal() as session:
        _insert_profile(session, "tmdb:tv:1", "Show A", 2024)
        _insert_profile(session, "tmdb:tv:2", "Show B", 2024)
        _insert_subscription(session, "tmdb:tv:1", active=True, followed=True)
        _insert_task(session, "tmdb:tv:1", "task-1", "file_missing", "2026-04-18T12:00:00")
        _insert_task(session, "tmdb:tv:2", "task-2", "completed", "2026-04-18T11:00:00")
        _insert_event(
            session,
            "tmdb:tv:1",
            "media.import",
            "warning",
            "Business warning",
            "2026-04-18T12:10:00",
            season_number=1,
        )
        _insert_event(
            session,
            "tmdb:tv:1",
            "scheduler.sync",
            "error",
            "Should be ignored",
            "2026-04-18T12:20:00",
            season_number=1,
        )
        session.commit()

    page = media_management_repository.list_page(statuses=["issues"], sort="issues", direction="desc", limit=10, offset=0)

    assert page.total == 1
    row = page.rows[0]
    assert str(row.media_id) == "tmdb:tv:1"
    assert row.file_missing_task_count == 1
    assert row.has_recent_warning == 1
    assert row.last_event_message_key == "Business warning"
    assert row.last_event_message_params == {}


def test_media_management_repository_scopes_recent_events_by_tv_season():
    with SessionLocal() as session:
        _insert_profile(session, "tmdb:tv:1", "Show A", 2024)
        _insert_subscription(session, "tmdb:tv:1", active=True, followed=True, season_number=1)
        _insert_subscription(session, "tmdb:tv:1", active=True, followed=True, season_number=2)
        _insert_event(
            session,
            "tmdb:tv:1",
            "subscription.run",
            "error",
            "Season 2 error",
            "2026-04-18T12:10:00",
            season_number=2,
        )
        session.commit()

    page = media_management_repository.list_page(sort="title", direction="asc", limit=10, offset=0)

    rows_by_season = {row.season_number: row for row in page.rows}
    assert page.total == 2
    assert rows_by_season[1].has_recent_error == 0
    assert rows_by_season[1].has_issues is False
    assert rows_by_season[2].has_recent_error == 1
    assert rows_by_season[2].has_issues is False
    assert rows_by_season[2].last_event_message_key == "Season 2 error"


def test_media_management_repository_counts_succeeded_artifacts_as_activity():
    with SessionLocal() as session:
        _insert_profile(session, "tmdb:movie:1", "Movie A", 2024, media_type="movie")
        _insert_profile(session, "tmdb:movie:2", "Movie B", 2024, media_type="movie")
        _insert_library_file(session, "tmdb:movie:1", "file-1")
        _insert_library_file(session, "tmdb:movie:2", "file-2")
        _insert_artifact(
            session,
            "file-1",
            "artifact-success",
            status=LibraryFileArtifactStatus.succeeded,
            updated_at=2000.0,
            last_success_at=2000.0,
        )
        _insert_artifact(
            session,
            "file-2",
            "artifact-failed",
            status=LibraryFileArtifactStatus.failed,
            updated_at=3000.0,
        )
        _insert_task(session, "tmdb:movie:2", "task-2", "completed", "1970-01-01T00:25:00")
        session.commit()

    page = media_management_repository.list_page(sort="activity", direction="desc", limit=10, offset=0)

    assert page.total == 2
    assert [str(row.media_id) for row in page.rows] == ["tmdb:movie:1", "tmdb:movie:2"]
    assert page.rows[0].activity_ts == 2000.0
    assert page.rows[0].last_artifact_ts == 2000.0
    assert page.rows[1].last_artifact_ts is None


def test_media_management_active_task_statuses_include_migrating():
    assert TaskStatus.MIGRATING.value in ACTIVE_TASK_STATUSES


def test_media_management_repository_sorts_by_tasks_and_filters_by_query():
    with SessionLocal() as session:
        _insert_profile(session, "tmdb:tv:1", "Alpha Show", 2024)
        _insert_profile(session, "tmdb:tv:2", "Beta Show", 2024)
        _insert_task(session, "tmdb:tv:1", "task-1", "downloading", "2026-04-18T12:00:00")
        _insert_task(session, "tmdb:tv:1", "task-2", "finished", "2026-04-18T12:10:00")
        _insert_task(session, "tmdb:tv:2", "task-3", "completed", "2026-04-18T11:00:00")
        session.commit()

    page = media_management_repository.list_page(
        query="show",
        sort="tasks",
        direction="desc",
        limit=10,
        offset=0,
    )

    assert page.total == 2
    assert [str(row.media_id) for row in page.rows] == ["tmdb:tv:1", "tmdb:tv:2"]
    assert page.rows[0].active_task_count == 2
    assert page.rows[1].active_task_count == 0


def test_media_management_repository_does_not_create_default_tv_season_scope():
    with SessionLocal() as session:
        _insert_profile(session, "tmdb:tv:259537", "Sample", 2024)
        _insert_subscription(session, "tmdb:tv:259537", active=False, followed=True, season_number=2)
        session.commit()

    page = media_management_repository.list_page(query="Sample", sort="title", direction="asc", limit=10, offset=0)

    assert page.total == 1
    assert str(page.rows[0].media_id) == "tmdb:tv:259537"
    assert page.rows[0].season_number == 2
    assert page.rows[0].followed == 1
