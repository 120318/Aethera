"""qBittorrent client implementing the DownloadClient interface.

This module exposes `QBittorrentClient` and a module-global `qb_client`
instance created from configured settings.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime
from typing import List, Optional

import bencodepy
import qbittorrentapi
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.config import DownloaderConfig
from app.schemas.exception import ConfigurationException
from app.schemas.domain.download import DownloadFileInfo, DownloadInfo
from app.schemas.integration.common import ClientOperationResult
from app.schemas.domain.torrent_status import TorrentState, TorrentStatus
from app.utils.path_utils import PathMapper
from app.services.integration.download.client import DownloadClient

logger = logging.getLogger(__name__)


class QBFileInfo(BaseModel):
    """qBittorrent file info model"""
    model_config = ConfigDict(extra="allow")

    index: int = 0
    name: str = ""
    size: int = 0
    progress: float = 0.0
    priority: int = 0


class QBTorrentInfo(BaseModel):
    """qBittorrent torrent info model"""
    model_config = ConfigDict(extra="allow")

    hash: str = ""
    name: str = ""
    size: int = 0
    progress: float = 0.0
    state: str = ""
    dlspeed: int = 0
    upspeed: int = 0
    ratio: float = 0.0
    eta: int = 0
    num_seeds: int = 0
    num_leechs: int = 0
    added_on: int = 0
    completion_on: int = 0
    save_path: str = ""
    category: str = ""
    tags: str = ""
    
    # Optional fields for detail info
    content_path: Optional[str] = None
    magnet_uri: Optional[str] = None
    files: Optional[List[QBFileInfo]] = None


QBTorrentInfo.model_rebuild()


QB_STATE_MAPPING = {
    # Error / missing
    "error": TorrentState.ERROR,
    "missingfiles": TorrentState.MISSING,

    # Downloading phase (including metadata / allocating / moving / forced)
    "downloading": TorrentState.DOWNLOADING,
    "stalleddl": TorrentState.DOWNLOADING,
    "forceddl": TorrentState.DOWNLOADING,
    "metadl": TorrentState.DOWNLOADING,
    "forcedmetadl": TorrentState.DOWNLOADING,
    "allocating": TorrentState.DOWNLOADING,
    "moving": TorrentState.DOWNLOADING,

    # Seeding phase (uploading & stalled/forced)
    "uploading": TorrentState.SEEDING,
    "stalledup": TorrentState.SEEDING,
    "forcedup": TorrentState.SEEDING,

    # Paused / stopped (download or upload, finished or not)
    "pauseddl": TorrentState.PAUSED,
    "pausedup": TorrentState.PAUSED,
    "stoppeddl": TorrentState.PAUSED,
    "stoppedup": TorrentState.PAUSED,

    # Queued (download or upload)
    "queueddl": TorrentState.QUEUED,
    "queuedup": TorrentState.QUEUED,

    # Checking (any kind of hash/resume-data check)
    "checkingdl": TorrentState.CHECKING,
    "checkingup": TorrentState.CHECKING,
    "checkingresumedata": TorrentState.CHECKING,

    # Unknown
    "unknown": TorrentState.UNKNOWN,
}


def _map_qb_state_to_torrent_state(state: str) -> TorrentState:
    if not state:
        return TorrentState.UNKNOWN

    s = state.lower()
    if s in QB_STATE_MAPPING:
        return QB_STATE_MAPPING[s]
    

    return TorrentState.UNKNOWN


class QBittorrentClient(DownloadClient):
    def __init__(self, config: DownloaderConfig):
        super().__init__(config)
        self._client: Optional[qbittorrentapi.Client] = None
        self._authenticated = False

    def _get_path_mapper(self) -> PathMapper:
        """Internal helper."""
        mappings = self.config.path_mappings if self.config.path_mappings else []
        return PathMapper(mappings)

    def _map_remote_to_local_path(self, remote_path: str) -> str:
        """Internal helper."""
        return self._get_path_mapper().to_local(remote_path)

    def _map_local_to_remote_path(self, local_path: Optional[str]) -> Optional[str]:
        """Internal helper."""
        if not local_path:
            return local_path
        return self._get_path_mapper().to_remote(local_path)

    async def test_connection(self) -> bool:
        return await self.authenticate()

    async def _get_client(self) -> qbittorrentapi.Client:
        if not self._client:
            url = self.config.url.rstrip('/') if self.config.url else None
            username = self.config.username
            password = self.config.password
            self._client = qbittorrentapi.Client(
                host=url,
                username=username,
                password=password,
            )
        return self._client

    async def authenticate(self) -> bool:
        if self._authenticated:
            return True
        client = await self._get_client()
        if self.config.username and self.config.password:
            try:
                await asyncio.to_thread(client.auth_log_in)
                self._authenticated = True
                return True
            except qbittorrentapi.LoginFailed as e:
                logger.error("qBittorrent authentication failed: %s", e)
                return False
            except (qbittorrentapi.APIConnectionError, qbittorrentapi.APIError, OSError) as e:
                logger.error("qBittorrent login request failed: %s", e)
                return False
        url = self.config.url.rstrip('/') if self.config.url else ''
        logger.warning("qBittorrent requires authentication but no credentials were provided: %s", url)
        return False

    async def _reauthenticate(self) -> qbittorrentapi.Client:
        self._authenticated = False
        if self._client:
            await asyncio.to_thread(self._qb_logout, self._client)
        client = await self._get_client()
        if not await self.authenticate():
            raise qbittorrentapi.LoginFailed("qBittorrent re-authentication failed")
        return client

    async def _call_with_reauth(self, operation):
        client = await self._get_client()
        try:
            return await operation(client)
        except qbittorrentapi.Forbidden403Error:
            logger.warning("qBittorrent session expired, retrying after re-authentication")
            client = await self._reauthenticate()
            return await operation(client)

    async def add_torrent_file(
        self,
        torrent_data: bytes,
        category: Optional[str] = None,
        save_path: Optional[str] = None,
        file_priorities: Optional[list[int]] = None,
        torrent_hash: Optional[str] = None,
        tags: Optional[list[str]] = None,
        is_paused: Optional[bool] = None,
    ) -> ClientOperationResult:
        await self.authenticate()
        client = await self._get_client()

        if save_path:
            try:
                save_path = self._map_local_to_remote_path(save_path)
            except ValueError:
                pass

        result = await asyncio.to_thread(self._qb_add_torrent_file, client, torrent_data, save_path, category, tags, is_paused)

        if isinstance(result, str):
            text = result.strip()
            if not text.lower().startswith('ok'):
                return ClientOperationResult(success=False, message=f"Failed to add torrent file: {text}", id=torrent_hash)

        info_hash = torrent_hash
        if not info_hash:
            try:
                decoded = bencodepy.decode(torrent_data)
                if b'info' in decoded:
                    info = decoded[b'info']
                    binfo = bencodepy.encode(info)
                    info_hash = hashlib.sha1(binfo).hexdigest()
            except (ValueError, TypeError, KeyError):
                info_hash = None

        if file_priorities and info_hash:
            await self._apply_file_priorities_after_add(info_hash, file_priorities)

        if isinstance(result, str):
            return ClientOperationResult(success=True, id=info_hash)
        
        return ClientOperationResult(success=True, id=info_hash)

    async def get_torrents(self, hashes: Optional[list[str]] = None) -> list[TorrentStatus]:
        try:
            await self.authenticate()
            torrents_data = await self._call_with_reauth(
                lambda client: asyncio.to_thread(self._qb_get_torrents, client, hashes)
            )
            torrent_statuses: list[TorrentStatus] = []
            for torrent_raw in torrents_data:
                t = QBTorrentInfo.model_validate(torrent_raw)
                torrent_status = TorrentStatus(
                    hash=t.hash,
                    name=t.name,
                    size=t.size,
                    progress=t.progress,
                    state=_map_qb_state_to_torrent_state(t.state),
                    download_speed=t.dlspeed,
                    upload_speed=t.upspeed,
                    ratio=t.ratio,
                    eta=t.eta,
                    num_seeds=t.num_seeds,
                    num_leechs=t.num_leechs,
                    added_on=datetime.fromtimestamp(t.added_on) if t.added_on > 0 else None,
                    completion_on=datetime.fromtimestamp(t.completion_on) if t.completion_on > 0 else None,
                    downloader_id=f"qbittorrent_{self.config.id if self.config else 'unknown'}",
                    save_path=t.save_path,
                    category=t.category,
                    tags=t.tags.split(",") if t.tags else [],
                )
                torrent_statuses.append(torrent_status)
            return torrent_statuses
        except (qbittorrentapi.LoginFailed, qbittorrentapi.APIConnectionError, qbittorrentapi.APIError, OSError, ValueError, TypeError) as e:
            logger.error(f"Failed to parse torrents: {e}")
            return []

    async def get_torrent_info(self, torrent_hash: str) -> Optional[DownloadInfo]:
        try:
            await self.authenticate()
            torrents = await self._call_with_reauth(
                lambda client: asyncio.to_thread(self._qb_get_torrent_info, client, torrent_hash)
            )
            if not torrents:
                return None

            t = QBTorrentInfo.model_validate(torrents[0])
            files: Optional[list[DownloadFileInfo]] = None
            if t.files:
                files = [
                    DownloadFileInfo(
                        index=f.index,
                        name=f.name,
                        size=f.size,
                        progress=f.progress,
                        priority=f.priority,
                    ) for f in t.files
                ]

            di = DownloadInfo(
                hash=t.hash,
                name=t.name,
                state=t.state,
                progress=t.progress,
                size=t.size,
                save_path=t.save_path,
                content_path=t.content_path or "",
                num_seeds=t.num_seeds,
                num_leechs=t.num_leechs,
                ratio=t.ratio,
                added_on=t.added_on,
                completed_on=t.completion_on,
                category=t.category,
                magnet_uri=t.magnet_uri or "",
                tags=t.tags.split(",") if t.tags else [],
                files=files,
            )

            di.save_path = self._map_remote_to_local_path(di.save_path)
            di.content_path = self._map_remote_to_local_path(di.content_path) if di.content_path else di.content_path
            return di
        except (qbittorrentapi.LoginFailed, qbittorrentapi.APIConnectionError, qbittorrentapi.APIError, OSError, ValueError, TypeError) as e:
            logger.error(f"Failed to parse torrent info: {e}")
            return None

    async def get_torrent_files(self, torrent_hash: str) -> Optional[list[DownloadFileInfo]]:
        await self.authenticate()
        try:
            files_raw = await self._call_with_reauth(
                lambda client: asyncio.to_thread(self._qb_get_torrent_files, client, torrent_hash)
            )
            return [
                DownloadFileInfo(
                    index=file_info.index,
                    name=file_info.name,
                    size=file_info.size,
                    progress=file_info.progress,
                    priority=file_info.priority,
                )
                for file_info in (QBFileInfo.model_validate(item) for item in files_raw)
            ]
        except (qbittorrentapi.APIConnectionError, qbittorrentapi.APIError, ValueError, TypeError) as e:
            logger.error(f"Failed to get torrent files: {e}")
            return None

    async def get_torrent_trackers(self, torrent_hash: str) -> list[dict]:
        await self.authenticate()
        try:
            trackers_raw = await self._call_with_reauth(
                lambda client: asyncio.to_thread(self._qb_get_torrent_trackers, client, torrent_hash)
            )
            return [dict(item) for item in trackers_raw]
        except (qbittorrentapi.APIConnectionError, qbittorrentapi.APIError, OSError, ValueError, TypeError) as e:
            logger.error("Failed to get torrent trackers(%s): %s", torrent_hash, e)
            return []

    async def add_torrent_tags(self, hashes: list[str], tags: list[str]) -> bool:
        await self.authenticate()
        hashes_param = self._normalize_hashes(hashes)
        tags_param = ",".join(tag.strip() for tag in tags if tag and tag.strip())
        if not tags_param:
            return True
        try:
            await self._call_with_reauth(
                lambda client: asyncio.to_thread(self._qb_add_torrent_tags, client, hashes_param, tags_param)
            )
            return True
        except (qbittorrentapi.APIConnectionError, qbittorrentapi.APIError, OSError) as e:
            logger.error("Failed to add torrent tags(%s, %s): %s", hashes, tags, e)
            return False

    async def set_file_priority(self, torrent_hash: str, file_ids: list[int], priority: int) -> bool:
        await self.authenticate()
        try:
            await self._call_with_reauth(
                lambda client: asyncio.to_thread(self._qb_set_file_priority, client, torrent_hash, file_ids, priority)
            )
            return True
        except (qbittorrentapi.APIConnectionError, qbittorrentapi.APIError, OSError) as e:
            logger.error(f"Failed to set file priority: {e}")
            return False

    async def _apply_file_priorities_after_add(self, torrent_hash: str, file_priorities: list[int]) -> None:
        try:
            selected = [index for index, priority in enumerate(file_priorities) if int(priority) > 0]
            unselected = [index for index, priority in enumerate(file_priorities) if int(priority) <= 0]
        except (ValueError, TypeError):
            logger.warning("Invalid file priorities for torrent %s", torrent_hash)
            return
        if not selected and not unselected:
            return

        for attempt in range(5):
            files = await self.get_torrent_files(torrent_hash)
            if files and len(files) >= len(file_priorities):
                if unselected and not await self.set_file_priority(torrent_hash, unselected, 0):
                    logger.warning("Failed to disable unselected files after adding torrent %s", torrent_hash)
                    return
                if selected and not await self.set_file_priority(torrent_hash, selected, 1):
                    logger.warning("Failed to enable selected files after adding torrent %s", torrent_hash)
                    return
                return
            await asyncio.sleep(0.2 * (attempt + 1))

        logger.warning("Torrent files were not ready for priority sync after adding torrent %s", torrent_hash)

    async def export_torrent(self, torrent_hash: str) -> bytes | None:
        await self.authenticate()
        try:
            return await self._call_with_reauth(
                lambda client: asyncio.to_thread(self._qb_export_torrent, client, torrent_hash)
            )
        except (qbittorrentapi.APIConnectionError, qbittorrentapi.APIError, OSError) as e:
            logger.error("Failed to export torrent %s: %s", torrent_hash, e)
            return None

    async def recheck_torrents(self, hashes: list[str]) -> bool:
        await self.authenticate()
        hashes_param = self._normalize_hashes(hashes)
        try:
            await self._call_with_reauth(
                lambda client: asyncio.to_thread(self._qb_recheck_torrents, client, hashes_param)
            )
            return True
        except (qbittorrentapi.APIConnectionError, qbittorrentapi.APIError, OSError) as e:
            logger.error("Failed to recheck torrents(%s): %s", hashes, e)
            return False

    async def set_torrent_location(self, hashes: list[str], location: str) -> bool:
        await self.authenticate()
        hashes_param = self._normalize_hashes(hashes)
        mapped_location = self._map_local_to_remote_path(location)
        try:
            await self._call_with_reauth(
                lambda client: asyncio.to_thread(self._qb_set_torrent_location, client, hashes_param, mapped_location)
            )
            return True
        except (qbittorrentapi.APIConnectionError, qbittorrentapi.APIError, OSError) as e:
            logger.error("Failed to set torrent location(%s, %s): %s", hashes, location, e)
            return False

    def _normalize_hashes(self, hashes: list[str]) -> list[str]:
        return [torrent_hash.lower() for torrent_hash in hashes]

    async def start_torrents(self, hashes: list[str]) -> bool:
        await self.authenticate()
        hashes_param = self._normalize_hashes(hashes)

        try:
            await self._call_with_reauth(
                lambda client: asyncio.to_thread(self._qb_start_torrents, client, hashes_param)
            )
            logger.debug("Started torrents: %s", hashes_param)
            return True
        except (qbittorrentapi.APIConnectionError, qbittorrentapi.APIError, OSError) as e:
            logger.error(f"Failed to start torrents({hashes}): {e}")
            return False

    async def pause_torrents(self, hashes: list[str]) -> bool:
        await self.authenticate()
        hashes_param = self._normalize_hashes(hashes)

        try:
            await self._call_with_reauth(
                lambda client: asyncio.to_thread(self._qb_pause_torrents, client, hashes_param)
            )
            logger.debug("Paused torrents: %s", hashes_param)
            return True
        except (qbittorrentapi.APIConnectionError, qbittorrentapi.APIError, OSError) as e:
            logger.error(f"Failed to pause torrents({hashes}): {e}")
            return False

    async def delete_torrent(self, torrent_hash: str, delete_files: bool = False) -> bool:
        await self.authenticate()
        try:
            await self._call_with_reauth(
                lambda client: asyncio.to_thread(self._qb_delete_torrent, client, torrent_hash, delete_files)
            )
            return True
        except (qbittorrentapi.APIConnectionError, qbittorrentapi.APIError, OSError) as e:
            logger.error(f"Failed to delete torrent: {e}")
            return False

    async def close(self) -> None:
        if self._client:
            client = self._client

            await asyncio.to_thread(self._qb_logout, client)
            self._client = None

    def _qb_add_torrent_file(self, client, torrent_data, save_path, category, tags, is_paused):
        return client.torrents_add(
            torrent_files=torrent_data,
            save_path=save_path,
            category=category,
            tags=tags,
            is_paused=is_paused,
            is_stopped=is_paused,
            use_auto_torrent_management=False,
        )

    def _qb_get_torrents(self, client, hashes):
        return client.torrents_info(torrent_hashes=hashes) if hashes else client.torrents_info()

    def _qb_get_torrent_info(self, client, torrent_hash):
        return client.torrents_info(torrent_hashes=[torrent_hash], include_files=True)

    def _qb_get_torrent_files(self, client, torrent_hash):
        return client.torrents_files(torrent_hash=torrent_hash)

    def _qb_get_torrent_trackers(self, client, torrent_hash):
        return client.torrents_trackers(torrent_hash=torrent_hash)

    def _qb_add_torrent_tags(self, client, hashes_param, tags_param):
        client.torrents_add_tags(torrent_hashes=hashes_param, tags=tags_param)

    def _qb_set_file_priority(self, client, torrent_hash, file_ids, priority):
        client.torrents_file_priority(
            torrent_hash=torrent_hash,
            file_ids=file_ids,
            priority=priority,
        )

    def _qb_export_torrent(self, client, torrent_hash):
        return client.torrents_export(torrent_hash=torrent_hash)

    def _qb_recheck_torrents(self, client, hashes_param):
        client.torrents_recheck(torrent_hashes=hashes_param)

    def _qb_set_torrent_location(self, client, hashes_param, location):
        client.torrents_set_location(torrent_hashes=hashes_param, location=location)

    def _qb_start_torrents(self, client, hashes_param):
        if hasattr(client, "torrents_resume"):
            client.torrents_resume(torrent_hashes=hashes_param)
            return
        client.torrents_start(torrent_hashes=hashes_param)

    def _qb_pause_torrents(self, client, hashes_param):
        if hasattr(client, "torrents_pause"):
            client.torrents_pause(torrent_hashes=hashes_param)
            return
        client.torrents_stop(torrent_hashes=hashes_param)

    def _qb_delete_torrent(self, client, torrent_hash, delete_files):
        client.torrents_delete(
            delete_files=delete_files,
            torrent_hashes=[torrent_hash],
        )

    def _qb_logout(self, client):
        try:
            client.auth_log_out()
        except (qbittorrentapi.APIConnectionError, qbittorrentapi.APIError, OSError):
            pass
