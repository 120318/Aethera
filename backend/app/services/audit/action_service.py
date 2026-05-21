from __future__ import annotations

import json
import logging
from datetime import datetime
from collections.abc import Mapping

from app.db.repositories.action_repository import ActionRepository
from app.db.sql.serialization import to_jsonable
from app.schemas.media_id import MediaID
from app.schemas.domain.action import ActionActor, ActionKind, ActionName, ActionRecord, ActionSource, ActionStatus, ActionTargetType, ActionTrigger
from app.schemas.domain.media import MediaIdentity
from app.services.audit.action_catalog import (
    ACTION_FILTER_KINDS,
    ACTION_FILTER_STATUSES,
    ACTION_FILTER_TRIGGERS,
)
from app.services.audit.action_message_i18n import attach_action_message_i18n
from app.services.audit.search_text_support import build_action_search_text
from pydantic import BaseModel

logger = logging.getLogger("app.services.action")


def _action_search_blob(action: ActionRecord) -> str:
    return build_action_search_text(action)


def _normalize_action_meta(meta: BaseModel | None) -> str:
    if meta is None:
        return ""
    return json.dumps(to_jsonable(meta), ensure_ascii=False, sort_keys=True)


class ActionService:
    def __init__(self) -> None:
        self.repo = ActionRepository()
        self.max_actions = 50000
        self.max_age_days = 30

    def create_action(
        self,
        *,
        action_id: str | None = None,
        kind: ActionKind,
        action_name: str,
        status: ActionStatus,
        actor: ActionActor = ActionActor.system,
        trigger: ActionTrigger = ActionTrigger.system,
        source: ActionSource = ActionSource.system,
        target_type: ActionTargetType | None = None,
        target_id: str | None = None,
        media: MediaIdentity | None = None,
        media_id: MediaID | None = None,
        task_id: str | None = None,
        subscription_id: str | None = None,
        correlation_id: str | None = None,
        error: str | None = None,
        meta: BaseModel | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        duration_ms: int | None = None,
    ) -> ActionRecord:
        normalized_meta = _normalize_action_meta(meta)
        try:
            normalized_action_name = ActionName(action_name).value
        except ValueError:
            normalized_action_name = action_name
        resolved_media_id = media.media_id if media else media_id
        if action_id:
            action = ActionRecord(
                id=action_id,
                kind=kind,
                action_name=normalized_action_name,
                status=status,
                actor=actor,
                trigger=trigger,
                source=source,
                target_type=target_type,
                target_id=target_id,
                media=media,
                media_id=resolved_media_id,
                task_id=task_id,
                subscription_id=subscription_id,
                correlation_id=correlation_id,
                error=error,
                meta=normalized_meta,
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=duration_ms,
            )
        else:
            action = ActionRecord(
                kind=kind,
                action_name=normalized_action_name,
                status=status,
                actor=actor,
                trigger=trigger,
                source=source,
                target_type=target_type,
                target_id=target_id,
                media=media,
                media_id=resolved_media_id,
                task_id=task_id,
                subscription_id=subscription_id,
                correlation_id=correlation_id,
                error=error,
                meta=normalized_meta,
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=duration_ms,
            )
        attach_action_message_i18n(action)
        self.repo.insert(action)
        return action

    def _update_action(
        self,
        action_id: str,
        *,
        status: ActionStatus,
        error: str | None = None,
        message_params: dict[str, str] | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        duration_ms: int | None = None,
    ) -> ActionRecord | None:
        current = self.get_action(action_id)
        if not current:
            return None
        current.status = status
        current.error = error
        if message_params is not None:
            current.message_params = message_params
        if started_at is not None:
            current.started_at = started_at
        if finished_at is not None:
            current.finished_at = finished_at
        if duration_ms is not None:
            current.duration_ms = duration_ms
        elif current.started_at and current.finished_at:
            current.duration_ms = max(0, int((current.finished_at - current.started_at).total_seconds() * 1000))
        attach_action_message_i18n(current)
        self.repo.update(current)
        return current

    def mark_running(
        self,
        action_id: str,
        *,
        started_at: datetime | None = None,
    ) -> ActionRecord | None:
        return self._update_action(
            action_id,
            status=ActionStatus.running,
            started_at=started_at or datetime.now(),
        )

    def mark_completed(
        self,
        action_id: str,
        *,
        message_params: dict[str, str] | None = None,
        finished_at: datetime | None = None,
        duration_ms: int | None = None,
    ) -> ActionRecord | None:
        return self._update_action(
            action_id,
            status=ActionStatus.completed,
            error=None,
            message_params=message_params,
            finished_at=finished_at or datetime.now(),
            duration_ms=duration_ms,
        )

    def mark_failed(
        self,
        action_id: str,
        *,
        error: str | None = None,
        message_params: dict[str, str] | None = None,
        finished_at: datetime | None = None,
        duration_ms: int | None = None,
    ) -> ActionRecord | None:
        return self._update_action(
            action_id,
            status=ActionStatus.failed,
            error=error,
            message_params=message_params,
            finished_at=finished_at or datetime.now(),
            duration_ms=duration_ms,
        )

    def mark_cancelled(
        self,
        action_id: str,
        *,
        finished_at: datetime | None = None,
    ) -> ActionRecord | None:
        return self._update_action(
            action_id,
            status=ActionStatus.cancelled,
            finished_at=finished_at or datetime.now(),
        )

    def mark_skipped(
        self,
        action_id: str,
        *,
        error: str | None = None,
        message_params: dict[str, str] | None = None,
        finished_at: datetime | None = None,
    ) -> ActionRecord | None:
        return self._update_action(
            action_id,
            status=ActionStatus.skipped,
            error=error,
            message_params=message_params,
            finished_at=finished_at or datetime.now(),
            duration_ms=0,
        )

    def _match_action(
        self,
        action: ActionRecord,
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
    ) -> bool:
        if media_id and action.media_id != media_id:
            return False
        if task_id and action.task_id != task_id:
            return False
        if subscription_id and action.subscription_id != subscription_id:
            return False
        if target_type and action.target_type != target_type:
            return False
        if target_id and action.target_id != target_id:
            return False
        if kinds and action.kind not in kinds:
            return False
        if statuses and action.status not in statuses:
            return False
        if action_names and action.action_name not in action_names:
            return False
        if triggers and action.trigger not in triggers:
            return False
        if sources and action.source not in sources:
            return False
        if correlation_id and action.correlation_id != correlation_id:
            return False
        if keyword and keyword.lower() not in _action_search_blob(action):
            return False
        return True

    def list_actions(
        self,
        limit: int = 50,
        offset: int = 0,
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
        if keyword:
            keyword = keyword.strip()
        if not keyword:
            keyword = None
        total, items = self.repo.list_filtered_page(
            limit=limit,
            offset=offset,
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
        return total, [attach_action_message_i18n(action) for action in items]

    def list_filter_options(
        self,
        media_id: MediaID | None = None,
        task_id: str | None = None,
        subscription_id: str | None = None,
        target_type: ActionTargetType | None = None,
        target_id: str | None = None,
        keyword: str | None = None,
        correlation_id: str | None = None,
    ) -> Mapping[str, list[str]]:
        distinct_values = self.repo.list_distinct_filter_values(
            media_id=media_id,
            task_id=task_id,
            subscription_id=subscription_id,
            target_type=target_type,
            target_id=target_id,
            keyword=keyword,
            correlation_id=correlation_id,
        )
        return {
            "kinds": list(ACTION_FILTER_KINDS),
            "statuses": list(ACTION_FILTER_STATUSES),
            "action_names": distinct_values["action_names"],
            "triggers": list(ACTION_FILTER_TRIGGERS),
            "sources": distinct_values["sources"],
        }

    def list_latest_actions_by_target(
        self,
        *,
        target_type: ActionTargetType,
        target_ids: list[str],
    ) -> dict[str, ActionRecord]:
        if not target_ids:
            return {}
        target_id_set = set(target_ids)
        latest: dict[str, ActionRecord] = {}
        actions = [
            attach_action_message_i18n(action)
            for action in self.repo.list_by_target_ids(target_type=target_type, target_ids=target_ids)
        ]
        for action in actions:
            if action.target_type != target_type or action.target_id not in target_id_set:
                continue
            target_id = action.target_id or ""
            existing = latest[target_id] if target_id in latest else None
            current_sort_key = action.started_at or action.ts
            existing_sort_key = (existing.started_at or existing.ts) if existing else None
            if existing is None or current_sort_key > existing_sort_key:
                latest[target_id] = action
        return latest

    def fail_active_actions(
        self,
        *,
        error: str,
        kinds: list[ActionKind] | None = None,
        sources: list[ActionSource] | None = None,
        action_names: list[str] | None = None,
        exclude_ids: set[str] | None = None,
        exclude_id_prefixes: tuple[str, ...] = (),
    ) -> int:
        exclude_ids = exclude_ids or set()
        actions = self.repo.list_filtered(
            kinds=kinds,
            sources=sources,
            action_names=action_names,
            statuses=[ActionStatus.queued, ActionStatus.running],
        )
        updated = 0
        for action in actions:
            if action.id in exclude_ids:
                continue
            if any(action.id.startswith(prefix) for prefix in exclude_id_prefixes):
                continue
            if self.mark_failed(action.id, error=error):
                updated += 1
        return updated

    def list_actions_page_by_target(
        self,
        *,
        target_type: ActionTargetType,
        target_id: str,
        limit: int,
        offset: int,
    ) -> tuple[int, list[ActionRecord]]:
        total, items = self.repo.list_page_by_target(
            target_type=target_type,
            target_id=target_id,
            limit=limit,
            offset=offset,
        )
        return total, [attach_action_message_i18n(action) for action in items]

    def get_action(self, action_id: str) -> ActionRecord | None:
        action = self.repo.get_by_id(action_id)
        return attach_action_message_i18n(action) if action else None

    def cleanup_retention(self) -> None:
        removed = self.repo.prune_to_limit(self.max_actions)
        if removed > 0:
            logger.info("Action retention cleanup removed %d records", removed)
action_service = ActionService()
