import os
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

pytestmark = [pytest.mark.drift, pytest.mark.health]

os.environ.setdefault("DATA_PATH", f"/tmp/aethera-test-data-{uuid.uuid4()}")

from app.services.application.commands.service import CommandConflictException
from app.services.application.workflows.scheduled_transfer.service import scheduled_transfer_command_service


@pytest.mark.asyncio
async def test_enqueue_finished_tasks_counts_conflicts_as_skips_and_runtime_failures_as_errors(monkeypatch):
    tasks = [
        SimpleNamespace(id="task-1"),
        SimpleNamespace(id="task-2"),
        SimpleNamespace(id="task-3"),
    ]

    monkeypatch.setattr(
        "app.services.application.workflows.scheduled_transfer.service.download_service.get_tasks",
        AsyncMock(return_value=tasks),
    )
    create_command_mock = AsyncMock(
        side_effect=[object(), CommandConflictException(), RuntimeError("worker down")]
    )
    monkeypatch.setattr(
        "app.services.application.workflows.scheduled_transfer.service.command_service.create_command",
        create_command_mock,
    )

    result = await scheduled_transfer_command_service.enqueue_finished_tasks()

    assert result.processed == 3
    assert result.completed == 1
    assert result.errors == 1
