from __future__ import annotations

from sqlalchemy import asc, delete, desc, select, update

from app.db.sql.models import EventDispatchORM
from app.db.sql.session import SessionLocal
from app.schemas.persistence.event_dispatch import EventDispatchRecord, EventDispatchStatus


class EventDispatchRepository:
    def cond_id(self, record_id: str) -> str:
        return record_id

    @staticmethod
    def _to_model(row: EventDispatchORM) -> EventDispatchRecord:
        return EventDispatchRecord.model_validate(
            {
                "id": row.id,
                "event_id": row.event_id,
                "consumer_name": row.consumer_name,
                "status": row.status,
                "attempts": row.attempts,
                "max_attempts": row.max_attempts,
                "available_at": row.available_at,
                "error": row.error,
                "created_at": row.created_at,
                "started_at": row.started_at,
                "finished_at": row.finished_at,
            }
        )

    async def insert(self, record: EventDispatchRecord) -> str:
        with SessionLocal() as session:
            session.add(
                EventDispatchORM(
                    id=record.id,
                    event_id=record.event_id,
                    consumer_name=record.consumer_name,
                    status=record.status.value,
                    attempts=record.attempts,
                    max_attempts=record.max_attempts,
                    available_at=record.available_at.isoformat(),
                    error=record.error,
                    created_at=record.created_at.isoformat(),
                    started_at=record.started_at.isoformat() if record.started_at else None,
                    finished_at=record.finished_at.isoformat() if record.finished_at else None,
                )
            )
            session.commit()
            return record.id

    async def update(self, record: EventDispatchRecord, cond: str) -> bool:
        record_id = cond
        with SessionLocal() as session:
            result = session.execute(
                update(EventDispatchORM)
                .where(EventDispatchORM.id == record_id)
                .values(
                    event_id=record.event_id,
                    consumer_name=record.consumer_name,
                    status=record.status.value,
                    attempts=record.attempts,
                    max_attempts=record.max_attempts,
                    available_at=record.available_at.isoformat(),
                    error=record.error,
                    created_at=record.created_at.isoformat(),
                    started_at=record.started_at.isoformat() if record.started_at else None,
                    finished_at=record.finished_at.isoformat() if record.finished_at else None,
                )
            )
            session.commit()
            return bool(result.rowcount)

    async def find_next_queued(self) -> EventDispatchRecord | None:
        from datetime import datetime

        now = datetime.now().isoformat()
        with SessionLocal() as session:
            row = session.execute(
                select(EventDispatchORM)
                .where(
                    EventDispatchORM.status == EventDispatchStatus.QUEUED.value,
                    EventDispatchORM.available_at <= now,
                )
                .order_by(asc(EventDispatchORM.available_at))
                .limit(1)
            ).scalars().first()
            return self._to_model(row) if row else None

    async def find_running(self) -> list[EventDispatchRecord]:
        with SessionLocal() as session:
            rows = session.execute(
                select(EventDispatchORM).where(EventDispatchORM.status == EventDispatchStatus.RUNNING.value)
            ).scalars().all()
            return [self._to_model(row) for row in rows]

    def prune_terminal_to_limit(self, max_records: int) -> int:
        limit = int(max_records or 0)
        if limit <= 0:
            return 0
        terminal_statuses = (
            EventDispatchStatus.SUCCEEDED.value,
            EventDispatchStatus.FAILED.value,
        )
        with SessionLocal() as session:
            keep_ids = (
                select(EventDispatchORM.id)
                .where(EventDispatchORM.status.in_(terminal_statuses))
                .order_by(desc(EventDispatchORM.created_at))
                .limit(limit)
                .subquery()
            )
            result = session.execute(
                delete(EventDispatchORM)
                .where(EventDispatchORM.status.in_(terminal_statuses))
                .where(EventDispatchORM.id.not_in(select(keep_ids.c.id)))
            )
            session.commit()
            return int(result.rowcount or 0)
