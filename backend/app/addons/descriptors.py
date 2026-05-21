from __future__ import annotations

from app.addons.registry import AddonDescriptor, AddonJobSpec, AddonRegistry
from app.schemas.config import AddonsConfig
from app.services.application.workflows.danmu import danmu_application_service
from app.services.application.workflows.notifications import notification_application_service
from app.services.platform.auth_provider_service import auth_provider_service
from app.services.platform.notification_channel_service import notification_channel_service


def _auth_enabled(config: AddonsConfig) -> bool:
    return config.auth.enabled and any(auth_provider_service.supports(provider.type) for provider in config.auth.providers)


def _notifications_enabled(config: AddonsConfig) -> bool:
    return config.notifications.enabled and any(
        notification_channel_service.supports(channel.type) for channel in config.notifications.channels
    )


def _notification_event_patterns() -> list[str]:
    return ["*"]


def _danmu_enabled(config: AddonsConfig) -> bool:
    return config.danmu.enabled


def _danmu_event_patterns() -> list[str]:
    return ["media.import.completed"]


def _danmu_jobs() -> list[AddonJobSpec]:
    config = danmu_application_service.config()
    if not config.enabled or not config.backfill_enabled:
        return []
    return [
        AddonJobSpec(
            id="danmu.backfill",
            name="Danmu Backfill",
            trigger="interval",
            interval_seconds=config.backfill_interval_seconds,
            max_instances=1,
            handler=danmu_application_service.run_backfill,
        )
    ]


def register_addons(registry: AddonRegistry) -> None:
    notification_channel_service.discover_and_register()
    registry.register(
        AddonDescriptor(
            name="auth",
            display_name="Auth",
            is_enabled=_auth_enabled,
        )
    )
    registry.register(
        AddonDescriptor(
            name="notifications",
            display_name="Notifications",
            is_enabled=_notifications_enabled,
            subscribed_event_patterns=_notification_event_patterns,
            event_handler=notification_application_service.handle_event,
        )
    )
    registry.register(
        AddonDescriptor(
            name="danmu",
            display_name="Danmu",
            is_enabled=_danmu_enabled,
            subscribed_event_patterns=_danmu_event_patterns,
            scheduled_jobs=_danmu_jobs,
            event_handler=danmu_application_service.handle_event,
        )
    )
