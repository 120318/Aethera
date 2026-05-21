"""
text
text
"""
from abc import ABC, abstractmethod

from app.schemas.config import DownloaderProviderConfig, IndexerProviderConfig, MediaServerProviderConfig
from app.schemas.integration.site_models import SiteInfo, SiteSearchCapabilities
from app.schemas.domain.resource_search import ResourceSearchResult
from app.schemas.integration.common import ClientOperationResult
from app.schemas.integration.media_server import JellyfinLibrary
from app.schemas.domain.torrent_status import TorrentStatus
from app.schemas.domain.download import DownloadInfo
from app.schemas.runtime.indexer_site_health import IndexerSiteHealthStatus


class BaseClient(ABC):
    """text
    
    text
    """
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """text
        
        Returns:
            bool: textTrue，textFalse
        """
        pass
    
    @abstractmethod
    def get_id(self) -> str:
        """identifier
        
        Returns:
            str: identifier
        """
        pass


class IndexerClient(BaseClient):
    """text
    
    text
    """
    
    def __init__(self, config: IndexerProviderConfig):
        """text
        
        Args:
            config: text
        """
        self.config = config
    
    @abstractmethod
    async def search_all_torznab(
        self,
        query: str,
        category: str | None = None,
        indexers: list[str] | None = None,
    ) -> list[ResourceSearchResult]:
        """Internal helper."""
        pass
    
    @abstractmethod
    async def get_indexers(self) -> list[SiteInfo]:
        """Internal helper."""
        pass

    @abstractmethod
    async def get_indexer_caps(self, indexer: str) -> SiteSearchCapabilities:
        """Internal helper."""
        pass

    @abstractmethod
    async def search_indexer_torznab(
        self,
        indexer: str,
        query: str,
        category: str | None = None,
        search_param: str = "auto",
    ) -> list[ResourceSearchResult]:
        """Internal helper."""
        pass

    async def list_sites(self) -> list[SiteInfo]:
        return await self.get_indexers()

    async def get_site_capabilities(self, site_id: str) -> SiteSearchCapabilities:
        return await self.get_indexer_caps(site_id)

    async def search_site(
        self,
        site_id: str,
        query: str,
        category: str | None = None,
        search_param: str = "auto",
    ) -> list[ResourceSearchResult]:
        return await self.search_indexer_torznab(site_id, query, category=category, search_param=search_param)

    async def get_site_health(self) -> list[IndexerSiteHealthStatus]:
        return []

    async def close(self) -> None:
        return None

    def build_torznab_feed(self, query: str, indexers: list[str] | None = None) -> str:
        """Internal helper."""
        return ""


class DownloadClient(BaseClient):
    """Internal helper."""
    
    def __init__(self, config: DownloaderProviderConfig):
        """Internal helper."""
        self.config = config

    @abstractmethod
    async def add_torrent_file(
        self,
        torrent_data: bytes,
        category: str | None = None,
        save_path: str | None = None,
        file_priorities: list[int] | None = None,
        torrent_hash: str | None = None,
        tags: list[str] | None = None,
    ) -> ClientOperationResult:
        """Internal helper."""
        pass

    @abstractmethod
    async def get_torrents(self, hashes: list[str] | None = None) -> list[TorrentStatus]:
        """Internal helper."""
        pass

    @abstractmethod
    async def get_torrent_info(self, torrent_hash: str) -> DownloadInfo | None:
        """Internal helper."""
        pass

    @abstractmethod
    async def start_torrents(self, hashes: list[str]) -> bool:
        """Internal helper."""
        pass

    @abstractmethod
    async def pause_torrents(self, hashes: list[str]) -> bool:
        """Internal helper."""
        pass

    @abstractmethod
    async def delete_torrent(self, torrent_hash: str, delete_files: bool = False) -> bool:
        """Internal helper."""
        pass


class MediaServerClient(BaseClient):
    """Internal helper."""
    
    def __init__(self, config: MediaServerProviderConfig):
        """Internal helper."""
        self.config = config
    
    @abstractmethod
    async def get_libraries(self) -> list[JellyfinLibrary]:
        """Internal helper."""
        pass
    
    @abstractmethod
    async def add_media(self, library_id: str, media_path: str) -> bool:
        """Internal helper."""
        pass

    @abstractmethod
    async def refresh_path(self, media_path: str) -> bool:
        """Internal helper."""
        pass
