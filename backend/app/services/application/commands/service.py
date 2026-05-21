import asyncio
import logging
from datetime import datetime

from app.core.action_context import action_context
from app.db.repositories.command_repository import CommandRepository
from app.schemas.exception import DownloadException
from app.schemas.exception.base import AppException
from app.schemas.media_id import MediaID
from app.schemas.domain.action import ActionActor, ActionKind, ActionName, ActionRecord, ActionSource, ActionStatus, ActionTrigger
from app.schemas.domain.action_meta import CommandQueuedActionMeta
from app.schemas.domain.addon_events import DownloadFailedEventMeta
from app.schemas.domain.command import (
    CommandCreateRequest,
    CommandInitiator,
    CommandRecord,
    CommandResult,
    CommandStatus,
    CommandTargetType,
    CommandType,
)
from app.schemas.domain.event import EventActor, EventEntityRef, EventLevel, EventSource, MediaEventCreate
from app.services.audit.action_service import action_service
from app.services.audit.event_service import event_service
from app.services.application.commands.message_i18n import attach_command_message_i18n
from app.services.application.commands.registry import CommandHandlerRegistry
from app.services.application.commands.setup import create_command_handler_registry
from app.schemas.constants.event_types import EventTypes

logger = logging.getLogger("app.services.command")

class CommandConflictException(Exception):
    pass


