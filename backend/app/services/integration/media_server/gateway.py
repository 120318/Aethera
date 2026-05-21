import logging

from app.clients.factory import ClientFactory, ClientType
from app.schemas.config import MediaServerProviderConfig
from app.schemas.domain.media_server_link import MediaServerDetailLink
from app.schemas.exception.base import AppException
from app.schemas.domain.media_server_sync import MediaServerChange

logger = logging.getLogger("app.media_server.gateway")


class MediaServerGateway:
    async def test_connection_for_config(self, media_server: MediaServerProviderConfig) -> bool:
        client = ClientFactory.create_client_with_config(ClientType.JELLYFIN, media_server)
        return await client.test_connection()

    async def apply_changes(
        self,
        media_server: MediaServerProviderConfig,
        changes: list[MediaServerChange],
    ) -> bool:
        valid_changes = [change for change in changes if change.target_path]
        if not valid_changes or media_server.type != "jellyfin":
            return False

        try:
            client = ClientFactory.get_client_with_config(ClientType.JELLYFIN, media_server)
            logger.debug(
                "Triggering media server changes: server_id=%s changes=%s",
                media_server.id,
                [
                    {
                        "path": change.target_path,
                        "change_type": change.change_type.value,
                        "is_media_root": change.is_media_root,
                        "reason": change.reason,
                    }
                    for change in valid_changes
                ],
            )
            success = await client.apply_changes(valid_changes)
            if not success:
                logger.warning(
                    "Failed to apply media server changes: server_id=%s changes=%s",
                    media_server.id,
                    [
                        {
                            "path": change.target_path,
                            "change_type": change.change_type.value,
                            "is_media_root": change.is_media_root,
                        }
                        for change in valid_changes
                    ],
                )
            return success
        except (AppException, RuntimeError, TypeError, ValueError) as exc:
            logger.warning(
                "Failed to trigger media server changes: server_id=%s changes=%s error=%s",
                media_server.id,
                [
                    {
                        "path": change.target_path,
                        "change_type": change.change_type.value,
                        "is_media_root": change.is_media_root,
                    }
                    for change in valid_changes
                ],
                exc,
            )
            return False

    async def resolve_detail_link(
        self,
        media_server: MediaServerProviderConfig,
        media_path: str,
    ) -> MediaServerDetailLink | None:
        if not media_path or media_server.type != "jellyfin":
            return None
        try:
            client = ClientFactory.get_client_with_config(ClientType.JELLYFIN, media_server)
            return await client.resolve_detail_link(media_path)
        except (RuntimeError, TypeError, ValueError) as exc:
            logger.warning(
                "Failed to resolve media server detail link: server_id=%s path=%s error=%s",
                media_server.id,
                media_path,
                exc,
            )
            return None


media_server_gateway = MediaServerGateway()
