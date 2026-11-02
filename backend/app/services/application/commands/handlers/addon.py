from __future__ import annotations

import uuid

from app.addons.registry import addon_service
from app.schemas.domain.command import (
    AddonRunCommandRecordPayload,
    CommandCreateRequest,
    CommandRecord,
    CommandResult,
    CommandTargetType,
    CommandType,
)
from app.schemas.runtime.command_runtime import CommandActionContext
from app.services.application.commands.target_labels import format_media_target_label
from app.services.domain.download import download_service
from app.services.domain.library.service import library_service
from app.services.domain.media import media_service


class AddonRunCommandHandler:
    command_type = CommandType.ADDON_RUN

    async def build(self, body: CommandCreateRequest) -> CommandRecord:
        request = body.payload
        self._resolve_operation(request.addon_id, request.operation_id)
        target_type = CommandTargetType.MEDIA
        target_id = str(request.target.media_id)
        target_label = target_id
        task_id = request.task_id
        file_id = request.file_id

        if task_id:
            task = await download_service.find_task_by_id(task_id)
            if task is None:
                raise ValueError("Task does not exist")
            target_type = CommandTargetType.TASK
            target_id = task.id
            context = task.context
            metadata = task.metadata
            target_label = (
                context.resource_title
                if context and context.resource_title
                else metadata.name
                if metadata and metadata.name
                else task.id
            )
        elif file_id:
            library_file = await library_service.find_file_by_id(file_id)
            if library_file is None:
                raise ValueError("Library file does not exist")
            target_type = CommandTargetType.LIBRARY_FILE
            target_id = request.package_root or library_file.id
            media = await media_service.resolve_execution_snapshot(
                request.target.media_id,
                season_number=request.target.season_number,
            )
            target_label = format_media_target_label(media)
        else:
            media = await media_service.resolve_execution_snapshot(
                request.target.media_id,
                season_number=request.target.season_number,
            )
            target_label = format_media_target_label(media)

        payload = AddonRunCommandRecordPayload(
            addon_id=request.addon_id,
            operation_id=request.operation_id,
            target=request.target,
            task_id=task_id,
            file_id=file_id,
            package_root=request.package_root,
            event_id=request.event_id,
        )
        return CommandRecord(
            id=str(uuid.uuid4()),
            type=self.command_type,
            payload=payload,
            initiator=body.initiator,
            media_id=request.target.media_id,
            target=request.target,
            uniq_key=(
                f"command:{self.command_type.value}:{request.addon_id}:"
                f"{request.operation_id}:{target_type.value}:{target_id}"
            ),
            target_type=target_type,
            target_id=target_id,
            target_label=target_label,
        )

    async def execute(self, command: CommandRecord) -> CommandResult:
        payload = command.payload
        operation = self._resolve_operation(payload.addon_id, payload.operation_id)
        if operation.handler is None:
            raise ValueError(
                f"Addon operation has no handler: {payload.addon_id}.{payload.operation_id}"
            )
        return await operation.handler(payload)

    def resolve_running_message(self) -> str:
        return "Running addon operation"

    def resolve_success_message(self, result: CommandResult) -> str:
        return f"Addon operation completed, processed {result.result_count} files"

    def resolve_failed_message(self) -> str:
        return "Addon operation failed"

    def resolve_action_context(self, command: CommandRecord) -> CommandActionContext:
        payload = command.payload
        return CommandActionContext(
            media_id=payload.target.media_id,
            task_id=payload.task_id,
        )

    @staticmethod
    def _resolve_operation(addon_id: str, operation_id: str):
        addon_service.discover_and_register()
        if not addon_service.is_addon_enabled(addon_id):
            raise ValueError(f"Addon is not enabled: {addon_id}")
        operation = addon_service.get_command(addon_id, operation_id)
        if operation is None:
            raise ValueError(f"Unknown addon operation: {addon_id}.{operation_id}")
        return operation


def register_addon_command_handlers(registry) -> None:
    registry.register(AddonRunCommandHandler())
