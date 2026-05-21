from app.schemas.domain.media_types import MediaType
from app.schemas.exception import DownloadException
from app.schemas.exception.exceptions import InvalidRequestException
from app.schemas.media_id import MediaID
from app.schemas.domain.action import ActionSource
from app.schemas.domain.command import CommandCreateRequest, CommandInitiator, CommandRecord, CommandType, ProfileRefreshCommandRequestPayload
from app.schemas.domain.media import MediaTarget
from app.services.application.commands.service import command_service


class ProfileRefreshCommandService:
    @staticmethod
    def _uniq_key(media_id: MediaID, season_number: int | None = None) -> str:
        if media_id.media_type == MediaType.tv and (season_number is None or season_number <= 0):
            raise InvalidRequestException("backendErrors.seasonRequired")
        season_part = f":season={season_number}" if season_number is not None and season_number > 0 else ":season=all"
        return f"command:{CommandType.PROFILE_REFRESH.value}:{media_id}{season_part}"

    @classmethod
    def _followup_uniq_key(cls, media_id: MediaID, season_number: int | None = None) -> str:
        return f"{cls._uniq_key(media_id, season_number)}:followup"

    @staticmethod
    def _target(media_id: MediaID, season_number: int | None) -> MediaTarget:
        if media_id.media_type == MediaType.tv and (season_number is None or season_number <= 0):
            raise InvalidRequestException("backendErrors.seasonRequired")
        return MediaTarget(media_id=media_id, season_number=season_number if season_number and season_number > 0 else None)

    async def enqueue(
        self,
        media_id: MediaID,
        season_number: int | None = None,
        initiator: CommandInitiator = CommandInitiator.SYSTEM,
        *,
        force_requeue: bool = False,
    ) -> CommandRecord | None:
        target = self._target(media_id, season_number)
        if not force_requeue:
            return await command_service.create_command(
                CommandCreateRequest(
                    type=CommandType.PROFILE_REFRESH,
                    initiator=initiator,
                    payload=ProfileRefreshCommandRequestPayload(target=target),
                )
            )

        existing = await command_service.find_active_command_by_uniq_key(self._uniq_key(media_id, season_number))
        if existing and existing.status.value == "queued":
            try:
                await command_service.cancel_command(existing.id)
            except DownloadException:
                existing = await command_service.find_active_command_by_uniq_key(self._uniq_key(media_id, season_number))

        if existing and existing.status.value == "running":
            return await command_service.create_command_with_uniq_key(
                CommandCreateRequest(
                    type=CommandType.PROFILE_REFRESH,
                    initiator=initiator,
                    payload=ProfileRefreshCommandRequestPayload(target=target),
                ),
                uniq_key=self._followup_uniq_key(media_id, season_number),
                source=ActionSource.api,
            )

        return await command_service.create_command(
            CommandCreateRequest(
                type=CommandType.PROFILE_REFRESH,
                initiator=initiator,
                payload=ProfileRefreshCommandRequestPayload(target=target),
            )
        )


profile_refresh_command_service = ProfileRefreshCommandService()
