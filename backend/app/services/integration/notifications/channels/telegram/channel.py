from __future__ import annotations

import json

from app.schemas.config import NotificationChannelConfig, TelegramNotificationChannelConfig
from app.schemas.domain.event import Event
from app.services.i18n.message_renderer import render_message
from app.services.platform.notification_channel_service import BaseNotificationChannel

from .client import TelegramClient


def _escape_markdown(value: str) -> str:
    escaped = value or ""
    for char in "\\_[]()~`>#+-=|{}.!":
        escaped = escaped.replace(char, f"\\{char}")
    return escaped


def _build_entity_summary(event: Event) -> str:
    parts: list[str] = []
    if event.media_id:
        parts.append(f"media: `{_escape_markdown(str(event.media_id))}`")
    if event.task_id:
        parts.append(f"task: `{_escape_markdown(event.task_id)}`")
    if event.subscription_id:
        parts.append(f"subscription: `{_escape_markdown(event.subscription_id)}`")
    if event.addon_name:
        parts.append(f"addon: `{_escape_markdown(event.addon_name)}`")
    return "\n".join(parts)


def _build_meta_summary(event: Event) -> str:
    if not event.meta:
        return ""
    try:
        meta_payload = json.loads(event.meta)
    except json.JSONDecodeError:
        return f"meta: `{_escape_markdown(event.meta)}`"
    if type(meta_payload) is not dict:
        return f"meta: `{_escape_markdown(str(meta_payload))}`"
    keys = sorted(meta_payload.keys())[:6]
    pairs = [f"{_escape_markdown(str(key))}: `{_escape_markdown(str(meta_payload[key]))}`" for key in keys]
    return "\n".join(pairs)


class TelegramNotificationChannel(BaseNotificationChannel):
    def __init__(self) -> None:
        self._client = TelegramClient()

    @property
    def channel_type(self) -> str:
        return "telegram"

    def is_configured(self, config: NotificationChannelConfig) -> bool:
        telegram_config = TelegramNotificationChannelConfig.model_validate(config)
        return bool(telegram_config.bot_token and telegram_config.chat_id)

    async def send(self, config: NotificationChannelConfig, event: Event) -> None:
        telegram_config = TelegramNotificationChannelConfig.model_validate(config)
        await self._client.send_message(
            bot_token=telegram_config.bot_token,
            chat_id=telegram_config.chat_id,
            text=self._format_message(event),
        )

    def _format_message(self, event: Event) -> str:
        sections = [
            f"*{_escape_markdown(event.level.value.upper())}* · `{_escape_markdown(event.type)}`",
            _escape_markdown(render_message(event.message_key, event.message_params)),
        ]
        entity_summary = _build_entity_summary(event)
        if entity_summary:
            sections.append(entity_summary)
        meta_summary = _build_meta_summary(event)
        if meta_summary:
            sections.append(meta_summary)
        sections.append(f"time: `{_escape_markdown(event.ts.isoformat())}`")
        return "\n\n".join(section for section in sections if section)
