import os
import uuid
from unittest.mock import AsyncMock

import pytest

os.environ.setdefault("DATA_PATH", f"/tmp/aethera-test-data-{uuid.uuid4()}")

pytestmark = [pytest.mark.drift, pytest.mark.health]

from app.api.v1.resource.download_history.sync import sync_download_history
from app.schemas.domain.download import BatchJobResult


@pytest.mark.asyncio
async def test_sync_download_history_returns_fast_sync_count(monkeypatch):
    monkeypatch.setattr(
        "app.api.v1.resource.download_history.sync.download_service.sync_active_downloads",
        AsyncMock(return_value=BatchJobResult(updated=2)),
    )

    response = await sync_download_history()

    assert response.success is True
    assert response.updated_count == 2
    assert response.message_key == "operationMessages.downloadHistory.synced"
    assert response.params == {"total": 2, "fast_sync": 2}
