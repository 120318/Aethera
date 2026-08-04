import logging

from app.schemas.domain.media_types import MediaType
from app.schemas.exception import DownloadException
from app.schemas.exception.exceptions import InvalidRequestException
from app.schemas.media_id import MediaID
from app.schemas.domain.action import ActionSource
from app.schemas.domain.command import CommandCreateRequest, CommandInitiator, CommandRecord, CommandStatus, CommandType, ProfileRefreshCommandRequestPayload
from app.schemas.domain.media import MediaTarget
from app.services.application.commands.service import command_service

logger = logging.getLogger("app.services.profile_refresh_command")


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
        target_label: str | None = None,
        defer_publish: bool = False,
    ) -> CommandRecord | None:
        target = self._target(media_id, season_number)
        create_command = (
            command_service.create_staged_command
            if defer_publish
            else command_service.create_command
        )
        if not force_requeue:
            return await create_command(
                CommandCreateRequest(
                    type=CommandType.PROFILE_REFRESH,
                    initiator=initiator,
                    payload=ProfileRefreshCommandRequestPayload(target=target, target_label=target_label),
                )
            )

        existing = await command_service.find_active_command_by_uniq_key(self._uniq_key(media_id, season_number))
        if defer_publish and existing and existing.status == CommandStatus.READY:
            reserved = await command_service.reserve_ready_command(existing.id)
            if reserved.status == CommandStatus.STAGED:
                return reserved
            existing = reserved
        if existing and existing.status.value == "queued":
            try:
                await command_service.cancel_command(existing.id)
            except DownloadException:
                existing = await command_service.find_active_command_by_uniq_key(self._uniq_key(media_id, season_number))

        if existing and existing.status.value == "running":
            followup_uniq_key = self._followup_uniq_key(media_id, season_number)
            if defer_publish:
                existing_followup = await command_service.find_active_command_by_uniq_key(
                    followup_uniq_key
                )
                if existing_followup and existing_followup.status == CommandStatus.READY:
                    reserved = await command_service.reserve_ready_command(
                        existing_followup.id
                    )
                    if reserved.status == CommandStatus.STAGED:
                        return reserved
            create_with_uniq_key = (
                command_service.create_staged_command_with_uniq_key
                if defer_publish
                else command_service.create_command_with_uniq_key
            )
            return await create_with_uniq_key(
                CommandCreateRequest(
                    type=CommandType.PROFILE_REFRESH,
                    initiator=initiator,
                    payload=ProfileRefreshCommandRequestPayload(target=target, target_label=target_label),
                ),
                uniq_key=followup_uniq_key,
                source=ActionSource.api,
            )

        return await create_command(
            CommandCreateRequest(
                type=CommandType.PROFILE_REFRESH,
                initiator=initiator,
                payload=ProfileRefreshCommandRequestPayload(target=target, target_label=target_label),
            )
        )

    async def publish(self, command: CommandRecord) -> CommandRecord:
        try:
            if command.status == CommandStatus.STAGED:
                command = await command_service.mark_staged_command_ready(command.id)
            if command.status == CommandStatus.READY:
                command = await command_service.publish_staged_command(
                    command.id,
                    source=ActionSource.api,
                )
            return command
        except Exception:
            logger.exception("Deferred profile refresh will be recovered: command=%s", command.id)
            return await command_service.get_command(command.id) or command

    async def discard(self, command: CommandRecord | None) -> None:
        if command and command.status == CommandStatus.STAGED:
            await command_service.discard_staged_command(command.id)


profile_refresh_command_service = ProfileRefreshCommandService()
