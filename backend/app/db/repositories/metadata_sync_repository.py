from __future__ import annotations

from sqlalchemy import asc, select

from app.db.sql.models import MetadataSyncORM
from app.db.sql.session import SessionLocal
from app.schemas.media_id import MediaID
from app.schemas.domain.media_server_sync import MediaServerSyncState


class MetadataSyncRepository:
    def fetch_state(self, media_server_id: str, media_id: MediaID) -> MediaServerSyncState | None:
        with SessionLocal() as session:
            row = session.get(MetadataSyncORM, (media_server_id, str(media_id)))
            if row is None:
                return None
            return MediaServerSyncState(
                media_server_id=row.media_server_id,
                media_id=MediaID.model_validate(row.media_id),
                media_type=row.media_type,
                status=row.status,
                last_check_at=row.last_check_at,
                last_success_at=row.last_success_at,
                failure_count=row.failure_count,
                last_error=row.last_error,
                next_due_at=row.next_due_at,
                missing_flags=row.missing_flags_json or [],
                updated_paths=row.updated_paths_json or [],
            )

    def save_state(self, state: MediaServerSyncState) -> None:
        media_server_id = str(state.media_server_id)
        media_id = str(state.media_id)
        with SessionLocal() as session:
            row = session.get(MetadataSyncORM, (media_server_id, media_id))
            if row is None:
                row = MetadataSyncORM(media_server_id=media_server_id, media_id=media_id)
                session.add(row)

            row.media_server_id = media_server_id
            row.media_type = state.media_type
            row.status = state.status
            row.last_check_at = float(state.last_check_at or 0)
            row.last_success_at = state.last_success_at
            row.failure_count = int(state.failure_count or 0)
            row.last_error = state.last_error
            row.next_due_at = float(state.next_due_at or 0)
            row.missing_flags_json = list(state.missing_flags or [])
            row.updated_paths_json = list(state.updated_paths or [])
            session.commit()

    def list_due_ids(self, media_server_id: str, now: float, limit: int) -> list[MediaID]:
        with SessionLocal() as session:
            rows = session.execute(
                select(MetadataSyncORM.media_id)
                .where(
                    MetadataSyncORM.media_server_id == media_server_id,
                    MetadataSyncORM.status != "paused",
                    MetadataSyncORM.next_due_at <= now,
                )
                .order_by(asc(MetadataSyncORM.next_due_at), asc(MetadataSyncORM.failure_count))
                .limit(limit)
            ).all()
            return [MediaID.model_validate(row[0]) for row in rows]

    def list_all_media_ids(self, media_server_id: str) -> set[MediaID]:
        with SessionLocal() as session:
            rows = session.execute(
                select(MetadataSyncORM.media_id).where(MetadataSyncORM.media_server_id == media_server_id)
            ).all()
            return {MediaID.model_validate(row[0]) for row in rows}
