from __future__ import annotations

import uuid

from app.schemas.domain.command import (
    CommandCreateRequest,
    CommandRecord,
    CommandResult,
    CommandTargetType,
    CommandType,
    ProfileRefreshCommandRecordPayload,
)
from app.schemas.runtime.command_runtime import CommandActionContext
from app.services.application.commands.target_labels import format_media_target_label
from app.services.domain.media import media_service


class ProfileRefreshCommandHandler:
    command_type = CommandType.PROFILE_REFRESH

    async def build(self, body: CommandCreateRequest) -> CommandRecord:
        request = body.payload
        target = request.target
        payload = ProfileRefreshCommandRecordPayload(target=target)
        media = await media_service.resolve_execution_snapshot(
            target.media_id,
            season_number=target.season_number,
        )
        target_label = format_media_target_label(media)
        season_part = f":season={target.season_number}" if target.season_number is not None and target.season_number > 0 else ":season=all"
        return CommandRecord(
            id=str(uuid.uuid4()),
            type=CommandType.PROFILE_REFRESH,
            payload=payload,
            initiator=body.initiator,
            media_id=target.media_id,
            target=target,
            uniq_key=f"command:{CommandType.PROFILE_REFRESH.value}:{target.media_id}{season_part}",
            target_type=CommandTargetType.MEDIA,
            target_id=str(target.media_id),
            target_label=target_label,
        )

    async def execute(self, command: CommandRecord) -> CommandResult:
        payload = command.payload
        await media_service.refresh_profile_safely(payload.target.media_id, payload.target.season_number)
        return CommandResult()

    def resolve_running_message(self) -> str:
        return "Refreshing media profile"

    def resolve_success_message(self, result: CommandResult) -> str:
        return "Media profile refreshed"

    def resolve_failed_message(self) -> str:
        return "Media profile refresh failed"

    def resolve_action_context(self, command: CommandRecord) -> CommandActionContext:
        payload = command.payload
        return CommandActionContext(media_id=payload.target.media_id)


def register_profile_command_handlers(registry) -> None:
    registry.register(ProfileRefreshCommandHandler())
