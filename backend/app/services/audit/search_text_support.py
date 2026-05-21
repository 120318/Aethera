from __future__ import annotations

from app.schemas.domain.action import ActionRecord
from app.schemas.domain.event import Event
from app.services.i18n.message_renderer import render_message


SEARCH_LOCALES = ("zh-CN", "en-US")


def _rendered_messages(message_key: str | None, params: dict[str, str]) -> list[str]:
    if not message_key:
        return []
    return [render_message(message_key, params, locale=locale) for locale in SEARCH_LOCALES]


def build_action_search_text(action: ActionRecord) -> str:
    media = action.media
    parts: list[str] = [
        action.kind.value if action.kind else "",
        action.action_name or "",
        action.status.value if action.status else "",
        action.actor.value if action.actor else "",
        action.trigger.value if action.trigger else "",
        action.source or "",
        action.target_type or "",
        action.target_id or "",
        str(action.media_id) if action.media_id else "",
        media.title if media else "",
        str(media.year) if media else "",
        action.task_id or "",
        action.subscription_id or "",
        action.correlation_id or "",
        action.message_key or "",
        " ".join(str(value) for value in action.message_params.values()),
        *_rendered_messages(action.message_key, action.message_params),
        action.error or "",
    ]
    if action.meta:
        parts.append(action.meta)
    return " ".join(part for part in parts if part).lower()


def build_event_search_text(event: Event) -> str:
    media = event.media
    parts: list[str] = [
        event.type or "",
        event.message_key or "",
        " ".join(str(value) for value in event.message_params.values()),
        *_rendered_messages(event.message_key, event.message_params),
        str(media.media_id) if media else "",
        media.title if media else "",
        str(media.year) if media else "",
        event.task_id or "",
        event.subscription_id or "",
        event.addon_id or "",
        event.addon_name or "",
        event.correlation_id or "",
        event.action_id or "",
        event.actor.value if event.actor else "",
        event.source.value if event.source else "",
        event.level.value if event.level else "",
    ]
    for ent in event.entities or []:
        parts.append(ent.type or "")
        parts.append(ent.id or "")
    if event.meta:
        parts.append(event.meta)
    return " ".join(part for part in parts if part).lower()
