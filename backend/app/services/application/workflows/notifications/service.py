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
from app.schemas.domain.addon_events import AddonRunEventMeta
from app.schemas.domain.event import Event, EventType
from app.schemas.domain.event_catalog import is_manual_notification_suppressed
from app.services.application.events.consumer import event_matches_patterns
from app.services.audit.action_catalog import ACTION_NAME_NOTIFICATION_SEND
from app.services.audit.action_service import action_service
from app.services.audit.event_service import event_service
from app.services.config.settings_service import settings_service
from app.services.platform.notification_channel_service import notification_channel_service
from app.services.application.workflows.notifications.import_summary import import_notification_summary_service

logger = logging.getLogger("app.application.notifications")


class NotificationApplicationService:
    async def handle_event(self, event: Event) -> None:
        channels = settings_service.get_addons_config().notifications.channels
        eligible_channels = [channel for channel in channels if self._should_send(channel, event, apply_level_filter=False)]
        if eligible_channels and event.type == EventType.MEDIA_IMPORT_COMPLETED and event.meta:
            event = await import_notification_summary_service.build_notification(event)
        for channel in eligible_channels:
            if channel.levels and event.level.value not in channel.levels:
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
                continue
            action_service.mark_completed(action.id)

    def _should_send(self, channel: NotificationChannelConfig, event: Event, *, apply_level_filter: bool = True) -> bool:
        # Generic execution receipts belong to audit history, not user notifications.
        if event.type == EventType.ADDON_RUN_COMPLETED:
            return False
        if event.type in {
            EventType.MEDIA_SERVER_SYNC_COMPLETED, EventType.MEDIA_SERVER_SYNC_FAILED,
            EventType.DANMU_GENERATE_COMPLETED, EventType.DANMU_GENERATE_FAILED,
        }:
            if self._is_import_event(event.correlation_id):
                return False
        if event.type == EventType.ADDON_RUN_FAILED and event.meta:
            if self._is_import_event(AddonRunEventMeta.model_validate_json(event.meta).trigger_event_id):
                return False
        if not channel.enabled:
            return False
        if not notification_channel_service.supports(channel.type):
            return False
        if not notification_channel_service.get_channel(channel.type).is_configured(channel):
            return False
        if not event_matches_patterns(event.type, channel.event_patterns):
            return False
        if is_manual_notification_suppressed(event):
            return False
        if apply_level_filter and channel.levels and event.level.value not in channel.levels:
            return False
        return True

    @staticmethod
    def _is_import_event(event_id: str | None) -> bool:
        if not event_id:
            return False
        parent = event_service.get_event(event_id)
        # Manual imports remain covered: their entire user-triggered chain is
        # intentionally silent, including automatically executed postprocessing.
        return parent is not None and parent.type == EventType.MEDIA_IMPORT_COMPLETED

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
