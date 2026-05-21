from __future__ import annotations

from app.db.repositories.settings_sqlite_repository import SettingsSqliteRepository
from app.schemas.config import MediaServerProviderConfig
from app.schemas.exception import ConfigurationException


class MediaServerSettings:
    def __init__(self, repo: SettingsSqliteRepository) -> None:
        self._repo = repo

    def list(self) -> list[MediaServerProviderConfig]:
        return self._repo.media_servers.list()

    def replace_all(self, media_servers: list[MediaServerProviderConfig]) -> None:
        self._repo.media_servers.replace(media_servers)

    def create(self, media_server: MediaServerProviderConfig) -> MediaServerProviderConfig:
        media_servers = self.list()
        if any(item.id == media_server.id for item in media_servers):
            raise ConfigurationException("backendErrors.config.mediaServerIdExists", params={"id": media_server.id})
        media_servers.append(media_server)
        self.replace_all(media_servers)
        return media_server

    def update(self, media_server_id: str, media_server: MediaServerProviderConfig) -> MediaServerProviderConfig:
        media_servers = self.list()
        current_index = next((index for index, item in enumerate(media_servers) if item.id == media_server_id), -1)
        if current_index == -1:
            raise ConfigurationException("backendErrors.config.mediaServerNotFound", params={"id": media_server_id})
        media_server.id = media_server_id
        media_servers[current_index] = media_server
        self.replace_all(media_servers)
        return media_server

    def delete(self, media_server_id: str) -> None:
        media_servers = self.list()
        next_media_servers = [item for item in media_servers if item.id != media_server_id]
        if len(next_media_servers) == len(media_servers):
            raise ConfigurationException("backendErrors.config.mediaServerNotFound", params={"id": media_server_id})
        if self.get_default_id() == media_server_id:
            self.clear_default()
        self.replace_all(next_media_servers)

    def set_default(self, media_server_id: str) -> None:
        media_server = next((item for item in self.list() if item.id == media_server_id and item.enabled), None)
        if media_server is None:
            raise ConfigurationException("backendErrors.config.mediaServerNotFoundOrDisabled", params={"id": media_server_id})
        self._repo.set_default("default_media_server_id", media_server_id)

    def clear_default(self) -> None:
        self._repo.set_default("default_media_server_id", None)

    def get_default_id(self) -> str | None:
        return self._repo.get_default("default_media_server_id")