class CommandService:
    def __init__(self) -> None:
        self.repo = CommandRepository()
        self._registry: CommandHandlerRegistry | None = None
        self._uniq_key_locks: dict[str, asyncio.Lock] = {}

    def _get_registry(self) -> CommandHandlerRegistry:
        if self._registry is None:
            self._registry = create_command_handler_registry()
        return self._registry

    async def reset_active_commands(self) -> None:
        await self.reset_running_commands()

    async def reset_running_commands(self) -> None:
        running_commands = await self.repo.find_running()
        for command in running_commands:
            command.status = CommandStatus.FAILED
            command.error = "Service restarted and the command was interrupted"
            command.error_key = None
            command.error_params = {}
            command.finished_at = datetime.now()
            attach_command_message_i18n(command)
            await self.repo.update(command, self.repo.cond_id(command.id))
            self._mark_command_failed(command)
        await self.reset_orphaned_active_command_actions()

    async def reset_orphaned_active_command_actions(self) -> None:
        active_commands = await self.repo.find_active()
        active_command_ids = {command.id for command in active_commands}
        reset_count = action_service.fail_active_actions(
            kinds=[ActionKind.command],
            exclude_ids=active_command_ids,
            exclude_id_prefixes=("storage-migration:",),
            error="Command action no longer has an active command",
        )
        if reset_count > 0:
            logger.info("Reset %d orphaned active command actions", reset_count)

    async def create_command(self, body: CommandCreateRequest) -> CommandRecord:
        return await self._submit_command(
            await self._get_registry().build_command(body),
            source=ActionSource.api,
        )

    async def find_active_command_by_uniq_key(self, uniq_key: str) -> CommandRecord | None:
        command = await self.repo.find_active_by_uniq_key(uniq_key)
        return attach_command_message_i18n(command) if command else None

    async def create_command_with_uniq_key(
        self,
        body: CommandCreateRequest,
        *,
        uniq_key: str,
        source: ActionSource,
    ) -> CommandRecord:
        command = await self._get_registry().build_command(body)
        command.uniq_key = uniq_key
        return await self._submit_command(command, source=source)

    async def get_command(self, command_id: str) -> CommandRecord | None:
        command = await self.repo.find_by_id(command_id)
        return attach_command_message_i18n(command) if command else None

    async def cancel_command(self, command_id: str) -> CommandRecord | None:
        command = await self.repo.find_by_id(command_id)
        if not command:
            return None
        if command.status == CommandStatus.RUNNING:
            raise DownloadException("backendErrors.runningCommandCannotCancel")
        if command.status != CommandStatus.QUEUED:
            return attach_command_message_i18n(command)
        now = datetime.now()
        updated = await self.repo.cancel_queued_command(command.id, now.isoformat())
        latest = await self.repo.find_by_id(command_id)
        if not updated:
            if latest and latest.status == CommandStatus.RUNNING:
                raise DownloadException("backendErrors.commandAlreadyStartedCannotCancel")
            return attach_command_message_i18n(latest) if latest else None
        if not latest:
            return None
        attach_command_message_i18n(latest)
        await self.repo.update(latest, self.repo.cond_id(latest.id))
        self._mark_command_cancelled(latest)
        return latest

    async def list_active_commands(
        self,
        target_type: CommandTargetType | None = None,
        target_ids: list[str] | None = None,
        season_number: int | None = None,
        command_types: list[CommandType] | None = None,
    ) -> list[CommandRecord]:
        commands = await self.repo.find_active_filtered(
            target_type=target_type,
            target_ids=target_ids,
            target_season_number=season_number if target_type == CommandTargetType.MEDIA else None,
            command_types=command_types,
        )
        return [attach_command_message_i18n(command) for command in commands]

    async def list_recent_commands(self, limit: int = 20, statuses: list[CommandStatus] | None = None) -> list[CommandRecord]:
        commands = await self.repo.find_recent(limit=limit, statuses=statuses)
        return [attach_command_message_i18n(command) for command in commands]

    async def list_media_active_commands(
        self,
        media_id: MediaID,
        *,
        season_number: int | None = None,
        command_types: list[CommandType] | None = None,
    ) -> list[CommandRecord]:
        commands = await self.repo.find_active_by_media(
            str(media_id),
            target_season_number=season_number if media_id.media_type.value == "tv" and season_number is not None else None,
            command_types=command_types,
        )
        return [attach_command_message_i18n(command) for command in commands]

    @staticmethod
    def _command_matches_media_season(command: CommandRecord, season_number: int) -> bool:
        command_season = CommandService._command_payload_season_number(command)
        return command_season == season_number

    @staticmethod
    def _command_payload_season_number(command: CommandRecord) -> int | None:
        if command.target is not None and command.target.season_number is not None:
            return command.target.season_number
        if command.target_season_number > 0:
            return command.target_season_number
        return None

    async def run_next_queued_command(self) -> bool:
        command = await self.repo.find_next_queued()
        if not command:
            return False
        command.status = CommandStatus.RUNNING
        command.started_at = datetime.now()
        attach_command_message_i18n(command)
        await self.repo.update(command, self.repo.cond_id(command.id))
        command_action = self._mark_command_running(command)

        try:
            with action_context(command_action.id if command_action else None):
                result = await self._get_registry().execute(command)
            current = await self.repo.find_by_id(command.id)
            if current and current.status == CommandStatus.CANCELLED:
                return True
            command.status = CommandStatus.SUCCEEDED
            command.result = result
            command.error = None
            command.finished_at = datetime.now()
            attach_command_message_i18n(command)
            await self.repo.update(command, self.repo.cond_id(command.id))
            self._mark_command_completed(command)
        except AppException as exc:
            current = await self.repo.find_by_id(command.id)
            if current and current.status == CommandStatus.CANCELLED:
                return True
            logger.exception("Command %s failed: %s", command.id, exc)
            command.status = CommandStatus.FAILED
            command.error = None
            command.error_key = exc.message_key
            command.error_params = exc.params
            command.finished_at = datetime.now()
            attach_command_message_i18n(command)
            await self.repo.update(command, self.repo.cond_id(command.id))
            self._mark_command_failed(command)
            self._emit_command_failed_event(command)
        except (RuntimeError, ValueError) as exc:
            current = await self.repo.find_by_id(command.id)
            if current and current.status == CommandStatus.CANCELLED:
                return True
            logger.exception("Command %s failed: %s", command.id, exc)
            command.status = CommandStatus.FAILED
            command.error = str(exc)
            command.error_key = None
            command.error_params = {}
            command.finished_at = datetime.now()
            attach_command_message_i18n(command)
            await self.repo.update(command, self.repo.cond_id(command.id))
            self._mark_command_failed(command)
            self._emit_command_failed_event(command)

        return True

    async def _submit_command(self, command: CommandRecord, source: ActionSource) -> CommandRecord:
        if not command.uniq_key:
            attach_command_message_i18n(command)
            await self.repo.insert(command)
            self._create_command_action(command, source=source)
            return attach_command_message_i18n(command)

        lock = self._uniq_key_locks.setdefault(command.uniq_key, asyncio.Lock())
        async with lock:
            existing = await self.repo.find_active_by_uniq_key(command.uniq_key)
            if existing:
                logger.info(
                    "Reusing active command instead of enqueueing duplicate: type=%s uniq_key=%s existing=%s",
                    command.type.value,
                    command.uniq_key,
                    existing.id,
                )
                return attach_command_message_i18n(existing)
            attach_command_message_i18n(command)
            await self.repo.insert(command)
            self._create_command_action(command, source=source)
            return attach_command_message_i18n(command)

    def _create_command_action(self, command: CommandRecord, source: ActionSource) -> ActionRecord:
        actor = ActionActor.user if command.initiator == CommandInitiator.MANUAL else ActionActor.system
        if command.initiator == CommandInitiator.MANUAL:
            trigger = ActionTrigger.manual
        elif command.initiator == CommandInitiator.SCHEDULER:
            trigger = ActionTrigger.scheduler
        else:
            trigger = ActionTrigger.system
        action_context_data = self._get_registry().resolve_action_context(command)
        return action_service.create_action(
            kind=ActionKind.command,
            action_name=ActionName(command.type.value),
            status=ActionStatus.queued,
            actor=actor,
            trigger=trigger,
            source=source,
            target_type=command.target_type,
            target_id=command.target_id,
            media_id=command.media_id or action_context_data.media_id,
            task_id=action_context_data.task_id or (command.result.task_id if command.result else None),
            correlation_id=command.id,
            error=command.error,
            meta=CommandQueuedActionMeta(
                command_id=command.id,
                initiator=command.initiator.value,
                target_label=command.target_label,
            ),
            action_id=command.id,
        )

    def _mark_command_running(self, command: CommandRecord) -> ActionRecord | None:
        return action_service.mark_running(
            command.id,
            started_at=command.started_at or datetime.now(),
        )

    def _mark_command_completed(self, command: CommandRecord) -> ActionRecord | None:
        duration_ms = None
        if command.started_at and command.finished_at:
            duration_ms = max(0, int((command.finished_at - command.started_at).total_seconds() * 1000))
        return action_service.mark_completed(
            command.id,
            message_params=command.message_params,
            finished_at=command.finished_at or datetime.now(),
            duration_ms=duration_ms,
        )

    def _mark_command_failed(self, command: CommandRecord) -> ActionRecord | None:
        duration_ms = None
        if command.started_at and command.finished_at:
            duration_ms = max(0, int((command.finished_at - command.started_at).total_seconds() * 1000))
        return action_service.mark_failed(
            command.id,
            error=command.error,
            message_params=command.message_params,
            finished_at=command.finished_at or datetime.now(),
            duration_ms=duration_ms,
        )

    def _mark_command_cancelled(self, command: CommandRecord) -> ActionRecord | None:
        return action_service.mark_cancelled(
            command.id,
            finished_at=command.finished_at or datetime.now(),
        )

    def _emit_command_failed_event(self, command: CommandRecord) -> None:
        if command.type != CommandType.TASK_CREATE:
            return
        payload = command.payload
        event_service.emit_media(
            MediaEventCreate(
                type=EventTypes.DOWNLOAD_FAILED,
                level=EventLevel.error,
                media=payload.media,
                actor=EventActor.system,
                source=EventSource.base,
                entities=[
                    EventEntityRef(type="command", id=command.id),
                    EventEntityRef(type="media", id=str(payload.media.media_id)),
                ],
                correlation_id=command.id,
                action_id=command.id,
            ),
            meta=DownloadFailedEventMeta(
                command_id=command.id,
                media_id=payload.media.media_id,
                resource_title=payload.resource_title,
                result_id=payload.result_id,
                directory_id=payload.directory_id,
                selected_files=list(payload.selected_files or []),
                error=command.error or "",
                error_key=command.error_key,
                error_params=command.error_params,
            ),
        )


command_service = CommandService()
