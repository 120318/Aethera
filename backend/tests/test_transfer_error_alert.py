from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from app.schemas.domain.download import TaskContext, TaskErrorStage, TaskStatus, TaskData
from app.schemas.media_id import MediaID
from app.services.domain.transfer.service import handle_transfer_error


def _task() -> TaskData:
    media_id = MediaID.parse("tmdb:movie:1")
    return TaskData(
        id="task-1",
        torrent_hash="hash-1",
        media_id=media_id,
        status=TaskStatus.TRANSFERRING,
        context=TaskContext(
            download_url="https://example.com/file.torrent",
            directory_id="dir-1",
            media={"media_id": media_id, "title": "Test Movie", "year": 2024},
            resource_title="Test.Movie.2024.2160p",
        ),
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


@pytest.mark.asyncio
async def test_handle_transfer_error_serializes_alert_reason_params(monkeypatch):
    captured = {}
    update_task_state = AsyncMock(return_value=True)

    def raise_alert(request):
        captured["request"] = request

    monkeypatch.setattr(
        "app.services.domain.transfer.service.download_service.update_task_state",
        update_task_state,
    )
    monkeypatch.setattr(
        "app.services.domain.transfer.service.alert_service.raise_alert",
        raise_alert,
    )

    await handle_transfer_error(
        _task(),
        "backendErrors.transferFailed",
        {"reason": "disk full"},
    )

    update_task_state.assert_awaited_once_with(
        "task-1",
        TaskStatus.FINISHED,
        error_key="backendErrors.transferFailed",
        error_params={"reason": "disk full"},
        error_stage=TaskErrorStage.TRANSFER,
    )
    request = captured["request"]
    assert request.message_params == {
        "task": "Test.Movie.2024.2160p",
        "reason_key": "backendErrors.transferFailed",
        "reason_params": '{"reason": "disk full"}',
    }
    assert request.message_key == "alertMessages.taskTransferFailed"
