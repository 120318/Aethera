"""
Torrent status models for unified download client interface
"""
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class TorrentState(str, Enum):
    DOWNLOADING = "downloading"
    SEEDING = "seeding"
    PAUSED = "paused"
    QUEUED = "queued"
    CHECKING = "checking"
    MISSING = "missing"
    ERROR = "error"
    UNKNOWN = "unknown"


class TorrentStatus(BaseModel):
    """Internal helper."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    
    # Internal note.
    hash: str = Field(..., description="Field description")
    name: str = Field(..., description="Field description")
    size: int = Field(..., description="Field description")
    progress: float = Field(..., description="Field description")
    
    # Internal note.
    state: TorrentState = Field(..., description="Field description")
    download_speed: int = Field(default=0, description="Field description")
    upload_speed: int = Field(default=0, description="Field description")
    ratio: float = Field(default=0.0, description="Field description")
    eta: int = Field(default=0, description="Field description")
    num_seeds: int = Field(default=0, description="Field description")
    num_leechs: int = Field(default=0, description="Field description")
    
    # Internal note.
    added_on: datetime | None = None
    completion_on: datetime | None = None
    
    # Internal note.
    downloader_id: str = Field(..., description="Field description")
    
    # Internal note.
    save_path: str | None = None
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    

class TorrentStatusMap(BaseModel):
    """Internal helper."""
    
    torrents_by_hash: dict[str, list[TorrentStatus]] = Field(
        default_factory=dict,
        description="Field description"
    )
    
    def add_torrent(self, torrent: TorrentStatus) -> None:
        """Internal helper."""
        if torrent.hash not in self.torrents_by_hash:
            self.torrents_by_hash[torrent.hash] = []
        self.torrents_by_hash[torrent.hash].append(torrent)
    
    def get_torrents(self, torrent_hash: str) -> list[TorrentStatus]:
        """Internal helper."""
        return self.torrents_by_hash.get(torrent_hash, [])
    
    def has_torrent(self, torrent_hash: str) -> bool:
        """Internal helper."""
        return torrent_hash in self.torrents_by_hash
    
    def get_primary_torrent(self, torrent_hash: str) -> TorrentStatus | None:
        """Internal helper."""
        torrents = self.get_torrents(torrent_hash)
        return torrents[0] if torrents else None
