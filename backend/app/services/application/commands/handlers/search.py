from __future__ import annotations

import uuid

from app.schemas.domain.command import (
    CommandCreateRequest,
    CommandRecord,
    CommandResult,
    CommandTargetType,
    CommandType,
    ResourceSearchCommandRecordPayload,
)
from app.schemas.domain.media import MediaTarget
from app.schemas.domain.resource_search import MediaSearchQuery
from app.schemas.runtime.command_runtime import CommandActionContext
from app.services.application.commands.target_labels import format_media_target_label
from app.services.domain.media import media_service
from app.services.domain.subscription.download_config_service import subscription_download_config_service
from app.services.application.workflows.resource_search import resource_search_service


class ResourceSearchCommandHandler:
    command_type = CommandType.RESOURCE_SEARCH

    async def build(self, body: CommandCreateRequest) -> CommandRecord:
        request = body.payload
        target = request.target
        media_id = target.media_id
        season_number = target.season_number
        media = await media_service.resolve_execution_snapshot(
            media_id,
            season_number=season_number,
            require_tv_season=True,
        )
        payload = ResourceSearchCommandRecordPayload(
            media=media,
            site_ids=request.site_ids,
        )
        target_label = format_media_target_label(media)
        return CommandRecord(
            id=str(uuid.uuid4()),
            type=CommandType.RESOURCE_SEARCH,
            payload=payload,
            initiator=body.initiator,
            media_id=media_id,
            target=MediaTarget(media_id=media_id, season_number=season_number),
            uniq_key=(
                f"command:{CommandType.RESOURCE_SEARCH.value}:"
                f"{media_id}:season={season_number or 'all'}:"
                f"sites={','.join(sorted(request.site_ids))}"
            ),
            target_type=CommandTargetType.MEDIA,
            target_id=str(media_id),
            target_label=target_label,
        )

    async def execute(self, command: CommandRecord) -> CommandResult:
        payload = command.payload
        media = payload.media
        config = await subscription_download_config_service.find_by_media_id(media.media_id, media.season_number)
        results = await resource_search_service.search_media(
            MediaSearchQuery(
                media=media,
                indexers=payload.site_ids or None,
                unmatched_rules=list(config.unmatched_rules) if config else [],
                use_cache=False,
            )
        )
        return CommandResult(result_count=len(results or []))

    def resolve_running_message(self) -> str:
        return "Searching resources"

    def resolve_success_message(self, result: CommandResult) -> str:
        return f"Search completed, found {result.result_count} resources"

    def resolve_failed_message(self) -> str:
        return "Resource search failed"

    def resolve_action_context(self, command: CommandRecord) -> CommandActionContext:
        payload = command.payload
        return CommandActionContext(media_id=payload.media.media_id)


def register_search_command_handlers(registry) -> None:
    registry.register(ResourceSearchCommandHandler())
