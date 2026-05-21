from pydantic import BaseModel

from app.schemas.domain.command import CommandInitiator, CommandRecord
from app.schemas.domain.media_types import MediaType
from app.schemas.media_id import MediaID
from app.services.application.workflows.profile_refresh.service import profile_refresh_command_service
from app.services.domain.media import media_service
from app.services.domain.media.mapping import MediaExternalMappingService, media_external_mapping_service


class MediaExternalMappingAttachCommandResult(BaseModel):
    media_id: MediaID
    command: CommandRecord


class MediaExternalMappingApplicationService:
    def __init__(
        self,
        *,
        mapping_service: MediaExternalMappingService | None = None,
    ) -> None:
        self.mapping_service = mapping_service or media_external_mapping_service

    async def attach_tmdb_mapping(
        self,
        media_id: MediaID,
        *,
        tmdb_id: int,
        season_number: int | None = None,
        episode_count_override: int | None = None,
    ) -> MediaExternalMappingAttachCommandResult:
        media = await media_service.simple_info(media_id)
        target_season_number = None
        if media and media.media_type == MediaType.tv:
            target_season_number = season_number or media.season_number or 1
        result = await self.mapping_service.attach_tmdb_mapping(
            media,
            tmdb_id=tmdb_id,
            season_number=target_season_number,
            episode_count_override=episode_count_override,
        )
        try:
            command = await profile_refresh_command_service.enqueue(
                result.canonical_media_id,
                season_number=target_season_number,
                initiator=CommandInitiator.SYSTEM,
                force_requeue=True,
            )
        except Exception:
            self.mapping_service.rollback_tmdb_mapping_attach(result)
            raise

        self.mapping_service.finalize_tmdb_mapping_attach(result)
        await media_service.apply_source_mapping_snapshot(
            result.canonical_media_id,
            season_number=target_season_number,
            douban_id=None,
            episode_count_override=episode_count_override,
        )
        return MediaExternalMappingAttachCommandResult(
            media_id=result.canonical_media_id,
            command=command,
        )


media_external_mapping_application_service = MediaExternalMappingApplicationService()
