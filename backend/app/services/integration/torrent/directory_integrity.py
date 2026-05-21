from __future__ import annotations

import logging

from pydantic import BaseModel, ConfigDict

from app.clients.factory import ClientFactory
from app.schemas.domain.download import TaskData
from app.schemas.domain.torrent_status import TorrentStatus
from app.schemas.exception.exceptions import DownloadException
from app.services.domain.directory_integrity.models import DownloaderTorrentIndex, TrackerMessageIndex

logger = logging.getLogger("app.services.directory_integrity.torrent")


class TorrentTrackerInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    msg: str = ""
    message: str = ""

    @property
    def status_message(self) -> str:
        return str(self.msg or self.message).strip()


class DirectoryIntegrityTorrentSnapshot:
    def __init__(self) -> None:
        self.client_factory = ClientFactory

    async def load_torrents(self, tasks: list[TaskData]) -> DownloaderTorrentIndex:
        hashes_by_downloader: dict[str, set[str]] = {}
        for task in tasks:
            if not task.downloader_id or not task.torrent_hash:
                continue
            if task.downloader_id not in hashes_by_downloader:
                hashes_by_downloader[task.downloader_id] = set()
            hashes_by_downloader[task.downloader_id].add(task.torrent_hash.lower())

        results: DownloaderTorrentIndex = {}
        for downloader_id, hashes in hashes_by_downloader.items():
            try:
                client = self.client_factory.get_download_client(downloader_id)
                statuses: list[TorrentStatus] = await client.get_torrents(hashes=sorted(hashes))
            except (DownloadException, RuntimeError, ValueError, OSError) as exc:
                logger.warning("Failed to inspect downloader torrents for %s: %s", downloader_id, exc)
                continue
            results[downloader_id] = {status.hash.lower(): status for status in statuses if status.hash}
        return results

    async def load_tracker_messages(self, downloader_torrents: DownloaderTorrentIndex) -> TrackerMessageIndex:
        results: TrackerMessageIndex = {}
        for downloader_id, torrents in downloader_torrents.items():
            try:
                client = self.client_factory.get_download_client(downloader_id)
            except (DownloadException, RuntimeError, ValueError, OSError) as exc:
                logger.warning("Failed to create downloader client for tracker inspection %s: %s", downloader_id, exc)
                continue
            for torrent_hash in torrents:
                try:
                    raw_trackers = await client.get_torrent_trackers(torrent_hash)
                except (AttributeError, DownloadException, RuntimeError, ValueError, OSError) as exc:
                    logger.warning("Failed to inspect torrent trackers for %s: %s", torrent_hash, exc)
                    continue
                trackers = [self._normalize_tracker(item) for item in raw_trackers]
                results[(downloader_id, torrent_hash)] = self._extract_tracker_messages(trackers)
        return results

    @staticmethod
    def _normalize_tracker(raw_tracker) -> TorrentTrackerInfo:
        return TorrentTrackerInfo.model_validate(raw_tracker)

    @staticmethod
    def _extract_tracker_messages(trackers: list[TorrentTrackerInfo]) -> list[str]:
        messages: list[str] = []
        for tracker in trackers:
            message = tracker.status_message
            if DirectoryIntegrityTorrentSnapshot._is_ignored_tracker_message(message):
                continue
            if message and message not in messages:
                messages.append(message)
        return messages

    @staticmethod
    def _is_ignored_tracker_message(message: str) -> bool:
        text = message.strip().lower()
        if not text:
            return True
        if text in {"<none>", "none"}:
            return True
        return ("private" in text and "torrent" in text) or ("私有" in text and ("torrent" in text or "种子" in text))
