import logging
from enum import Enum
from typing import ClassVar, Mapping

from pydantic import BaseModel

from app.clients.base import BaseClient
from app.clients.douban import DoubanClient
from app.clients.jackett import JackettClient
from app.clients.jellyfin import JellyfinClient
from app.clients.prowlarr import ProwlarrClient
from app.clients.qbittorrent import QBittorrentClient
from app.clients.rtorrent import RTorrentClient
from app.clients.tmdb import TMDBClient
from app.schemas.config import (
    ClientConfigBase,
    DoubanConfig,
    DownloaderConfig,
    IndexerConfig,
    IndexerProviderConfig,
    MediaServerConfig,
    MediaServerProviderConfig,
    TMDBConfig,
)
from app.services.integration.download.client import DownloadClient
from app.services.config.settings_service import settings_service

logger = logging.getLogger(__name__)


class ClientType(str, Enum):
    """Internal helper."""
    # Internal note.
    TMDB = "themoviedb"
    DOUBAN = "douban"
    
    # Internal note.
    JACKETT = "jackett"
    PROWLARR = "prowlarr"
    
    # Internal note.
    QBITTORRENT = "qbittorrent"
    RTORRENT = "rtorrent"
    
    # Internal note.
    JELLYFIN = "jellyfin"


class ClientFactory:
    """Internal helper."""
    
    # Internal note.
    _client_map: ClassVar[Mapping[ClientType, type[BaseClient]]] = {
        ClientType.TMDB: TMDBClient,
        ClientType.JACKETT: JackettClient,
        ClientType.PROWLARR: ProwlarrClient,
        ClientType.QBITTORRENT: QBittorrentClient,
        ClientType.RTORRENT: RTorrentClient,
        ClientType.JELLYFIN: JellyfinClient,
        ClientType.DOUBAN: DoubanClient
    }

    # Internal note.
    # Key: client_type text client_type:config_id
    _instances: ClassVar[dict[str, BaseClient]] = {}
    
    @classmethod
    def _get_instance_key(cls, client_type: ClientType, config_id: str | None = None) -> str:
        if config_id:
            return f"{client_type.value}:{config_id}"
        return client_type.value

    @classmethod
    def _get_tmdb_config(cls) -> TMDBConfig:
        return settings_service.get_base_services_config().themoviedb

    @classmethod
    def _get_douban_config(cls) -> DoubanConfig:
        return settings_service.get_base_services_config().douban

    @classmethod
    def _get_config_id(
        cls,
        config: BaseModel | None,
    ) -> str | None:
        return config.id if isinstance(config, ClientConfigBase) else None

    @classmethod
    def _get_default_enabled_indexer(cls) -> IndexerProviderConfig | None:
        default_indexer_id = settings_service.get_default_indexer_id()
        indexers = settings_service.list_indexers()
        if default_indexer_id:
            default_indexer = next(
                (indexer for indexer in indexers if indexer.id == default_indexer_id and indexer.enabled),
                None,
            )
            if default_indexer:
                return default_indexer
        return next((indexer for indexer in indexers if indexer.enabled), None)

    @classmethod
    def _get_default_enabled_downloader(cls, downloader_id: str | None = None) -> DownloaderConfig | None:
        downloaders = settings_service.list_downloaders()
        if downloader_id:
            selected = next(
                (downloader for downloader in downloaders if downloader.id == downloader_id and downloader.enabled),
                None,
            )
            if selected:
                return selected
        default_downloader_id = settings_service.get_default_downloader_id()
        if default_downloader_id:
            default_downloader = next(
                (downloader for downloader in downloaders if downloader.id == default_downloader_id and downloader.enabled),
                None,
            )
            if default_downloader:
                return default_downloader
        return next((downloader for downloader in downloaders if downloader.enabled), None)

    @classmethod
    def _get_default_enabled_media_server(cls) -> MediaServerProviderConfig | None:
        default_media_server_id = settings_service.get_default_media_server_id()
        media_servers = settings_service.list_media_servers()
        if default_media_server_id:
            default_media_server = next(
                (media_server for media_server in media_servers if media_server.id == default_media_server_id and media_server.enabled),
                None,
            )
            if default_media_server:
                return default_media_server
        return next((media_server for media_server in media_servers if media_server.enabled), None)

    @classmethod
    def get_client(cls, client_type: ClientType) -> BaseClient:
        """Internal helper."""
        if client_type not in cls._client_map:
            raise ValueError(f"Unsupported client type: {client_type}")

        config_obj = None
        config_id = None

        # Internal note.
        if client_type == ClientType.TMDB:
            config_obj = cls._get_tmdb_config()
        elif client_type == ClientType.DOUBAN:
            config_obj = cls._get_douban_config()
        elif client_type in {ClientType.JACKETT, ClientType.PROWLARR}:
            config_obj = cls._get_default_enabled_indexer()
        elif client_type in {ClientType.QBITTORRENT, ClientType.RTORRENT}:
            config_obj = cls._get_default_enabled_downloader()
        elif client_type == ClientType.JELLYFIN:
            config_obj = cls._get_default_enabled_media_server()

        config_id = cls._get_config_id(config_obj)

        key = cls._get_instance_key(client_type, config_id)
        if key in cls._instances:
            return cls._instances[key]

        # Internal note.
        client_class = cls._client_map[client_type]
        logger.debug("Creating new client instance: %s", key)
        try:
            instance = client_class(config_obj) if config_obj else client_class()
            cls._instances[key] = instance
            return instance
        except (RuntimeError, TypeError, ValueError) as e:
            raise RuntimeError(f"Failed to create client {key}: {str(e)}") from e
    
    @classmethod
    def get_client_with_config(
        cls,
        client_type: ClientType,
        config: BaseModel | None,
    ) -> BaseClient:
        """Internal helper."""
        config_id = cls._get_config_id(config)
        key = cls._get_instance_key(client_type, config_id)
        
        if key in cls._instances:
            return cls._instances[key]

        client_class = cls._client_map[client_type]
        try:
            logger.debug("Creating new client instance with custom config: %s", key)
            instance = client_class(config) if config else client_class()
            cls._instances[key] = instance
            return instance
        except (RuntimeError, TypeError, ValueError) as e:
            raise RuntimeError(f"Failed to create client {key} with custom config: {str(e)}") from e

    @classmethod
    def create_client_with_config(
        cls,
        client_type: ClientType,
        config: BaseModel | None,
    ) -> BaseClient:
        """Internal helper."""
        if client_type not in cls._client_map:
            raise ValueError(f"Unsupported client type: {client_type}")
        client_class = cls._client_map[client_type]
        try:
            logger.debug("Creating uncached client instance: %s", client_type.value)
            return client_class(config) if config else client_class()
        except (RuntimeError, TypeError, ValueError) as e:
            raise RuntimeError(f"Failed to create uncached client {client_type.value} with custom config: {str(e)}") from e
    
    @classmethod
    def get_download_client(cls, downloader_id: str | None = None) -> DownloadClient:
        """Internal helper."""
        downloader_config = cls._get_default_enabled_downloader(downloader_id)
        if not downloader_config:
            raise ValueError("No enabled downloader config is available")
        
        return cls.get_client_with_config(ClientType(downloader_config.type), downloader_config)
    
    @classmethod
    def clear_cache(cls) -> None:
        """Internal helper."""
        logger.debug("Clearing client instance cache")
        cls._instances.clear()
