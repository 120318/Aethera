from __future__ import annotations

import time

from sqlalchemy import case, desc, select, update

from app.db.sql.models import MediaSubscriptionCycleORM
from app.db.sql.session import SessionLocal
from app.schemas.domain.media_subscription_cycle import MediaSubscriptionCycle, SubscriptionCycleStatus
from app.schemas.media_id import MediaID
from app.schemas.runtime.media_management import MediaMonitorState


def _storage_season(media_id: MediaID, season_number: int | None) -> int:
    if media_id.media_type.value != "tv":
        return 0
    return int(season_number or 0)


def _model_season(value: int | None) -> int | None:
    normalized = int(value or 0)
    return normalized if normalized > 0 else None


class MediaSubscriptionCycleRepository:
    @staticmethod
    def _to_model(row: MediaSubscriptionCycleORM) -> MediaSubscriptionCycle:
        return MediaSubscriptionCycle(
            cycle_id=row.cycle_id,
            media_id=MediaID.parse(row.media_id),
            season_number=_model_season(row.season_number),
            sub_id=row.sub_id,
            status=row.status,
            started_at=row.started_at,
            last_checked_at=row.last_checked_at,
            ended_at=row.ended_at,
            ended_reason=row.ended_reason,
            ended_trigger=row.ended_trigger,
            warnings=row.warnings_json or [],
            completion_snapshot=row.completion_snapshot_json,
            config_fingerprint=row.config_fingerprint,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def find_active_by_media_id(self, media_id: MediaID, season_number: int | None = None) -> MediaSubscriptionCycle | None:
        with SessionLocal() as session:
            row = session.execute(
                select(MediaSubscriptionCycleORM)
                .where(
                    MediaSubscriptionCycleORM.media_id == str(media_id),
                    MediaSubscriptionCycleORM.season_number == _storage_season(media_id, season_number),
                    MediaSubscriptionCycleORM.status == SubscriptionCycleStatus.ACTIVE.value,
                )
                .order_by(desc(MediaSubscriptionCycleORM.created_at))
            ).scalars().first()
            return self._to_model(row) if row else None

    async def find_latest_by_media_id(self, media_id: MediaID, season_number: int | None = None) -> MediaSubscriptionCycle | None:
        with SessionLocal() as session:
            row = session.execute(
                select(MediaSubscriptionCycleORM)
                .where(
                    MediaSubscriptionCycleORM.media_id == str(media_id),
                    MediaSubscriptionCycleORM.season_number == _storage_season(media_id, season_number),
                )
                .order_by(desc(MediaSubscriptionCycleORM.created_at))
            ).scalars().first()
            return self._to_model(row) if row else None

    async def find_latest_by_media_targets(
        self,
        targets: list[tuple[MediaID, int | None]],
    ) -> dict[tuple[str, int], MediaSubscriptionCycle]:
        if not targets:
            return {}
        media_values = sorted({str(media_id) for media_id, _season_number in targets})
        requested_keys = {
            (str(media_id), _storage_season(media_id, season_number))
            for media_id, season_number in targets
        }
        with SessionLocal() as session:
            rows = session.execute(
                select(MediaSubscriptionCycleORM)
                .where(MediaSubscriptionCycleORM.media_id.in_(media_values))
                .order_by(MediaSubscriptionCycleORM.media_id.asc(), desc(MediaSubscriptionCycleORM.created_at))
            ).scalars().all()

        cycles: dict[tuple[str, int], MediaSubscriptionCycle] = {}
        for row in rows:
            key = (row.media_id, int(row.season_number or 0))
            if key not in requested_keys or key in cycles:
                continue
            cycles[key] = self._to_model(row)
        return cycles

    async def find_current_by_media_id(
        self,
        media_id: MediaID,
        season_number: int | None = None,
    ) -> tuple[MediaSubscriptionCycle | None, MediaSubscriptionCycle | None]:
        with SessionLocal() as session:
            row = session.execute(
                select(MediaSubscriptionCycleORM)
                .where(
                    MediaSubscriptionCycleORM.media_id == str(media_id),
                    MediaSubscriptionCycleORM.season_number == _storage_season(media_id, season_number),
                )
                .order_by(
                    case((MediaSubscriptionCycleORM.status == SubscriptionCycleStatus.ACTIVE.value, 0), else_=1),
                    desc(MediaSubscriptionCycleORM.created_at),
                )
                .limit(1)
            ).scalars().first()
        active_row = row if row and row.status == SubscriptionCycleStatus.ACTIVE.value else None
        latest_row = row
        return (
            self._to_model(active_row) if active_row else None,
            self._to_model(latest_row) if latest_row else None,
        )

    async def find_active_by_sub_id(self, sub_id: str) -> MediaSubscriptionCycle | None:
        with SessionLocal() as session:
            row = session.execute(
                select(MediaSubscriptionCycleORM)
                .where(
                    MediaSubscriptionCycleORM.sub_id == sub_id,
                    MediaSubscriptionCycleORM.status == SubscriptionCycleStatus.ACTIVE.value,
                )
                .order_by(desc(MediaSubscriptionCycleORM.created_at))
            ).scalars().first()
            return self._to_model(row) if row else None

    async def find_latest_by_sub_id(self, sub_id: str) -> MediaSubscriptionCycle | None:
        with SessionLocal() as session:
            row = session.execute(
                select(MediaSubscriptionCycleORM)
                .where(MediaSubscriptionCycleORM.sub_id == sub_id)
                .order_by(desc(MediaSubscriptionCycleORM.created_at))
            ).scalars().first()
            return self._to_model(row) if row else None

    async def get_active_cycles(self) -> list[MediaSubscriptionCycle]:
        with SessionLocal() as session:
            rows = session.execute(
                select(MediaSubscriptionCycleORM)
                .where(MediaSubscriptionCycleORM.status == SubscriptionCycleStatus.ACTIVE.value)
                .order_by(MediaSubscriptionCycleORM.created_at.desc())
            ).scalars().all()
            return [self._to_model(row) for row in rows]

    async def find_active_by_media_targets(
        self,
        targets: list[tuple[MediaID, int | None]],
    ) -> dict[tuple[str, int], MediaSubscriptionCycle]:
        if not targets:
            return {}
        media_values = sorted({str(media_id) for media_id, _season_number in targets})
        requested_keys = {
            (str(media_id), _storage_season(media_id, season_number))
            for media_id, season_number in targets
        }
        with SessionLocal() as session:
            rows = session.execute(
                select(MediaSubscriptionCycleORM)
                .where(
                    MediaSubscriptionCycleORM.media_id.in_(media_values),
                    MediaSubscriptionCycleORM.status == SubscriptionCycleStatus.ACTIVE.value,
                )
                .order_by(MediaSubscriptionCycleORM.media_id.asc(), desc(MediaSubscriptionCycleORM.created_at))
            ).scalars().all()

        cycles: dict[tuple[str, int], MediaSubscriptionCycle] = {}
        for row in rows:
            key = (row.media_id, int(row.season_number or 0))
            if key not in requested_keys or key in cycles:
                continue
            cycles[key] = self._to_model(row)
        return cycles

    async def upsert(self, cycle: MediaSubscriptionCycle) -> str:
        payload = cycle.model_dump(mode="json")
        payload["media_id"] = str(cycle.media_id)
        payload["season_number"] = _storage_season(cycle.media_id, cycle.season_number)
        payload["status"] = cycle.status.value
        payload["ended_reason"] = cycle.ended_reason.value if cycle.ended_reason else None
        payload["ended_trigger"] = cycle.ended_trigger.value if cycle.ended_trigger else None
        payload["warnings_json"] = payload.pop("warnings", None) or None
        payload["completion_snapshot_json"] = payload.pop("completion_snapshot", None)
        payload["cycle_id"] = payload.pop("cycle_id")
        with SessionLocal() as session:
            existing = session.get(MediaSubscriptionCycleORM, cycle.cycle_id)
            if existing:
                session.execute(
                    update(MediaSubscriptionCycleORM)
                    .where(MediaSubscriptionCycleORM.cycle_id == cycle.cycle_id)
                    .values(**payload)
                )
            else:
                session.add(MediaSubscriptionCycleORM(**payload))
            session.commit()
            return cycle.cycle_id

    async def touch_last_checked(self, cycle_id: str, checked_at: float | None = None) -> bool:
        with SessionLocal() as session:
            result = session.execute(
                update(MediaSubscriptionCycleORM)
                .where(MediaSubscriptionCycleORM.cycle_id == cycle_id)
                .values(last_checked_at=checked_at if checked_at is not None else time.time(), updated_at=time.time())
            )
            session.commit()
            return bool(result.rowcount)

    async def find_current_monitors_by_media_ids(self, media_ids: list[MediaID]) -> dict[str, MediaMonitorState]:
        if not media_ids:
            return {}
        media_values = [str(media_id) for media_id in media_ids]
        with SessionLocal() as session:
            rows = session.execute(
                select(MediaSubscriptionCycleORM)
                .where(
                    MediaSubscriptionCycleORM.media_id.in_(media_values),
                    MediaSubscriptionCycleORM.status == SubscriptionCycleStatus.ACTIVE.value,
                )
                .order_by(MediaSubscriptionCycleORM.media_id.asc(), desc(MediaSubscriptionCycleORM.created_at))
            ).scalars().all()

        monitors: dict[str, MediaMonitorState] = {}
        for row in rows:
            if row.media_id in monitors:
                continue
            monitors[row.media_id] = MediaMonitorState(
                subscription_id=row.sub_id,
                subscribed=True,
                followed=False,
                last_run_at=row.last_checked_at,
            )
        return monitors
