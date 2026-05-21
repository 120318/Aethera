from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import delete, desc, func, not_, or_, select

from app.db.sql.models import EventORM
from app.db.sql.session import SessionLocal
from app.schemas.media_id import MediaID
from app.schemas.domain.event import Event, EventLevel, EventSource, EventType
from app.schemas.domain.media import MediaIdentity
from app.schemas.runtime.media_management import MediaRecentEventSummary
from app.services.audit.search_text_support import build_event_search_text


class EventRepository:
    @staticmethod
    def _normalize_meta_text(raw) -> str:
        if raw is None or raw == "":
            return ""
        if type(raw) is str:
            return raw
        return json.dumps(raw, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _meta_db_value(meta: str):
        if not meta:
            return {}
        return json.loads(meta)

    @staticmethod
    def _build_filtered_stmt(
        *,
        media_id: MediaID | None = None,
        media_season_number: int | None = None,
        task_id: str | None = None,
        subscription_id: str | None = None,
        levels: list[EventLevel] | None = None,
        types: list[EventType] | None = None,
        sources: list[EventSource] | None = None,
        addon_id: str | None = None,
        action_id: str | None = None,
        keyword: str | None = None,
        excluded_type_prefixes: tuple[str, ...] = (),
    ):
        stmt = select(EventORM)
        if media_id:
            stmt = stmt.where(EventORM.media_id == str(media_id))
        if media_season_number is not None:
            stmt = stmt.where(EventORM.media_season_number == media_season_number)
        if task_id:
            stmt = stmt.where(EventORM.task_id == task_id)
        if subscription_id:
            stmt = stmt.where(EventORM.subscription_id == subscription_id)
        if levels:
            stmt = stmt.where(EventORM.level.in_([level.value for level in levels]))
        if types:
            stmt = stmt.where(EventORM.type.in_([event_type.value for event_type in types]))
        if sources:
            stmt = stmt.where(EventORM.source.in_([source.value for source in sources]))
        if addon_id:
            stmt = stmt.where(EventORM.addon_id == addon_id)
        if action_id:
            stmt = stmt.where(EventORM.action_id == action_id)
        if keyword:
            stmt = stmt.where(func.lower(EventORM.search_text).like(f"%{keyword.lower()}%"))
        if excluded_type_prefixes:
            stmt = stmt.where(
                not_(or_(*[EventORM.type.like(f"{prefix}%") for prefix in excluded_type_prefixes]))
            )
        return stmt

    @staticmethod
    def _normalize_params(raw) -> dict[str, str]:
        if type(raw) is dict:
            return {str(key): str(value) for key, value in raw.items() if value is not None}
        if type(raw) is str and raw:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                return {}
            if type(data) is dict:
                return {str(key): str(value) for key, value in data.items() if value is not None}
        return {}

    @staticmethod
    def _to_model(row: EventORM) -> Event:
        media = None
        if row.media_id and row.media_title and row.media_year is not None:
            media = MediaIdentity(
                media_id=MediaID.parse(row.media_id),
                season_number=row.media_season_number,
                title=row.media_title,
                year=row.media_year,
            )
        return Event.model_validate(
            {
                "id": row.id,
                "ts": row.ts,
                "type": row.type,
                "level": row.level,
                "message_key": row.message_key,
                "message_params": EventRepository._normalize_params(row.message_params_json),
                "media": media,
                "task_id": row.task_id,
                "subscription_id": row.subscription_id,
                "actor": row.actor,
                "source": row.source,
                "addon_id": row.addon_id,
                "addon_name": row.addon_name,
                "entities": row.entities_json,
                "meta": EventRepository._normalize_meta_text(row.meta_json),
                "correlation_id": row.correlation_id,
                "action_id": row.action_id,
            }
        )

    def insert(self, event: Event) -> str:
        with SessionLocal() as session:
            session.add(
                EventORM(
                    id=event.id,
                    ts=event.ts.isoformat(),
                    type=event.type.value,
                    level=event.level.value,
                    message_key=event.message_key,
                    message_params_json=event.message_params,
                    search_text=build_event_search_text(event),
                    media_id=str(event.media_id) if event.media_id else None,
                    media_season_number=event.media.season_number if event.media else None,
                    media_title=event.media_title,
                    media_year=event.media_year,
                    task_id=event.task_id,
                    subscription_id=event.subscription_id,
                    actor=event.actor.value if event.actor else None,
                    source=event.source.value if event.source else None,
                    addon_id=event.addon_id,
                    addon_name=event.addon_name,
                    entities_json=[item.model_dump(mode="json") for item in event.entities],
                    meta_json=self._meta_db_value(event.meta),
                    correlation_id=event.correlation_id,
                    action_id=event.action_id,
                )
            )
            session.commit()
            return event.id

    def get_all(self) -> list[Event]:
        with SessionLocal() as session:
            rows = session.execute(select(EventORM).order_by(desc(EventORM.ts))).scalars().all()
            return [self._to_model(row) for row in rows]

    def list_filtered(
        self,
        *,
        media_id: MediaID | None = None,
        media_season_number: int | None = None,
        task_id: str | None = None,
        subscription_id: str | None = None,
        levels: list[EventLevel] | None = None,
        types: list[EventType] | None = None,
        sources: list[EventSource] | None = None,
        addon_id: str | None = None,
        action_id: str | None = None,
        keyword: str | None = None,
        excluded_type_prefixes: tuple[str, ...] = (),
    ) -> list[Event]:
        with SessionLocal() as session:
            stmt = self._build_filtered_stmt(
                media_id=media_id,
                media_season_number=media_season_number,
                task_id=task_id,
                subscription_id=subscription_id,
                levels=levels,
                types=types,
                sources=sources,
                addon_id=addon_id,
                action_id=action_id,
                keyword=keyword,
                excluded_type_prefixes=excluded_type_prefixes,
            ).order_by(desc(EventORM.ts))
            rows = session.execute(stmt).scalars().all()
            return [self._to_model(row) for row in rows]

    def list_filtered_page(
        self,
        *,
        limit: int,
        offset: int,
        media_id: MediaID | None = None,
        media_season_number: int | None = None,
        task_id: str | None = None,
        subscription_id: str | None = None,
        levels: list[EventLevel] | None = None,
        types: list[EventType] | None = None,
        sources: list[EventSource] | None = None,
        addon_id: str | None = None,
        action_id: str | None = None,
        keyword: str | None = None,
        excluded_type_prefixes: tuple[str, ...] = (),
    ) -> tuple[int, list[Event]]:
        with SessionLocal() as session:
            stmt = self._build_filtered_stmt(
                media_id=media_id,
                media_season_number=media_season_number,
                task_id=task_id,
                subscription_id=subscription_id,
                levels=levels,
                types=types,
                sources=sources,
                addon_id=addon_id,
                action_id=action_id,
                keyword=keyword,
                excluded_type_prefixes=excluded_type_prefixes,
            )

            total = int(
                session.execute(
                    select(func.count()).select_from(stmt.order_by(None).subquery())
                ).scalar_one()
            )
            rows = session.execute(
                stmt.order_by(desc(EventORM.ts)).limit(limit).offset(offset)
            ).scalars().all()
            return total, [self._to_model(row) for row in rows]

    def list_distinct_filter_values(
        self,
        *,
        media_id: MediaID | None = None,
        media_season_number: int | None = None,
        task_id: str | None = None,
        subscription_id: str | None = None,
        action_id: str | None = None,
    ) -> dict[str, list[str]]:
        with SessionLocal() as session:
            base_stmt = select(EventORM)
            if media_id:
                base_stmt = base_stmt.where(EventORM.media_id == str(media_id))
            if media_season_number is not None:
                base_stmt = base_stmt.where(EventORM.media_season_number == media_season_number)
            if task_id:
                base_stmt = base_stmt.where(EventORM.task_id == task_id)
            if subscription_id:
                base_stmt = base_stmt.where(EventORM.subscription_id == subscription_id)
            if action_id:
                base_stmt = base_stmt.where(EventORM.action_id == action_id)

            rows = session.execute(base_stmt).scalars().all()

        levels = sorted({row.level for row in rows if row.level})
        types = sorted({row.type for row in rows if row.type})
        sources = sorted({row.source for row in rows if row.source})
        return {
            "levels": levels,
            "types": types,
            "sources": sources,
        }

    def list_by_media_id(self, media_id: MediaID, limit: int | None = None, season_number: int | None = None) -> list[Event]:
        with SessionLocal() as session:
            stmt = (
                select(EventORM)
                .where(EventORM.media_id == str(media_id))
                .order_by(desc(EventORM.ts))
            )
            if season_number is not None:
                stmt = stmt.where(EventORM.media_season_number == season_number)
            if limit is not None:
                stmt = stmt.limit(limit)
            rows = session.execute(stmt).scalars().all()
            return [self._to_model(row) for row in rows]

    def get_by_id(self, event_id: str) -> Event | None:
        with SessionLocal() as session:
            row = session.get(EventORM, event_id)
            return self._to_model(row) if row else None

    def prune_to_limit(self, max_records: int) -> int:
        limit = int(max_records or 0)
        if limit <= 0:
            return 0
        with SessionLocal() as session:
            total = int(session.execute(select(func.count()).select_from(EventORM)).scalar_one() or 0)
            if total <= limit:
                return 0
            keep_ids = (
                select(EventORM.id)
                .order_by(desc(EventORM.ts))
                .limit(limit)
                .subquery()
            )
            result = session.execute(
                delete(EventORM).where(EventORM.id.not_in(select(keep_ids.c.id)))
            )
            session.commit()
            return int(result.rowcount or 0)

    def summarize_recent_by_media_ids(self, media_ids: list[MediaID]) -> dict[str, MediaRecentEventSummary]:
        if not media_ids:
            return {}
        media_id_values = [str(media_id) for media_id in media_ids]
        with SessionLocal() as session:
            rows = session.execute(
                select(EventORM.media_id, EventORM.level, EventORM.message_key, EventORM.message_params_json, EventORM.ts)
                .where(EventORM.media_id.in_(media_id_values))
                .order_by(EventORM.media_id.asc(), desc(EventORM.ts))
            ).all()

        summaries: dict[str, MediaRecentEventSummary] = {}
        counts: dict[str, int] = {}
        for media_id_value, level, message_key, message_params, ts in rows:
            if not media_id_value:
                continue
            if media_id_value not in summaries:
                summaries[media_id_value] = MediaRecentEventSummary(
                    media_id=media_id_value,
                    last_event_at=datetime.fromisoformat(ts) if ts else None,
                    last_event_message_key=message_key,
                    last_event_message_params=self._normalize_params(message_params),
                )
                counts[media_id_value] = 0
            if counts[media_id_value] >= 6:
                continue
            counts[media_id_value] += 1
            summary = summaries[media_id_value]
            if level == "error":
                summary.has_recent_error = True
            if level == "warning":
                summary.has_recent_warning = True
        return summaries
