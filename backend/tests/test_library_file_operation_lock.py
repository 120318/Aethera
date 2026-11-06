import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from app.services.domain.library.deletion import LibraryDeletionWorker
from app.services.domain.library.operation_lock import LibraryFileOperationCoordinator


@pytest.mark.asyncio
async def test_library_file_delete_waits_for_cross_process_file_operation_lock(
    tmp_path,
    monkeypatch,
):
    coordinator = LibraryFileOperationCoordinator(tmp_path, retry_interval=0.001)
    query = Mock()
    query.find_file_by_id = AsyncMock(return_value=None)
    worker = LibraryDeletionWorker(
        query=query,
        file_repo=Mock(),
        artifact_repo=Mock(),
        episode_repo=Mock(),
        meta_repo=Mock(),
        cleanup=Mock(),
    )
    monkeypatch.setattr(
        "app.services.domain.library.deletion.library_file_operation_coordinator",
        coordinator,
    )

    async with coordinator.lock(["file-1"]):
        deletion = asyncio.create_task(worker.delete_file_by_id("file-1"))
        await asyncio.sleep(0.01)
        query.find_file_by_id.assert_not_awaited()

    assert await deletion is True
    query.find_file_by_id.assert_awaited_once_with("file-1")
