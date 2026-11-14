from __future__ import annotations

from datetime import datetime, timedelta

from app.schemas.domain.addon_events import MediaImportCompletedEventMeta
from app.schemas.domain.command import CommandRecord, CommandStatus
from app.schemas.domain.event import Event, EventType
from app.schemas.persistence.event_dispatch import EventDispatchDeferred, EventDispatchRecord, EventDispatchStatus
from app.schemas.runtime.import_notification import ImportNotificationMeta, ImportNotificationStep, ImportStepStatus
from app.services.application.commands.service import command_service
from app.services.application.events.dispatch import event_dispatch_service
from app.services.application.workflows.media_server_sync.config import media_server_sync_config
from app.services.audit.event_service import event_service
from app.services.config.settings_service import settings_service


IMPORT_NOTIFICATION_TIMEOUT = timedelta(minutes=10)
TERMINAL_COMMAND_STATUSES = {CommandStatus.SUCCEEDED, CommandStatus.FAILED, CommandStatus.CANCELLED}
TERMINAL_DISPATCH_STATUSES = {EventDispatchStatus.SUCCEEDED, EventDispatchStatus.FAILED}


class ImportNotificationSummaryService:
    async def build_notification(self, event: Event) -> Event:
        meta = MediaImportCompletedEventMeta.model_validate_json(event.meta)
        dispatches = await event_dispatch_service.list_event_dispatches(event.id)
        dispatch_by_consumer = {item.consumer_name: item for item in dispatches}
        commands = await command_service.list_addon_commands_for_event(event.id)
        timed_out = datetime.now() - event.ts >= IMPORT_NOTIFICATION_TIMEOUT
        steps: list[ImportNotificationStep] = []

        sync_events = [
            item for item in event_service.list_correlated_events(event.id)
            if item.type in {EventType.MEDIA_SERVER_SYNC_COMPLETED, EventType.MEDIA_SERVER_SYNC_FAILED}
        ]
        sync_enabled = media_server_sync_config.resolve_server_for_directory_id(meta.directory_id) is not None
        if sync_events or sync_enabled:
            steps.append(self._sync_step(dispatch_by_consumer.get("media_server_sync"), sync_events, timed_out))

        config = settings_service.get_addons_config()
        configured_addons = {
            "danmu": config.danmu.enabled and meta.directory_id in config.danmu.directory_ids,
            "subtitles": config.subtitles.enabled and config.subtitles.auto_fill_enabled,
        }
        for name, enabled in configured_addons.items():
            addon_commands = [command for command in commands if command.payload.addon_id == name]
            dispatch = dispatch_by_consumer.get(name)
            if addon_commands or (enabled and dispatch is not None):
                steps.append(self._addon_step(name, dispatch, addon_commands, timed_out))

        summary = ImportNotificationMeta(**meta.model_dump(), postprocessing=steps)
        return event.model_copy(update={"meta": summary.model_dump_json()})

    @staticmethod
    def _pending_step(name: str, timed_out: bool) -> ImportNotificationStep:
        if not timed_out:
            raise EventDispatchDeferred()
        return ImportNotificationStep(name=name, status=ImportStepStatus.TIMED_OUT)

    def _sync_step(
        self,
        dispatch: EventDispatchRecord | None,
        events: list[Event],
        timed_out: bool,
    ) -> ImportNotificationStep:
        # A result event can be emitted before its handler has fully returned.
        if dispatch is not None and dispatch.status not in TERMINAL_DISPATCH_STATUSES:
            return self._pending_step("media_server_sync", timed_out)
        if dispatch is not None and dispatch.status == EventDispatchStatus.FAILED:
            return ImportNotificationStep(name="media_server_sync", status=ImportStepStatus.FAILED)
        if events:
            failed = any(item.type == EventType.MEDIA_SERVER_SYNC_FAILED for item in events)
            return ImportNotificationStep(
                name="media_server_sync",
                status=ImportStepStatus.FAILED if failed else ImportStepStatus.COMPLETED,
            )
        if dispatch is None:
            return self._pending_step("media_server_sync", timed_out)
        return ImportNotificationStep(name="media_server_sync", status=ImportStepStatus.SKIPPED)

    def _addon_step(
        self,
        name: str,
        dispatch: EventDispatchRecord | None,
        commands: list[CommandRecord],
        timed_out: bool,
    ) -> ImportNotificationStep:
        if dispatch is not None and dispatch.status not in TERMINAL_DISPATCH_STATUSES:
            return self._pending_step(name, timed_out)
        if any(command.status not in TERMINAL_COMMAND_STATUSES for command in commands):
            return self._pending_step(name, timed_out)
        completed = sum(command.result.result_count for command in commands if command.result)
        skipped = sum(command.result.skipped_count for command in commands if command.result)
        failed = sum(
            max(command.result.failed_count if command.result else 0, int(command.status != CommandStatus.SUCCEEDED))
            for command in commands
        )
        if dispatch is not None and dispatch.status == EventDispatchStatus.FAILED:
            failed += 1
        status = (
            ImportStepStatus.PARTIAL if completed and failed else
            ImportStepStatus.FAILED if failed else
            ImportStepStatus.COMPLETED if completed else
            ImportStepStatus.SKIPPED
        )
        return ImportNotificationStep(
            name=name,
            status=status,
            completed_count=completed,
            skipped_count=skipped,
            failed_count=failed,
        )


import_notification_summary_service = ImportNotificationSummaryService()
