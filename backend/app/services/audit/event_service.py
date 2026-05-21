from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Mapping

from app.core.action_context import get_current_action_id
from app.db.repositories.event_repository import EventRepository
from app.db.sql.serialization import to_jsonable
from app.schemas.media_id import MediaID
from app.schemas.domain.event import Event, EventCreate, EventLevel, EventSource, EventType, MediaEventCreate
from app.services.application.events.dispatch import event_dispatch_service
from app.services.audit.event_message_i18n import attach_event_message_i18n, event_message_key, event_message_params
from app.services.audit.search_text_support import build_event_search_text
from pydantic import BaseModel

logger = logging.getLogger("app.services.event")
NON_BUSINESS_EVENT_PREFIXES = (
    "command.",
    "addon.run.",
    "notification.",
    "scheduler.",
)


def _event_search_blob(ev: Event) -> str:
    return build_event_search_text(ev)


def _normalize_event_meta(meta: BaseModel | None) -> str:
    if meta is None:
        return ""
    return json.dumps(to_jsonable(meta), ensure_ascii=False, sort_keys=True)


def _merge_message_params(event: EventCreate, meta: BaseModel | None) -> dict[str, str]:
    params = event_message_params(event, meta)
    params.update(event.message_params or {})
    return params


class EventService:
    def __init__(self) -> None:
        self.repo = EventRepository()
        self.max_events = 20000
        self.max_age_days = 30

    def is_business_event(self, event_type: str) -> bool:
        return not any(event_type.startswith(prefix) for prefix in NON_BUSINESS_EVENT_PREFIXES)

    def _persist_event(self, event: Event) -> Event:
        self.repo.insert(event)
        if self.is_business_event(event.type):
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                asyncio.run(event_dispatch_service.enqueue_event(event.id, event.type))
            else:
                loop.create_task(event_dispatch_service.enqueue_event(event.id, event.type))
        return event

    def emit(
        self,
        event: EventCreate,
        meta: BaseModel | None = None,
    ) -> Event | None:
        # Internal note.
        ev = Event(
            type=event.type,
            message_key=event.message_key or event_message_key(event.type),
            message_params=_merge_message_params(event, meta),
            level=event.level,
            media=None,
            task_id=event.task_id,
            subscription_id=event.subscription_id,
            actor=event.actor,
            source=event.source,
            addon_id=event.addon_id,
            addon_name=event.addon_name,
            entities=list(event.entities),
            meta=_normalize_event_meta(meta),
            correlation_id=event.correlation_id,
            action_id=event.action_id or get_current_action_id(),
        )
        return self._persist_event(ev)

    def emit_media(
        self,
        event: MediaEventCreate,
        meta: BaseModel | None = None,
    ) -> Event | None:
        media = event.media
        if not media.title or media.year <= 0:
            raise ValueError("media_title and media_year must be valid when media_id is provided")
        ev = Event(
            type=event.type,
            message_key=event.message_key or event_message_key(event.type),
            message_params=_merge_message_params(event, meta),
            level=event.level,
            media=media,
            task_id=event.task_id,
            subscription_id=event.subscription_id,
            actor=event.actor,
            source=event.source,
            addon_id=event.addon_id,
            addon_name=event.addon_name,
            entities=list(event.entities),
            meta=_normalize_event_meta(meta),
            correlation_id=event.correlation_id,
            action_id=event.action_id or get_current_action_id(),
        )
        return self._persist_event(ev)

    def _match_event(
        self,
        ev: Event,
        media_id: MediaID | None = None,
        season_number: int | None = None,
        task_id: str | None = None,
        subscription_id: str | None = None,
        levels: list[EventLevel] | None = None,
        types: list[EventType] | None = None,
        keyword: str | None = None,
        sources: list[EventSource] | None = None,
        addon_id: str | None = None,
        action_id: str | None = None,
    ) -> bool:
        if media_id and ev.media_id != media_id:
            return False
        if season_number is not None and (ev.media is None or ev.media.season_number != season_number):
            return False
        if task_id and ev.task_id != task_id:
            return False
        if subscription_id and ev.subscription_id != subscription_id:
            return False
        if levels and ev.level not in levels:
            return False
        if types and ev.type not in types:
            return False
        if sources and ev.source not in sources:
            return False
        if addon_id and ev.addon_id != addon_id:
            return False
        if action_id and ev.action_id != action_id:
            return False
        if keyword:
            kw = keyword.lower()
            if kw not in _event_search_blob(ev):
                return False
        return True

    def list_events(
        self,
        limit: int = 50,
        offset: int = 0,
        media_id: MediaID | None = None,
        season_number: int | None = None,
        task_id: str | None = None,
        subscription_id: str | None = None,
        levels: list[EventLevel] | None = None,
        types: list[EventType] | None = None,
        keyword: str | None = None,
        sources: list[EventSource] | None = None,
        addon_id: str | None = None,
        action_id: str | None = None,
    ) -> tuple[int, list[Event]]:
        if keyword:
            keyword = keyword.strip()
        if not keyword:
            keyword = None

        total, events = self.repo.list_filtered_page(
            limit=limit,
            offset=offset,
            media_id=media_id,
            media_season_number=season_number,
            task_id=task_id,
            subscription_id=subscription_id,
            levels=levels,
            types=types,
            keyword=keyword,
            sources=sources,
            addon_id=addon_id,
            action_id=action_id,
            excluded_type_prefixes=NON_BUSINESS_EVENT_PREFIXES,
        )
        return total, [attach_event_message_i18n(event) for event in events]

    def list_media_events(self, media_id: MediaID, limit: int = 50, season_number: int | None = None) -> list[Event]:
        events = [
            event
            for event in self.repo.list_by_media_id(media_id, limit=None, season_number=season_number)
            if self.is_business_event(event.type)
        ]
        events.sort(key=lambda event: event.ts, reverse=True)
        items = events[:limit] if limit else events
        return [attach_event_message_i18n(event) for event in items]

    def list_filter_options(
        self,
        media_id: MediaID | None = None,
        season_number: int | None = None,
        task_id: str | None = None,
        subscription_id: str | None = None,
        action_id: str | None = None,
        keyword: str | None = None,
    ) -> Mapping[str, list[str]]:
        events = self.repo.list_filtered(
            media_id=media_id,
            media_season_number=season_number,
            task_id=task_id,
            subscription_id=subscription_id,
            action_id=action_id,
        )

        events = [
            event for event in events if self._match_event(
                event,
                media_id=media_id,
                season_number=season_number,
                task_id=task_id,
                subscription_id=subscription_id,
                action_id=action_id,
                keyword=keyword,
            )
            and self.is_business_event(event.type)
        ]

        levels = sorted({event.level.value if event.level else "" for event in events if event.level})
        types = sorted({event.type for event in events if event.type})
        sources = sorted({event.source.value if event.source else "" for event in events if event.source})
        return {
            "levels": levels,
            "types": types,
            "sources": sources,
        }

    def get_event(self, event_id: str) -> Event | None:
        event = self.repo.get_by_id(event_id)
        return attach_event_message_i18n(event) if event else None

    def cleanup_retention(self) -> None:
        removed = self.repo.prune_to_limit(self.max_events)
        if removed > 0:
            logger.info("Event retention cleanup removed %d records", removed)
event_service = EventService()
