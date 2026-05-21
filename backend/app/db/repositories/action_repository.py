from __future__ import annotations

import json
from sqlalchemy import delete, desc, func, select, update

from app.schemas.media_id import MediaID
from app.db.sql.models import ActionORM
from app.db.sql.session import SessionLocal
from app.schemas.domain.action import ActionKind, ActionRecord, ActionSource, ActionStatus, ActionTargetType, ActionTrigger
from app.schemas.domain.media import MediaIdentity
from app.services.audit.search_text_support import build_action_search_text


class ActionRepository:
    @staticmethod
    def _apply_filters(
        stmt,
        *,
        media_id: MediaID | None = None,
        task_id: str | None = None,
        subscription_id: str | None = None,
        target_type: ActionTargetType | None = None,
        target_id: str | None = None,
        kinds: list[ActionKind] | None = None,
        statuses: list[ActionStatus] | None = None,
        action_names: list[str] | None = None,
        triggers: list[ActionTrigger] | None = None,
        sources: list[ActionSource] | None = None,
        keyword: str | None = None,
        correlation_id: str | None = None,
    ):
        if media_id:
            stmt = stmt.where(ActionORM.media_id == str(media_id))
        if task_id:
            stmt = stmt.where(ActionORM.task_id == task_id)
        if subscription_id:
            stmt = stmt.where(ActionORM.subscription_id == subscription_id)
        if target_type:
            stmt = stmt.where(ActionORM.target_type == target_type.value)
        if target_id:
            stmt = stmt.where(ActionORM.target_id == target_id)
        if kinds:
            stmt = stmt.where(ActionORM.kind.in_([kind.value for kind in kinds]))
        if statuses:
            stmt = stmt.where(ActionORM.status.in_([status.value for status in statuses]))
        if action_names:
            stmt = stmt.where(ActionORM.action_name.in_(action_names))
        if triggers:
            stmt = stmt.where(ActionORM.trigger.in_([trigger.value for trigger in triggers]))
        if sources:
            stmt = stmt.where(ActionORM.source.in_([source.value for source in sources]))
        if keyword:
            stmt = stmt.where(func.lower(ActionORM.search_text).like(f"%{keyword.lower()}%"))
        if correlation_id:
            stmt = stmt.where(ActionORM.correlation_id == correlation_id)
        return stmt

    @staticmethod
    def _build_filtered_stmt(
        *,
        media_id: MediaID | None = None,
        task_id: str | None = None,
        subscription_id: str | None = None,
        target_type: ActionTargetType | None = None,
        target_id: str | None = None,
        kinds: list[ActionKind] | None = None,
        statuses: list[ActionStatus] | None = None,
        action_names: list[str] | None = None,
        triggers: list[ActionTrigger] | None = None,
        sources: list[ActionSource] | None = None,
        keyword: str | None = None,
        correlation_id: str | None = None,
    ):
        return ActionRepository._apply_filters(
            select(ActionORM),
            media_id=media_id,
            task_id=task_id,
            subscription_id=subscription_id,
            target_type=target_type,
            target_id=target_id,
            kinds=kinds,
            statuses=statuses,
            action_names=action_names,
            triggers=triggers,
            sources=sources,
            keyword=keyword,
            correlation_id=correlation_id,
        )

    @staticmethod
    def _has_filter_scope(
        *,
        media_id: MediaID | None = None,
        task_id: str | None = None,
        subscription_id: str | None = None,
        target_type: ActionTargetType | None = None,
        target_id: str | None = None,
        keyword: str | None = None,
        correlation_id: str | None = None,
    ) -> bool:
        return any(
            (
                media_id,
                task_id,
                subscription_id,
                target_type,
                target_id,
                keyword,
                correlation_id,
            )
        )

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
    def _to_model(row: ActionORM) -> ActionRecord:
        media = None
        if row.media_id and row.media_title and row.media_year is not None:
            media = MediaIdentity(
                media_id=MediaID.parse(row.media_id),
                season_number=row.media_season_number,
                title=row.media_title,
                year=row.media_year,
            )
        return ActionRecord.model_validate(
            {
                "id": row.id,
                "ts": row.ts,
                "started_at": row.started_at,
                "finished_at": row.finished_at,
                "kind": row.kind,
                "action_name": row.action_name,
                "status": row.status,
                "actor": row.actor,
                "trigger": row.trigger,
                "source": row.source,
                "target_type": row.target_type,
                "target_id": row.target_id,
                "media": media,
                "media_id": row.media_id,
                "task_id": row.task_id,
                "subscription_id": row.subscription_id,
                "correlation_id": row.correlation_id,
                "message_key": row.message_key,
                "message_params": ActionRepository._normalize_params(row.message_params_json),
                "error": row.error,
                "duration_ms": row.duration_ms,
                "meta": ActionRepository._normalize_meta_text(row.meta_json),
            }
        )

    def insert(self, action: ActionRecord) -> str:
        with SessionLocal() as session:
            session.add(
                ActionORM(
                    id=action.id,
                    ts=action.ts.isoformat(),
                    started_at=action.started_at.isoformat() if action.started_at else None,
                    finished_at=action.finished_at.isoformat() if action.finished_at else None,
                    kind=action.kind.value,
                    action_name=action.action_name,
                    status=action.status.value,
                    actor=action.actor.value,
                    trigger=action.trigger.value,
                    source=action.source.value,
                    target_type=action.target_type.value if action.target_type else None,
                    target_id=action.target_id,
                    media_id=str(action.media_id) if action.media_id else None,
                    media_season_number=action.media.season_number if action.media else None,
                    media_title=action.media.title if action.media else None,
                    media_year=action.media.year if action.media else None,
                    task_id=action.task_id,
                    subscription_id=action.subscription_id,
                    correlation_id=action.correlation_id,
                    message_key=action.message_key,
                    message_params_json=action.message_params,
                    error=action.error,
                    search_text=build_action_search_text(action),
                    duration_ms=action.duration_ms,
                    meta_json=self._meta_db_value(action.meta),
                )
            )
            session.commit()
            return action.id

    def update(self, action: ActionRecord) -> bool:
        with SessionLocal() as session:
            result = session.execute(
                update(ActionORM)
                .where(ActionORM.id == action.id)
                .values(
                    ts=action.ts.isoformat(),
                    started_at=action.started_at.isoformat() if action.started_at else None,
                    finished_at=action.finished_at.isoformat() if action.finished_at else None,
                    kind=action.kind.value,
                    action_name=action.action_name,
                    status=action.status.value,
                    actor=action.actor.value,
                    trigger=action.trigger.value,
                    source=action.source.value,
                    target_type=action.target_type.value if action.target_type else None,
                    target_id=action.target_id,
                    media_id=str(action.media_id) if action.media_id else None,
                    media_season_number=action.media.season_number if action.media else None,
                    media_title=action.media.title if action.media else None,
                    media_year=action.media.year if action.media else None,
                    task_id=action.task_id,
                    subscription_id=action.subscription_id,
                    correlation_id=action.correlation_id,
                    message_key=action.message_key,
                    message_params_json=action.message_params,
                    error=action.error,
                    search_text=build_action_search_text(action),
                    duration_ms=action.duration_ms,
                    meta_json=self._meta_db_value(action.meta),
                )
            )
            session.commit()
            return bool(result.rowcount)

    def get_all(self) -> list[ActionRecord]:
        with SessionLocal() as session:
            rows = session.execute(select(ActionORM).order_by(desc(ActionORM.ts))).scalars().all()
            return [self._to_model(row) for row in rows]

    def list_filtered(
        self,
        *,
        media_id: MediaID | None = None,
        task_id: str | None = None,
        subscription_id: str | None = None,
        target_type: ActionTargetType | None = None,
        target_id: str | None = None,
        kinds: list[ActionKind] | None = None,
        statuses: list[ActionStatus] | None = None,
        action_names: list[str] | None = None,
        triggers: list[ActionTrigger] | None = None,
        sources: list[ActionSource] | None = None,
        keyword: str | None = None,
        correlation_id: str | None = None,
    ) -> list[ActionRecord]:
        with SessionLocal() as session:
            stmt = self._build_filtered_stmt(
                media_id=media_id,
                task_id=task_id,
                subscription_id=subscription_id,
                target_type=target_type,
                target_id=target_id,
                kinds=kinds,
                statuses=statuses,
                action_names=action_names,
                triggers=triggers,
                sources=sources,
                keyword=keyword,
                correlation_id=correlation_id,
            ).order_by(desc(ActionORM.ts))
            rows = session.execute(stmt).scalars().all()
            return [self._to_model(row) for row in rows]

    def list_filtered_page(
        self,
        *,
        limit: int,
        offset: int,
        media_id: MediaID | None = None,
        task_id: str | None = None,
        subscription_id: str | None = None,
        target_type: ActionTargetType | None = None,
        target_id: str | None = None,
        kinds: list[ActionKind] | None = None,
        statuses: list[ActionStatus] | None = None,
        action_names: list[str] | None = None,
        triggers: list[ActionTrigger] | None = None,
        sources: list[ActionSource] | None = None,
        keyword: str | None = None,
        correlation_id: str | None = None,
    ) -> tuple[int, list[ActionRecord]]:
        with SessionLocal() as session:
            base_stmt = self._build_filtered_stmt(
                media_id=media_id,
                task_id=task_id,
                subscription_id=subscription_id,
                target_type=target_type,
                target_id=target_id,
                kinds=kinds,
                statuses=statuses,
                action_names=action_names,
                triggers=triggers,
                sources=sources,
                keyword=keyword,
                correlation_id=correlation_id,
            )
            total = int(
                session.execute(
                    select(func.count()).select_from(base_stmt.order_by(None).subquery())
                ).scalar_one()
            )
            rows = session.execute(
                base_stmt
                .order_by(desc(ActionORM.ts))
                .limit(limit)
                .offset(offset)
            ).scalars().all()
            return total, [self._to_model(row) for row in rows]

    def list_distinct_filter_values(
        self,
        *,
        media_id: MediaID | None = None,
        task_id: str | None = None,
        subscription_id: str | None = None,
        target_type: ActionTargetType | None = None,
        target_id: str | None = None,
        keyword: str | None = None,
        correlation_id: str | None = None,
    ) -> dict[str, list[str]]:
        with SessionLocal() as session:
            has_scope = self._has_filter_scope(
                media_id=media_id,
                task_id=task_id,
                subscription_id=subscription_id,
                target_type=target_type,
                target_id=target_id,
                keyword=keyword,
                correlation_id=correlation_id,
            )
            action_name_stmt = select(ActionORM.action_name).where(ActionORM.action_name.is_not(None))
            source_stmt = select(ActionORM.source).where(ActionORM.source.is_not(None))
            if has_scope:
                action_name_stmt = self._apply_filters(
                    action_name_stmt,
                    media_id=media_id,
                    task_id=task_id,
                    subscription_id=subscription_id,
                    target_type=target_type,
                    target_id=target_id,
                    keyword=keyword,
                    correlation_id=correlation_id,
                )
                source_stmt = self._apply_filters(
                    source_stmt,
                    media_id=media_id,
                    task_id=task_id,
                    subscription_id=subscription_id,
                    target_type=target_type,
                    target_id=target_id,
                    keyword=keyword,
                    correlation_id=correlation_id,
                )
            action_name_rows = session.execute(
                action_name_stmt.distinct().order_by(ActionORM.action_name.asc())
            ).all()
            source_rows = session.execute(
                source_stmt.distinct().order_by(ActionORM.source.asc())
            ).all()
        return {
            "action_names": [value for value, in action_name_rows if value],
            "sources": [value for value, in source_rows if value],
        }

    def list_by_target_ids(
        self,
        *,
        target_type: ActionTargetType,
        target_ids: list[str],
    ) -> list[ActionRecord]:
        if not target_ids:
            return []
        with SessionLocal() as session:
            rows = session.execute(
                select(ActionORM)
                .where(ActionORM.target_type == target_type.value)
                .where(ActionORM.target_id.in_(target_ids))
                .order_by(desc(ActionORM.ts))
            ).scalars().all()
            return [self._to_model(row) for row in rows]

    def list_page_by_target(
        self,
        *,
        target_type: ActionTargetType,
        target_id: str,
        limit: int,
        offset: int,
    ) -> tuple[int, list[ActionRecord]]:
        with SessionLocal() as session:
            base_stmt = (
                select(ActionORM)
                .where(ActionORM.target_type == target_type.value)
                .where(ActionORM.target_id == target_id)
            )
            total = int(
                session.execute(
                    select(func.count()).select_from(ActionORM)
                    .where(ActionORM.target_type == target_type.value)
                    .where(ActionORM.target_id == target_id)
                ).scalar_one()
            )
            rows = session.execute(
                base_stmt
                .order_by(desc(ActionORM.ts))
                .limit(limit)
                .offset(offset)
            ).scalars().all()
            return total, [self._to_model(row) for row in rows]

    def get_by_id(self, action_id: str) -> ActionRecord | None:
        with SessionLocal() as session:
            row = session.get(ActionORM, action_id)
            return self._to_model(row) if row else None

    def prune_to_limit(self, max_records: int) -> int:
        limit = int(max_records or 0)
        if limit <= 0:
            return 0
        with SessionLocal() as session:
            total = int(session.execute(select(func.count()).select_from(ActionORM)).scalar_one() or 0)
            if total <= limit:
                return 0
            keep_ids = (
                select(ActionORM.id)
                .order_by(desc(ActionORM.ts))
                .limit(limit)
                .subquery()
            )
            result = session.execute(
                delete(ActionORM).where(ActionORM.id.not_in(select(keep_ids.c.id)))
            )
            session.commit()
            return int(result.rowcount or 0)
