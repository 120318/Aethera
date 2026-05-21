from pathlib import Path
from typing import List, Optional, Set
from enum import Enum, StrEnum
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.domain.resource_attributes import ResourceAttributes

# Canonical (normalized) torrent states derived from qBittorrent/state mapping.
class CanonicalState(str, Enum):
    DOWNLOADING = "downloading"
    SEEDING = "seeding"
    MISSING = "missing"
    ERROR = "error"
    UNKNOWN = "unknown"
    PAUSED = "paused"
    QUEUED = "queued"
    CHECKING = "checking"

class TorrentDownloadStatus(BaseModel):
    """Torrent status (text)"""
    model_config = ConfigDict(arbitrary_types_allowed=True, from_attributes=True)

    torrent_hash: str
    added_at: float
    last_updated: float
    download_client: str
    canonical_state: CanonicalState
    save_path: Optional[str] = None
    path: Optional[str] = None
    progress: float = 0.0
    download_speed: int = 0
    upload_speed: int = 0
    eta: int = 0
    
class TorrentFileItem(BaseModel):
    """Internal helper."""
    model_config = ConfigDict(from_attributes=True)

    index: int
    filename: str
    size: int
    attrs: Optional[ResourceAttributes] = None
    
    def get_episodes(self) -> Set[int]:
        if self.attrs and self.attrs.episodes:
            return set(self.attrs.episodes)
        return set()

class TorrentCoverageKind(StrEnum):
    EXACT_EPISODES = "exact_episodes"
    SEASON_PACKAGE = "season_package"
    DISC_PACKAGE = "disc_package"
    UNKNOWN = "unknown"


class TorrentMetadata(BaseModel):
    """Internal helper."""
    model_config = ConfigDict(from_attributes=True)

    hash: str
    name: str
    size: int
    files: List[TorrentFileItem] = []
    attrs: Optional[ResourceAttributes] = None
    coverage_kind: Optional[TorrentCoverageKind] = None
    
    def get_episodes(self) -> Set[int]:
        episodes = set()
        for f in self.files:
            episodes.update(f.get_episodes())
        return episodes

    def is_disc_package(self) -> bool:
        return self.coverage_kind == TorrentCoverageKind.DISC_PACKAGE

    def is_season_package(self) -> bool:
        return self.coverage_kind == TorrentCoverageKind.SEASON_PACKAGE

    def uses_root_directory_for(self, file_item: TorrentFileItem) -> bool:
        if len(self.files) > 1:
            return True
        return self._looks_like_rooted_single_file(file_item)

    def _looks_like_rooted_single_file(self, file_item: TorrentFileItem) -> bool:
        if len(self.files) != 1:
            return False

        relative = Path(file_item.filename)
        if len(relative.parts) > 1:
            return True

        root_name = Path(self.name).name.strip()
        file_name = relative.name.strip()
        if not root_name or not file_name:
            return False

        return root_name != file_name

class TorrentPayload(BaseModel):
    """Internal helper."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    metadata: TorrentMetadata
    blob: bytes # Internal note.
