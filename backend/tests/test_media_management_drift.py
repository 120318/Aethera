import os
import uuid
from datetime import datetime

import pytest

pytestmark = [pytest.mark.drift, pytest.mark.health]

os.environ.setdefault("DATA_PATH", f"/tmp/aethera-test-data-{uuid.uuid4()}")

from app.schemas.media_id import MediaID
from app.schemas.runtime.media_management import (
    MediaManagementListRow,
    MediaMonitorState,
    MediaRecentEventSummary,
    MediaTaskSummary,
)
from app.services.application.views.media_management import MediaManagementService


def _row() -> MediaManagementListRow:
    return MediaManagementListRow(
        media_id=MediaID.parse("tmdb:tv:1"),
        season_number=1,
        title="Test Show",
        media_type="tv",
        year=2024,
        task_count=2,
        active_task_count=0,
        error_task_count=0,
        file_missing_task_count=0,
        seeding_absent_task_count=0,
        library_count=1,
        library_episode_count=1,
        original_disc_package_count=0,
        library_size=123,
        activity_ts=0.0,
    )


def test_build_issue_snapshot_ignores_recent_warning_events():
    service = MediaManagementService()
    task_summary = MediaTaskSummary(
        media_id=MediaID.parse("tmdb:tv:1"),
        file_missing_task_count=1,
        seeding_absent_task_count=2,
    )
    event_summary = MediaRecentEventSummary(
        media_id=MediaID.parse("tmdb:tv:1"),
        has_recent_warning=True,
    )

    snapshot = service._build_issue_snapshot(task_summary, event_summary)

    assert snapshot.has_issues is True
    assert snapshot.codes == ["file_missing", "seeding_absent"]
    assert snapshot.summary_key == "mediaManagement.issues.fileMissing"


def test_build_item_exposes_seeding_absent_issue_in_media_management_list():
    service = MediaManagementService()
    task_summary = MediaTaskSummary(
        media_id=MediaID.parse("tmdb:tv:1"),
        seeding_absent_task_count=1,
        last_task_at=datetime(2026, 4, 18, 10, 0, 0),
        last_task_message_key="backendErrors.transferSourceFileNotFound",
    )

    item = service._build_item(
        media_id=MediaID.parse("tmdb:tv:1"),
        monitor=MediaMonitorState(subscribed=True, followed=True),
        task_summary=task_summary,
        event_summary=MediaRecentEventSummary(media_id=MediaID.parse("tmdb:tv:1")),
        row=_row(),
    )

    assert item.issues.has_issues is True
    assert item.issues.codes == ["seeding_absent"]
    assert item.issues.summary_key == "mediaManagement.issues.seedingAbsent"
    assert item.last_activity_message_key is None


def test_build_item_uses_media_id_as_title_fallback_when_profile_title_is_missing():
    service = MediaManagementService()
    row = _row().model_copy(update={"title": ""})

    item = service._build_item(
        media_id=row.media_id,
        monitor=None,
        task_summary=None,
        event_summary=None,
        row=row,
    )

    assert item.title == str(row.media_id)
