from __future__ import annotations

import importlib
import os
import pkgutil
from abc import ABC, abstractmethod

from app.core.feature_flags import telegram_notifications_enabled
from app.schemas.exception.exceptions import ConfigurationException
from app.schemas.config import NotificationChannelConfig
from app.schemas.domain.event import Event


class BaseNotificationChannel(ABC):
    @property
    @abstractmethod
    def channel_type(self) -> str:
        raise NotImplementedError

    @abstractmethod
    async def send(
        self,
        config: NotificationChannelConfig,
        event: Event,
    ) -> None:
        raise NotImplementedError

    def is_configured(self, config: NotificationChannelConfig) -> bool:
        return True


class NotificationChannelService:
    def __init__(self) -> None:
        self._channels: dict[str, BaseNotificationChannel] = {}

    def register(self, channel: BaseNotificationChannel) -> None:
        self._channels[channel.channel_type] = channel

    def discover_and_register(self) -> None:
        from app.services.integration.notifications import channels as notification_channels_pkg

        package_path = os.path.dirname(notification_channels_pkg.__file__)
        for _, module_name, is_pkg in pkgutil.iter_modules([package_path]):
            if not is_pkg:
                continue
            if module_name == "telegram" and not telegram_notifications_enabled():
                continue
            importlib.import_module(f"app.services.integration.notifications.channels.{module_name}")

    def get_channel(self, channel_type: str) -> BaseNotificationChannel:
        if channel_type not in self._channels:
            raise ConfigurationException("backendErrors.config.notificationChannelTypeUnsupported", params={"type": channel_type})
        return self._channels[channel_type]

    def supports(self, channel_type: str) -> bool:
        return channel_type in self._channels


notification_channel_service = NotificationChannelService()
