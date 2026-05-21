from __future__ import annotations

import uuid

from app.schemas.domain.command import (
    CommandCreateRequest,
    CommandRecord,
    CommandResult,
    CommandTargetType,
    CommandType,
    SubscriptionRunCommandRecordPayload,
)
from app.schemas.runtime.command_runtime import CommandActionContext
from app.services.application.commands.target_labels import format_media_target_label
from app.services.application.workflows.subscription.run import subscription_run_application_service
from app.services.domain.media import media_service


class SubscriptionRunCommandHandler:
    command_type = CommandType.SUBSCRIPTION_RUN

    async def build(self, body: CommandCreateRequest) -> CommandRecord:
        request = body.payload
        target = request.target
        payload = SubscriptionRunCommandRecordPayload(target=target)
        media = await media_service.resolve_execution_snapshot(
            target.media_id,
            season_number=target.season_number,
        )
        target_label = format_media_target_label(media)
        return CommandRecord(
            id=str(uuid.uuid4()),
            type=CommandType.SUBSCRIPTION_RUN,
            payload=payload,
            initiator=body.initiator,
            media_id=target.media_id,
            target=target,
            uniq_key=f"command:{CommandType.SUBSCRIPTION_RUN.value}:{target.media_id}:season={target.season_number or 'all'}",
            target_type=CommandTargetType.MEDIA,
            target_id=str(target.media_id),
            target_label=target_label,
        )

    async def execute(self, command: CommandRecord) -> CommandResult:
        payload = command.payload
        result = await subscription_run_application_service.run_one_by_media_id(payload.target.media_id, payload.target.season_number)
        return CommandResult(result_count=result.checked)

    def resolve_running_message(self) -> str:
        return "Running subscription refresh"

    def resolve_success_message(self, result: CommandResult) -> str:
        return "Subscription refresh completed"

    def resolve_failed_message(self) -> str:
        return "Subscription refresh failed"

    def resolve_action_context(self, command: CommandRecord) -> CommandActionContext:
        payload = command.payload
        return CommandActionContext(media_id=payload.target.media_id)


def register_subscription_command_handlers(registry) -> None:
    registry.register(SubscriptionRunCommandHandler())
