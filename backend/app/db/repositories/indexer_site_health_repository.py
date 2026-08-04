from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, not_, select, text
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.db.sql.models import EventAcknowledgementORM, EventORM, IndexerSiteHealthORM
from app.db.sql.session import SessionLocal
from app.schemas.constants.event_types import EventTypes
from app.schemas.domain.event import EventLevel
from app.schemas.runtime.indexer_site_health import IndexerSiteHealthStatus


class IndexerSiteHealthRepository:
    @staticmethod
    def _to_model(row: IndexerSiteHealthORM) -> IndexerSiteHealthStatus:
        return IndexerSiteHealthStatus.model_validate(
            {
                "indexer_id": row.indexer_id,
                "indexer_name": row.indexer_name,
                "site_id": row.site_id,
                "site_name": row.site_name,
                "status": row.status,
                "checked_at": row.checked_at,
                "last_success_at": row.last_success_at,
                "last_failure_at": row.last_failure_at,
                "consecutive_failures": row.consecutive_failures,
                "last_error_message": row.last_error_message,
                "notify_pending": bool(row.notify_pending),
                "last_notified_at": row.last_notified_at,
                "last_reopened_at": row.last_reopened_at,
                "client_type": row.client_type,
            }
        )

    def find_one(self, indexer_id: str, site_id: str) -> IndexerSiteHealthStatus | None:
        with SessionLocal() as session:
            row = session.get(IndexerSiteHealthORM, {"indexer_id": indexer_id, "site_id": site_id})
            return self._to_model(row) if row else None

    def upsert(self, status: IndexerSiteHealthStatus) -> IndexerSiteHealthStatus:
        with SessionLocal() as session:
            row = session.get(
                IndexerSiteHealthORM,
                {"indexer_id": status.indexer_id, "site_id": status.site_id},
            )
            if row is None:
                row = IndexerSiteHealthORM(indexer_id=status.indexer_id, site_id=status.site_id)
                session.add(row)

            row.indexer_name = status.indexer_name or ""
            row.site_name = status.site_name or ""
            row.status = status.status
            row.checked_at = status.checked_at.isoformat() if status.checked_at else None
            row.last_success_at = status.last_success_at.isoformat() if status.last_success_at else None
            row.last_failure_at = status.last_failure_at.isoformat() if status.last_failure_at else None
            row.consecutive_failures = status.consecutive_failures
            row.last_error_message = status.last_error_message
            row.notify_pending = bool(status.notify_pending)
            row.last_notified_at = status.last_notified_at.isoformat() if status.last_notified_at else None
            row.last_reopened_at = status.last_reopened_at.isoformat() if status.last_reopened_at else None
            row.client_type = status.client_type
            session.commit()
            return status

    @staticmethod
    def _matches_outcome(row: IndexerSiteHealthORM | None, status: IndexerSiteHealthStatus) -> bool:
        checked_at = status.checked_at.isoformat() if status.checked_at else None
        return bool(
            row
            and row.status == status.status
            and row.checked_at == checked_at
        )

    @staticmethod
    def _matching_unhealthy_event_ids(session, correlation_id: str) -> list[str]:
        return list(
            session.execute(
                select(EventORM.id)
                .where(EventORM.correlation_id == correlation_id)
                .where(EventORM.type == EventTypes.INDEXER_SITE_UNHEALTHY.value)
                .where(EventORM.level == EventLevel.warning.value)
            ).scalars().all()
        )

    @staticmethod
    def _latest_unhealthy_event_id(session, correlation_id: str) -> str | None:
        return session.execute(
            select(EventORM.id)
            .where(EventORM.correlation_id == correlation_id)
            .where(EventORM.type == EventTypes.INDEXER_SITE_UNHEALTHY.value)
            .where(EventORM.level == EventLevel.warning.value)
            .order_by(EventORM.ts.desc(), EventORM.id.desc())
            .limit(1)
        ).scalar_one_or_none()

    def mark_unhealthy_event_emitted(
        self,
        status: IndexerSiteHealthStatus,
        notified_at: datetime,
    ) -> bool:
        with SessionLocal() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            row = session.get(
                IndexerSiteHealthORM,
                {"indexer_id": status.indexer_id, "site_id": status.site_id},
            )
            if not self._matches_outcome(row, status) or row.status != "unhealthy" or not row.notify_pending:
                session.rollback()
                return False
            row.last_notified_at = notified_at.isoformat()
            session.commit()
            return True

    def acknowledge_recovered_unhealthy_events(
        self,
        status: IndexerSiteHealthStatus,
        correlation_id: str,
    ) -> tuple[bool, int]:
        with SessionLocal() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            row = session.get(
                IndexerSiteHealthORM,
                {"indexer_id": status.indexer_id, "site_id": status.site_id},
            )
            if not self._matches_outcome(row, status) or row.status != "healthy" or not row.notify_pending:
                session.rollback()
                return False, 0

            event_ids = self._matching_unhealthy_event_ids(session, correlation_id)
            unacknowledged_ids = list(
                session.execute(
                    select(EventORM.id)
                    .where(EventORM.id.in_(event_ids))
                    .where(
                        not_(
                            select(EventAcknowledgementORM.event_id)
                            .where(EventAcknowledgementORM.event_id == EventORM.id)
                            .exists()
                        )
                    )
                ).scalars().all()
            ) if event_ids else []
            acknowledged_count = 0
            if unacknowledged_ids:
                result = session.execute(
                    sqlite_insert(EventAcknowledgementORM)
                    .values(
                        [
                            {"event_id": event_id, "acknowledged_at": datetime.now().isoformat()}
                            for event_id in unacknowledged_ids
                        ]
                    )
                    .on_conflict_do_nothing(index_elements=[EventAcknowledgementORM.event_id])
                )
                acknowledged_count = int(result.rowcount or 0)
            row.notify_pending = False
            session.commit()
            return True, acknowledged_count

    def reopen_unhealthy_events(
        self,
        status: IndexerSiteHealthStatus,
        correlation_id: str,
    ) -> tuple[bool, int]:
        with SessionLocal() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            row = session.get(
                IndexerSiteHealthORM,
                {"indexer_id": status.indexer_id, "site_id": status.site_id},
            )
            if not self._matches_outcome(row, status) or row.status != "unhealthy" or not row.notify_pending:
                session.rollback()
                return False, 0

            event_id = self._latest_unhealthy_event_id(session, correlation_id)
            reopened_count = 0
            if event_id:
                result = session.execute(
                    delete(EventAcknowledgementORM).where(EventAcknowledgementORM.event_id == event_id)
                )
                reopened_count = int(result.rowcount or 0)
            row.last_reopened_at = status.checked_at.isoformat() if status.checked_at else datetime.now().isoformat()
            session.commit()
            return True, reopened_count

    def list_by_indexer(self, indexer_id: str) -> list[IndexerSiteHealthStatus]:
        with SessionLocal() as session:
            rows = session.execute(
                select(IndexerSiteHealthORM).where(IndexerSiteHealthORM.indexer_id == indexer_id)
            ).scalars().all()
            return [self._to_model(row) for row in rows]

    def get_all(self) -> list[IndexerSiteHealthStatus]:
        with SessionLocal() as session:
            rows = session.execute(select(IndexerSiteHealthORM)).scalars().all()
            return [self._to_model(row) for row in rows]
