from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.schemas.domain.event import Event, EventType
from app.schemas.persistence.event_dispatch import EventDispatchDeferred, EventDispatchRecord, EventDispatchStatus
from app.services.application.events.dispatch import EventDispatchService


@pytest.mark.asyncio
async def test_deferred_notification_yields_queue_and_does_not_spend_retry_attempts(monkeypatch):
    record = EventDispatchRecord(id="notification-1", event_id="batch-1", consumer_name="notifications", attempts=2)
    repo = SimpleNamespace(
        find_next_queued=AsyncMock(return_value=record),
        update=AsyncMock(return_value=True),
        cond_id=lambda value: value,
    )
    service = EventDispatchService()
    service.repo = repo
    service._event_repo = SimpleNamespace(get_by_id=lambda _: Event(id="batch-1", type=EventType.MEDIA_IMPORT_COMPLETED))
    monkeypatch.setattr(
        "app.services.application.events.dispatch.event_consumer_service",
        SimpleNamespace(dispatch=AsyncMock(side_effect=EventDispatchDeferred(delay_seconds=5))),
    )

    assert await service.run_next_queued_dispatch()
    assert record.status == EventDispatchStatus.QUEUED
    assert record.attempts == 2
    assert record.started_at is None
    assert record.available_at > datetime.now()
    assert record.error is None
