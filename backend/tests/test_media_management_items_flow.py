import os
import uuid
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

os.environ.setdefault("DATA_PATH", f"/tmp/aethera-test-data-{uuid.uuid4()}")

pytestmark = [pytest.mark.aggregation]

from app.schemas.media_id import MediaID
from app.schemas.runtime.media_management import (
    MediaManagementListRow,
    MediaManagementRowsPage,
    MediaMonitorState,
    MediaTaskSummary,
)
from app.services.application.views.media_management import MediaManagementService


def _row() -> MediaManagementListRow:
    return MediaManagementListRow(
        media_id=MediaID.parse("tmdb:tv:1"),
        season_number=1,
        title="Test Show",
        media_type="tv",
        poster_path=None,
        year=2024,
        subscribed=1,
        followed=1,
        task_count=2,
        active_task_count=1,
        error_task_count=0,
        file_missing_task_count=1,
        seeding_absent_task_count=0,
        library_count=3,
        library_episode_count=2,
        original_disc_package_count=1,
        library_size=300,
        activity_ts=0.0,
        last_task_ts=None,
        last_library_ts=None,
        last_event_message_key="eventMessages.mediaImportCompleted",
        last_event_message_params={"title": "Recent warning"},
        has_recent_error=0,
        has_recent_warning=1,
        has_issues=True,
    )


def _task_summary_map():
    media_id = MediaID.parse("tmdb:tv:1")
    return {
        str(media_id): MediaTaskSummary(
            media_id=media_id,
            task_count=2,
            active_task_count=1,
            error_task_count=0,
            file_missing_task_count=1,
            seeding_absent_task_count=0,
            last_task_at=datetime(2026, 4, 18, 12, 0, 0),
            last_task_message_key="backendErrors.transferSourceFileNotFound",
        )
    }


@pytest.mark.asyncio
async def test_list_items_builds_issue_rich_media_management_item(monkeypatch):
    service = MediaManagementService()
    media_id = MediaID.parse("tmdb:tv:1")

    monkeypatch.setattr(
        "app.services.application.views.media_management.service.media_service.list_management_rows",
        AsyncMock(return_value=MediaManagementRowsPage(total=1, rows=[_row()])),
    )
    monkeypatch.setattr(
        "app.services.application.views.media_management.service.subscription_query_service.find_current_monitors_by_media_ids",
        AsyncMock(
            return_value={
                str(media_id): MediaMonitorState(
                    subscription_id="sub-1",
                    subscribed=True,
                    followed=True,
                )
            }
        ),
    )
    monkeypatch.setattr(
        "app.services.application.views.media_management.service.download_service.summarize_media_tasks_by_media_ids",
        AsyncMock(return_value=_task_summary_map()),
    )

    page = await service.list_items(limit=10, offset=0)

    assert page.total == 1
    item = page.items[0]
    assert item.media_id == media_id
    assert item.monitor.subscribed is True
    assert item.library_episode_count == 2
    assert item.original_disc_package_count == 1
    assert item.issues.has_issues is True
    assert item.issues.codes == ["file_missing"]
    assert item.issues.summary_key == "mediaManagement.issues.fileMissing"
    assert item.last_activity_message_key == "eventMessages.mediaImportCompleted"
    assert item.last_activity_message_params == {"title": "Recent warning"}
