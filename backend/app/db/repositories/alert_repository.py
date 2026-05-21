from __future__ import annotations

from datetime import datetime

from sqlalchemy import desc, select

from app.db.sql.models import AlertORM
from app.db.sql.session import SessionLocal
from app.schemas.media_id import MediaID
from app.schemas.domain.alert import AlertRecord, AlertStatus
from app.schemas.domain.media import MediaIdentity


class AlertRepository:
    @staticmethod
    def _normalize_params(raw) -> dict[str, str]:
        if type(raw) is dict:
            return {str(key): str(value) for key, value in raw.items() if value is not None}
        return {}

    @staticmethod
    def _to_model(row: AlertORM) -> AlertRecord:
        media = None
        if row.media_id and row.media_title and row.media_year is not None:
            media = MediaIdentity(
                media_id=MediaID.parse(row.media_id),
                season_number=row.media_season_number,
                title=row.media_title,
                year=row.media_year,
            )
        return AlertRecord.model_validate(
            {
                "id": row.id,
                "fingerprint": row.fingerprint,
                "status": row.status,
                "severity": row.severity,
                "category": row.category,
                "message_key": row.message_key,
                "message_params": AlertRepository._normalize_params(row.message_params_json),
                "target_type": row.target_type,
                "target_id": row.target_id,
                "media": media,
                "media_id": row.media_id,
                "task_id": row.task_id,
                "action_id": row.action_id,
                "occurrence_count": row.occurrence_count,
                "first_seen_at": row.first_seen_at,
                "last_seen_at": row.last_seen_at,
                "acknowledged_at": row.acknowledged_at,
                "resolved_at": row.resolved_at,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
        )

    @staticmethod
    def _values(alert: AlertRecord) -> dict:
        media_id = alert.media.media_id if alert.media else alert.media_id
        return {
            "fingerprint": alert.fingerprint,
            "status": alert.status.value,
            "severity": alert.severity.value,
            "category": alert.category.value,
            "message_key": alert.message_key,
            "message_params_json": alert.message_params,
            "target_type": alert.target_type.value if alert.target_type else None,
            "target_id": alert.target_id,
            "media_id": str(media_id) if media_id else None,
            "media_season_number": alert.media.season_number if alert.media else None,
            "media_title": alert.media.title if alert.media else None,
            "media_year": alert.media.year if alert.media else None,
            "task_id": alert.task_id,
            "action_id": alert.action_id,
            "occurrence_count": alert.occurrence_count,
            "first_seen_at": alert.first_seen_at.isoformat(),
            "last_seen_at": alert.last_seen_at.isoformat(),
            "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
            "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
            "created_at": alert.created_at.isoformat(),
            "updated_at": alert.updated_at.isoformat(),
        }

    def find_by_fingerprint(self, fingerprint: str) -> AlertRecord | None:
        with SessionLocal() as session:
            row = session.execute(select(AlertORM).where(AlertORM.fingerprint == fingerprint)).scalar_one_or_none()
            return self._to_model(row) if row else None

    def find_by_id(self, alert_id: str) -> AlertRecord | None:
        with SessionLocal() as session:
            row = session.get(AlertORM, alert_id)
            return self._to_model(row) if row else None

    def upsert(self, alert: AlertRecord) -> AlertRecord:
        values = self._values(alert)
        with SessionLocal() as session:
            row = session.get(AlertORM, alert.id)
            if not row:
                row = session.execute(select(AlertORM).where(AlertORM.fingerprint == alert.fingerprint)).scalar_one_or_none()
            if row:
                for key, value in values.items():
                    setattr(row, key, value)
            else:
                session.add(AlertORM(id=alert.id, **values))
            session.commit()
        return alert

    def list_active(self, *, include_acknowledged: bool = False) -> list[AlertRecord]:
        with SessionLocal() as session:
            stmt = select(AlertORM).where(AlertORM.status == AlertStatus.active.value)
            if not include_acknowledged:
                stmt = stmt.where(AlertORM.acknowledged_at.is_(None))
            rows = session.execute(stmt.order_by(desc(AlertORM.last_seen_at))).scalars().all()
            return [self._to_model(row) for row in rows]

    def list_active_all(self) -> list[AlertRecord]:
        with SessionLocal() as session:
            rows = session.execute(
                select(AlertORM)
                .where(AlertORM.status == AlertStatus.active.value)
                .order_by(desc(AlertORM.last_seen_at))
            ).scalars().all()
            return [self._to_model(row) for row in rows]

    def acknowledge(self, alert_id: str, acknowledged_at: datetime) -> AlertRecord | None:
        alert = self.find_by_id(alert_id)
        if not alert:
            return None
        alert.acknowledged_at = acknowledged_at
        alert.updated_at = acknowledged_at
        return self.upsert(alert)

    def resolve(self, fingerprint: str, resolved_at: datetime) -> AlertRecord | None:
        alert = self.find_by_fingerprint(fingerprint)
        if not alert:
            return None
        alert.status = AlertStatus.resolved
        alert.resolved_at = resolved_at
        alert.updated_at = resolved_at
        return self.upsert(alert)
