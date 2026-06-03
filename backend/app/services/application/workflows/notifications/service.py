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
from app.schemas.domain.event import Event, EventCreate, EventLevel, EventSource, EventType
from app.services.application.events.consumer import event_matches_patterns
from app.services.audit.action_catalog import ACTION_NAME_NOTIFICATION_SEND
from app.services.audit.action_service import action_service
from app.services.audit.event_service import event_service
from app.services.config.settings_service import settings_service
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
                self._emit_notification_event(
                    channel=channel,
                    trigger_event=event,
                    action_id=action.id,
                    event_type=EventType.NOTIFICATION_FAILED,
                    level=EventLevel.error,
                    reason=str(exc),
                )
                continue
            action_service.mark_completed(action.id)
            self._emit_notification_event(
                channel=channel,
                trigger_event=event,
                action_id=action.id,
                event_type=EventType.NOTIFICATION_SENT,
                level=EventLevel.info,
            )

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

    def _emit_notification_event(
        self,
        *,
        channel: NotificationChannelConfig,
        trigger_event: Event,
        action_id: str,
        event_type: EventType,
        level: EventLevel,
        reason: str = "",
    ) -> None:
        channel_label = channel.name or channel.type
        try:
            event_service.emit(
                EventCreate(
                    type=event_type,
                    level=level,
                    task_id=trigger_event.task_id,
                    subscription_id=trigger_event.subscription_id,
                    source=EventSource.addon,
                    addon_id=channel.id,
                    addon_name="notifications",
                    correlation_id=trigger_event.correlation_id,
                    action_id=action_id,
                    message_params={
                        "channel": channel_label,
                        "channel_type": channel.type,
                        "trigger_event_id": trigger_event.id,
                        "trigger_event_type": trigger_event.type.value,
                        "reason": reason,
                    },
                )
            )
        except Exception:
            logger.exception("Failed to emit notification result event for channel=%s", channel_label)


notification_application_service = NotificationApplicationService()
