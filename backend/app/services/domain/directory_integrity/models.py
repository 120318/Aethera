from __future__ import annotations

from dataclasses import dataclass, field

from app.schemas.config import DirectoryConfig
from app.schemas.domain.download import TaskData
from app.schemas.domain.library import LibraryFile
from app.schemas.domain.torrent_status import TorrentStatus
from app.schemas.runtime.directory_integrity import DirectoryIntegrityPolicy


MediaDisplayIndex = dict[str, tuple[str, int | None]]
DownloaderTorrentIndex = dict[str, dict[str, TorrentStatus]]
TrackerMessageIndex = dict[tuple[str, str], list[str]]


@dataclass(frozen=True)
class DirectorySizeSummary:
    physical_size: int = 0
    logical_size: int = 0
    library_logical_size: int = 0
    download_logical_size: int = 0


@dataclass(frozen=True)
class DirectorySizeIndex:
    directories: dict[str, DirectorySizeSummary] = field(default_factory=dict)
    global_summary: DirectorySizeSummary = field(default_factory=DirectorySizeSummary)


@dataclass(frozen=True)
class DirectoryIntegritySnapshot:
    directories: list[DirectoryConfig]
    all_directories: list[DirectoryConfig]
    policies: dict[str, DirectoryIntegrityPolicy]
    library_files: list[LibraryFile]
    tasks: list[TaskData]
    media_display: MediaDisplayIndex
    downloader_torrents: DownloaderTorrentIndex = field(default_factory=dict)
    tracker_messages: TrackerMessageIndex = field(default_factory=dict)
