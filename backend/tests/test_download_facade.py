from unittest.mock import AsyncMock

import pytest

from app.schemas.domain.download import BatchJobResult
from app.services.domain.download.facade import DownloadService


@pytest.mark.asyncio
async def test_sync_active_downloads_preserves_batch_result_fields():
    service = DownloadService()
    service.finalize_task_downloader_changes = AsyncMock(return_value=2)
    service.task_runtime.sync_active_downloads = AsyncMock(
        return_value=BatchJobResult(
            processed=3,
            updated=1,
            completed=4,
            errors=5,
            error="client unavailable",
        )
    )

    result = await service.sync_active_downloads()

    assert result.processed == 5
    assert result.updated == 3
    assert result.completed == 4
    assert result.errors == 5
    assert result.error == "client unavailable"
