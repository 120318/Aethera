from __future__ import annotations

from sqlalchemy import select

from app.db.sql.models import IndexerSiteHealthORM
from app.db.sql.session import SessionLocal
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
            row.client_type = status.client_type
            session.commit()
            return status

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
