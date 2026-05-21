from __future__ import annotations

import logging
from datetime import datetime

from app.core.action_context import action_context
from app.schemas.config import NotificationChannelConfig
from app.schemas.domain.action import (
    ActionActor,
    ActionKind,
    ActionRecord,
    ActionSource,
    ActionStatus,
    ActionTargetType,
    ActionTrigger,
)
from app.schemas.domain.action_meta import NotificationSendQueuedActionMeta
from app.schemas.domain.event import Event
from app.services.application.events.consumer import event_matches_patterns
from app.services.audit.action_catalog import ACTION_NAME_NOTIFICATION_SEND
from app.services.audit.action_service import action_service
from app.services.config.settings_service import settings_service
from app.services.domain.alerts.workflow_alerts import raise_notification_alert, resolve_notification_alert
from app.services.platform.notification_channel_service import notification_channel_service

logger = logging.getLogger("app.application.notifications")


class NotificationApplicationService:
    async def handle_event(self, event: Event) -> None:
        channels = settings_service.get_addons_config().notifications.channels
        for channel in channels:
            if not self._should_send(channel, event):
                continue
            action = self._create_notify_action(channel, event)
            action_service.mark_running(action.id, started_at=datetime.now())
            try:
                with action_context(action.id):
                    await notification_channel_service.get_channel(channel.type).send(channel, event)
            except Exception as exc:
                logger.exception(
                    "Notification send failed for channel=%s event=%s",
                    channel.name or channel.id,
                    event.type,
                )
                action_service.mark_failed(action.id, error=str(exc))
                raise_notification_alert(
                    channel_id=channel.id,
                    channel_name=channel.name,
                    channel_type=channel.type,
                    event_type=event.type.value,
                    event_id=event.id,
                    media=event.media,
                    media_id=event.media_id,
                    task_id=event.task_id,
                    action_id=action.id,
                    error=str(exc),
                )
                continue
            action_service.mark_completed(action.id)
            resolve_notification_alert(channel.id)

    def _should_send(self, channel: NotificationChannelConfig, event: Event) -> bool:
        if not channel.enabled:
            return False
        if not notification_channel_service.supports(channel.type):
            return False
        if not notification_channel_service.get_channel(channel.type).is_configured(channel):
            return False
        if not event_matches_patterns(event.type, channel.event_patterns):
            return False
        if channel.levels and event.level.value not in channel.levels:
            return False
        return True

    def _create_notify_action(self, channel: NotificationChannelConfig, event: Event) -> ActionRecord:
        return action_service.create_action(
            kind=ActionKind.addon,
            action_name=ACTION_NAME_NOTIFICATION_SEND,
            status=ActionStatus.queued,
            actor=ActionActor.system,
            trigger=ActionTrigger.event,
            source=ActionSource.addon,
            target_type=ActionTargetType.notification_channel,
            target_id=channel.id,
            media_id=event.media_id,
            task_id=event.task_id,
            subscription_id=event.subscription_id,
            correlation_id=event.correlation_id,
            meta=NotificationSendQueuedActionMeta(
                channel_type=channel.type,
                channel_name=channel.name,
                trigger_event_type=event.type,
                trigger_event_id=event.id,
            ),
        )


notification_application_service = NotificationApplicationService()
