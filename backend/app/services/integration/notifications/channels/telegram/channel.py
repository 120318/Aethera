from __future__ import annotations

from app.schemas.config import NotificationChannelConfig, TelegramNotificationChannelConfig
from app.schemas.domain.event import Event
from app.services.config.settings_service import settings_service
from app.services.platform.notification_channel_service import BaseNotificationChannel

from .client import TelegramClient
from .renderer import format_telegram_event


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
        system_config = settings_service.get_base_system_config()
        await self._client.send_message(
            bot_token=telegram_config.bot_token,
            chat_id=telegram_config.chat_id,
            text=format_telegram_event(
                event,
                locale=system_config.locale,
                public_base_url=system_config.public_base_url,
            ),
        )
