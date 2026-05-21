from __future__ import annotations

from abc import ABC, abstractmethod

from app.clients.base import BaseClient
from app.schemas.config import DownloaderConfig
from pydantic import BaseModel
from app.schemas.integration.common import ClientOperationResult
from app.schemas.domain.download import DownloadFileInfo, DownloadInfo
from app.schemas.domain.torrent_status import TorrentStatus


class DownloadClientCapabilities(BaseModel):
    can_apply_categories: bool = True
    can_apply_tags: bool = True
    can_delete_files: bool = True
    delete_files_requires_aethera: bool = False
    can_export_torrent: bool = True
    can_recheck: bool = True
    can_set_file_priority: bool = True
    can_set_location: bool = True
    location_update_requires_aethera_move: bool = False
    can_read_trackers: bool = True


class DownloadClient(BaseClient, ABC):
    """Abstract interface that download clients (qBittorrent, others) should implement."""

    def __init__(self, config: DownloaderConfig):
        """text
        
        Args:
            config: text
        """
        self.config = config

    def get_id(self) -> str:
        """identifier
        
        Returns:
            str: identifier
        """
        if self.config:
            return self.config.id
        return 'default_download_client'

    def capabilities(self) -> DownloadClientCapabilities:
        return DownloadClientCapabilities()

    @abstractmethod
    async def add_torrent_file(
        self,
        torrent_data: bytes,
        category: str | None = None,
        save_path: str | None = None,
        file_priorities: list[int] | None = None,
        torrent_hash: str | None = None,
        tags: list[str] | None = None,
        is_paused: bool | None = None,
    ) -> ClientOperationResult:
        raise NotImplementedError()

    @abstractmethod
    async def get_torrents(self, hashes: list[str] | None = None) -> list[TorrentStatus]:
        raise NotImplementedError()

    @abstractmethod
    async def get_torrent_info(self, torrent_hash: str) -> DownloadInfo | None:
        """Return a `DownloadInfo` model for the given torrent hash, or None.

        """
        raise NotImplementedError()

    @abstractmethod
    async def get_torrent_files(self, torrent_hash: str) -> list[DownloadFileInfo] | None:
        raise NotImplementedError()

    @abstractmethod
    async def set_file_priority(self, torrent_hash: str, file_ids: list[int], priority: int) -> bool:
        raise NotImplementedError()

    async def export_torrent(self, torrent_hash: str) -> bytes | None:
        raise NotImplementedError()

    async def recheck_torrents(self, hashes: list[str]) -> bool:
        raise NotImplementedError()

    async def set_torrent_location(self, hashes: list[str], location: str) -> bool:
        raise NotImplementedError()

    @abstractmethod
    async def start_torrents(self, hashes: list[str]) -> bool:
        raise NotImplementedError()

    @abstractmethod
    async def pause_torrents(self, hashes: list[str]) -> bool:
        raise NotImplementedError()

    @abstractmethod
    async def delete_torrent(self, torrent_hash: str, delete_files: bool = False) -> bool:
        raise NotImplementedError()

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def test_connection(self) -> bool:
        """Test connection to the download client.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        pass
    

    
    def name(self) -> str:
        """Optional friendly name for the client implementation."""
        return self.__class__.__name__
