from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta

from app.db.repositories.event_repository import EventRepository
from app.db.repositories.event_dispatch_repository import EventDispatchRepository
from app.schemas.exception.exceptions import EventConsumerExecutionException
from app.schemas.persistence.event_dispatch import EventDispatchRecord, EventDispatchStatus
from app.services.application.events.consumer import event_consumer_service

logger = logging.getLogger("app.event_dispatch_service")


class EventDispatchService:
    def __init__(self) -> None:
        self.repo = EventDispatchRepository()
        self._event_repo = EventRepository()
        self.max_terminal_dispatches = 20000

    async def enqueue_event(self, event_id: str, event_type: str) -> None:
        consumers = event_consumer_service.match_consumers(event_type)
        for consumer in consumers:
            record = EventDispatchRecord(
                id=str(uuid.uuid4()),
                event_id=event_id,
                consumer_name=consumer.name,
            )
            await self.repo.insert(record)

    async def reset_running_dispatches(self) -> None:
        records = await self.repo.find_running()
        for record in records:
            record.status = EventDispatchStatus.QUEUED
            record.started_at = None
            record.finished_at = None
            record.available_at = datetime.now()
            await self.repo.update(record, self.repo.cond_id(record.id))

    async def run_next_queued_dispatch(self) -> bool:
        record = await self.repo.find_next_queued()
        if not record:
            return False

        record.status = EventDispatchStatus.RUNNING
        record.started_at = datetime.now()
        record.error = None
        await self.repo.update(record, self.repo.cond_id(record.id))

        event = self._event_repo.get_by_id(record.event_id)
        if not event:
            record.status = EventDispatchStatus.FAILED
            record.error = f"event not found: {record.event_id}"
            record.finished_at = datetime.now()
            await self.repo.update(record, self.repo.cond_id(record.id))
            return True

        try:
            await event_consumer_service.dispatch(event, record.consumer_name)
        except EventConsumerExecutionException as exc:
            logger.exception("Event dispatch failed: dispatch_id=%s consumer=%s", record.id, record.consumer_name)
            await self._mark_dispatch_attempt_failed(record, str(exc))
            return True
        except Exception as exc:
            logger.exception("Event dispatch failed unexpectedly: dispatch_id=%s consumer=%s", record.id, record.consumer_name)
            await self._mark_dispatch_attempt_failed(record, str(exc))
            return True

        record.status = EventDispatchStatus.SUCCEEDED
        record.attempts += 1
        record.finished_at = datetime.now()
        await self.repo.update(record, self.repo.cond_id(record.id))
        return True

    async def _mark_dispatch_attempt_failed(self, record: EventDispatchRecord, error: str) -> None:
        record.attempts += 1
        record.error = error
        record.finished_at = datetime.now()
        if record.attempts >= record.max_attempts:
            record.status = EventDispatchStatus.FAILED
        else:
            record.status = EventDispatchStatus.QUEUED
            record.available_at = datetime.now() + timedelta(seconds=min(60, 5 * record.attempts))
        await self.repo.update(record, self.repo.cond_id(record.id))

    def cleanup_retention(self) -> None:
        removed = self.repo.prune_terminal_to_limit(self.max_terminal_dispatches)
        if removed > 0:
            logger.info("Event dispatch retention cleanup removed %d records", removed)


event_dispatch_service = EventDispatchService()
