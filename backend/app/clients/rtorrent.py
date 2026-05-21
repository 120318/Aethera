"""rTorrent XMLRPC client implementing the DownloadClient interface."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime
from xmlrpc import client as xmlrpc_client

import bencodepy
import httpx
from pydantic import BaseModel, ConfigDict

from app.schemas.config import DownloaderConfig
from app.schemas.domain.download import DownloadFileInfo, DownloadInfo
from app.schemas.domain.torrent_status import TorrentState, TorrentStatus
from app.schemas.integration.common import ClientOperationResult
from app.services.integration.download.client import DownloadClient, DownloadClientCapabilities
from app.utils.path_utils import PathMapper

logger = logging.getLogger(__name__)


class RTorrentTorrentRow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    hash: str = ""
    name: str = ""
    size_bytes: int = 0
    left_bytes: int = 0
    directory: str = ""
    base_path: str = ""
    down_rate: int = 0
    up_rate: int = 0
    ratio: int = 0
    complete: int = 0
    state: int = 0
    is_active: int = 0
    load_date: int = 0
    completed_bytes: int = 0


class RTorrentFileRow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    index: int = 0
    path: str = ""
    size_bytes: int = 0
    completed_chunks: int = 0
    size_chunks: int = 0
    priority: int = 0


class RTorrentTrackerRow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    url: str = ""
    group: int = 0
    type: int = 0
    is_enabled: int = 0

    @property
    def msg(self) -> str:
        if self.is_enabled:
            return ""
        return "tracker disabled"


class RTorrentClient(DownloadClient):
    def __init__(self, config: DownloaderConfig):
        super().__init__(config)
        self._client: httpx.AsyncClient | None = None

    def capabilities(self) -> DownloadClientCapabilities:
        return DownloadClientCapabilities(
            can_apply_categories=False,
            can_apply_tags=False,
            delete_files_requires_aethera=True,
            can_export_torrent=False,
            location_update_requires_aethera_move=True,
        )

    def _get_path_mapper(self) -> PathMapper:
        mappings = self.config.path_mappings if self.config.path_mappings else []
        return PathMapper(mappings)

    def _map_remote_to_local_path(self, remote_path: str) -> str:
        return self._get_path_mapper().to_local(remote_path)

    def _map_local_to_remote_path(self, local_path: str | None) -> str | None:
        if not local_path:
            return local_path
        return self._get_path_mapper().to_remote(local_path)

    async def _get_client(self) -> httpx.AsyncClient:
        if not self._client:
            auth = None
            if self.config.username or self.config.password:
                auth = httpx.BasicAuth(self.config.username or "", self.config.password or "")
            self._client = httpx.AsyncClient(
                auth=auth,
                timeout=httpx.Timeout(20.0, connect=5.0),
                headers={"Content-Type": "text/xml"},
            )
        return self._client

    async def _rpc(self, method: str, params: tuple[object, ...] = ()) -> object:
        if not self.config.url:
            raise ValueError("rTorrent XMLRPC url is required")
        client = await self._get_client()
        body = xmlrpc_client.dumps(params, methodname=method, allow_none=True).encode("utf-8")
        response = await client.post(self.config.url, content=body)
        response.raise_for_status()
        values, _ = xmlrpc_client.loads(response.content)
        return values[0] if values else None

    async def test_connection(self) -> bool:
        try:
            methods = await self._rpc("system.listMethods")
            return bool(methods)
        except (httpx.HTTPError, xmlrpc_client.Error, ValueError, TypeError) as exc:
            logger.error("rTorrent connection test failed: %s", exc)
            return False

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
        try:
            remote_path = self._map_local_to_remote_path(save_path)
            commands = []
            if remote_path:
                commands.append(f"d.directory.set={remote_path}")
            method = "load.raw" if is_paused else "load.raw_start"
            await self._rpc(method, ("", xmlrpc_client.Binary(torrent_data), *commands))
            info_hash = torrent_hash or self._hash_torrent(torrent_data)
            if file_priorities and info_hash:
                await self._apply_file_priorities_after_add(info_hash, file_priorities)
            if category or tags:
                logger.info("rTorrent does not support qBittorrent category/tags; ignoring category=%s tags=%s", category, tags)
            return ClientOperationResult(success=True, id=info_hash)
        except (httpx.HTTPError, xmlrpc_client.Error, ValueError, TypeError) as exc:
            logger.error("Failed to add rTorrent torrent file: %s", exc)
            return ClientOperationResult(success=False, message=str(exc), id=torrent_hash)

    async def get_torrents(self, hashes: list[str] | None = None) -> list[TorrentStatus]:
        try:
            rows = await self._load_torrent_rows()
            wanted = {item.lower() for item in hashes or []}
            statuses = [self._to_status(row) for row in rows if not wanted or row.hash.lower() in wanted]
            return statuses
        except (httpx.HTTPError, xmlrpc_client.Error, ValueError, TypeError) as exc:
            logger.error("Failed to parse rTorrent torrents: %s", exc)
            return []

    async def get_torrent_info(self, torrent_hash: str) -> DownloadInfo | None:
        rows = await self.get_torrents([torrent_hash])
        if not rows:
            return None
        status = rows[0]
        files = await self.get_torrent_files(torrent_hash)
        added_on = status.added_on or datetime.fromtimestamp(0)
        content_path = self._map_remote_to_local_path(status.save_path or "")
        try:
            row = next(item for item in await self._load_torrent_rows() if item.hash.lower() == torrent_hash.lower())
            content_path = self._map_remote_to_local_path(row.base_path or row.directory)
        except (StopIteration, httpx.HTTPError, xmlrpc_client.Error, ValueError, TypeError):
            pass
        return DownloadInfo(
            hash=status.hash,
            name=status.name,
            size=status.size,
            progress=status.progress,
            state=status.state.value,
            save_path=status.save_path or "",
            content_path=content_path,
            added_on=added_on,
            completion_on=status.completion_on,
            category=None,
            tags=[],
            files=files,
        )

    async def get_torrent_files(self, torrent_hash: str) -> list[DownloadFileInfo] | None:
        try:
            rows = await self._load_file_rows(torrent_hash)
            return [
                DownloadFileInfo(
                    index=row.index,
                    name=row.path,
                    size=row.size_bytes,
                    progress=self._file_progress(row),
                    priority=row.priority,
                    is_selected=row.priority > 0,
                )
                for row in rows
            ]
        except (httpx.HTTPError, xmlrpc_client.Error, ValueError, TypeError) as exc:
            logger.error("Failed to get rTorrent files(%s): %s", torrent_hash, exc)
            return None

    async def get_torrent_trackers(self, torrent_hash: str) -> list[dict[str, str]]:
        try:
            rows = await self._load_tracker_rows(torrent_hash)
            return [{"msg": row.msg, "message": row.msg} for row in rows if row.msg]
        except (httpx.HTTPError, xmlrpc_client.Error, ValueError, TypeError) as exc:
            logger.error("Failed to get rTorrent trackers(%s): %s", torrent_hash, exc)
            return []

    async def set_file_priority(self, torrent_hash: str, file_ids: list[int], priority: int) -> bool:
        try:
            normalized = max(0, min(int(priority), 3))
            for file_id in file_ids:
                await self._rpc("f.priority.set", (torrent_hash.upper(), int(file_id), normalized))
            await self._rpc("d.update_priorities", (torrent_hash.upper(),))
            return True
        except (httpx.HTTPError, xmlrpc_client.Error, ValueError, TypeError) as exc:
            logger.error("Failed to set rTorrent file priority: %s", exc)
            return False

    async def export_torrent(self, torrent_hash: str) -> bytes | None:
        return None

    async def recheck_torrents(self, hashes: list[str]) -> bool:
        try:
            for torrent_hash in hashes:
                await self._rpc("d.check_hash", (torrent_hash.upper(),))
            return True
        except (httpx.HTTPError, xmlrpc_client.Error, ValueError, TypeError) as exc:
            logger.error("Failed to recheck rTorrent torrents(%s): %s", hashes, exc)
            return False

    async def set_torrent_location(self, hashes: list[str], location: str) -> bool:
        try:
            remote_location = self._map_local_to_remote_path(location)
            if not remote_location:
                return False
            for torrent_hash in hashes:
                await self._rpc("d.directory.set", (torrent_hash.upper(), remote_location))
            return True
        except (httpx.HTTPError, xmlrpc_client.Error, ValueError, TypeError) as exc:
            logger.error("Failed to set rTorrent location(%s, %s): %s", hashes, location, exc)
            return False

    async def start_torrents(self, hashes: list[str]) -> bool:
        return await self._call_for_hashes("d.start", hashes)

    async def pause_torrents(self, hashes: list[str]) -> bool:
        return await self._call_for_hashes("d.stop", hashes)

    async def delete_torrent(self, torrent_hash: str, delete_files: bool = False) -> bool:
        try:
            await self._rpc("d.erase", (torrent_hash.upper(),))
            return True
        except (httpx.HTTPError, xmlrpc_client.Error, ValueError, TypeError) as exc:
            logger.error("Failed to delete rTorrent torrent: %s", exc)
            return False

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _call_for_hashes(self, method: str, hashes: list[str]) -> bool:
        try:
            for torrent_hash in hashes:
                await self._rpc(method, (torrent_hash.upper(),))
            return True
        except (httpx.HTTPError, xmlrpc_client.Error, ValueError, TypeError) as exc:
            logger.error("Failed to call rTorrent %s(%s): %s", method, hashes, exc)
            return False

    async def _load_torrent_rows(self) -> list[RTorrentTorrentRow]:
        raw = await self._rpc(
            "d.multicall2",
            (
                "",
                "main",
                "d.hash=",
                "d.name=",
                "d.size_bytes=",
                "d.left_bytes=",
                "d.directory=",
                "d.base_path=",
                "d.down.rate=",
                "d.up.rate=",
                "d.ratio=",
                "d.complete=",
                "d.state=",
                "d.is_active=",
                "d.load_date=",
                "d.completed_bytes=",
            ),
        )
        return [self._to_torrent_row(item) for item in self._rows(raw)]

    async def _load_file_rows(self, torrent_hash: str) -> list[RTorrentFileRow]:
        raw = await self._rpc(
            "f.multicall",
            (
                torrent_hash.upper(),
                "",
                "f.path=",
                "f.size_bytes=",
                "f.completed_chunks=",
                "f.size_chunks=",
                "f.priority=",
            ),
        )
        return [self._to_file_row(index, item) for index, item in enumerate(self._rows(raw))]

    async def _load_tracker_rows(self, torrent_hash: str) -> list[RTorrentTrackerRow]:
        raw = await self._rpc(
            "t.multicall",
            (
                torrent_hash.upper(),
                "",
                "t.url=",
                "t.group=",
                "t.type=",
                "t.is_enabled=",
            ),
        )
        return [self._to_tracker_row(item) for item in self._rows(raw)]

    def _rows(self, raw: object) -> list[object]:
        return list(raw or [])

    def _to_torrent_row(self, item: object) -> RTorrentTorrentRow:
        values = list(item or [])
        return RTorrentTorrentRow(
            hash=str(values[0] or "").lower() if len(values) > 0 else "",
            name=str(values[1] or "") if len(values) > 1 else "",
            size_bytes=self._to_int(values[2]) if len(values) > 2 else 0,
            left_bytes=self._to_int(values[3]) if len(values) > 3 else 0,
            directory=str(values[4] or "") if len(values) > 4 else "",
            base_path=str(values[5] or "") if len(values) > 5 else "",
            down_rate=self._to_int(values[6]) if len(values) > 6 else 0,
            up_rate=self._to_int(values[7]) if len(values) > 7 else 0,
            ratio=self._to_int(values[8]) if len(values) > 8 else 0,
            complete=self._to_int(values[9]) if len(values) > 9 else 0,
            state=self._to_int(values[10]) if len(values) > 10 else 0,
            is_active=self._to_int(values[11]) if len(values) > 11 else 0,
            load_date=self._to_int(values[12]) if len(values) > 12 else 0,
            completed_bytes=self._to_int(values[13]) if len(values) > 13 else 0,
        )

    def _to_file_row(self, index: int, item: object) -> RTorrentFileRow:
        values = list(item or [])
        return RTorrentFileRow(
            index=index,
            path=str(values[0] or "") if len(values) > 0 else "",
            size_bytes=self._to_int(values[1]) if len(values) > 1 else 0,
            completed_chunks=self._to_int(values[2]) if len(values) > 2 else 0,
            size_chunks=self._to_int(values[3]) if len(values) > 3 else 0,
            priority=self._to_int(values[4]) if len(values) > 4 else 0,
        )

    def _to_tracker_row(self, item: object) -> RTorrentTrackerRow:
        values = list(item or [])
        return RTorrentTrackerRow(
            url=str(values[0] or "") if len(values) > 0 else "",
            group=self._to_int(values[1]) if len(values) > 1 else 0,
            type=self._to_int(values[2]) if len(values) > 2 else 0,
            is_enabled=self._to_int(values[3]) if len(values) > 3 else 0,
        )

    def _to_status(self, row: RTorrentTorrentRow) -> TorrentStatus:
        progress = self._torrent_progress(row)
        save_path = self._map_remote_to_local_path(row.directory) if row.directory else row.directory
        added_on = datetime.fromtimestamp(row.load_date) if row.load_date > 0 else None
        completion_on = datetime.now() if progress >= 0.999 and row.complete else None
        return TorrentStatus(
            hash=row.hash,
            name=row.name,
            size=row.size_bytes,
            progress=progress,
            state=self._torrent_state(row),
            download_speed=row.down_rate,
            upload_speed=row.up_rate,
            ratio=float(row.ratio or 0) / 1000,
            eta=0,
            num_seeds=0,
            num_leechs=0,
            added_on=added_on,
            completion_on=completion_on,
            downloader_id=f"rtorrent_{self.config.id if self.config else 'unknown'}",
            save_path=save_path,
            category=None,
            tags=[],
        )

    def _torrent_state(self, row: RTorrentTorrentRow) -> TorrentState:
        if not row.is_active and not row.state:
            return TorrentState.PAUSED
        if row.complete:
            return TorrentState.SEEDING
        return TorrentState.DOWNLOADING

    def _torrent_progress(self, row: RTorrentTorrentRow) -> float:
        if row.size_bytes <= 0:
            return 0.0
        completed = row.completed_bytes if row.completed_bytes > 0 else max(row.size_bytes - row.left_bytes, 0)
        return min(max(float(completed) / float(row.size_bytes), 0.0), 1.0)

    def _file_progress(self, row: RTorrentFileRow) -> float:
        if row.size_chunks <= 0:
            return 0.0
        return min(max(float(row.completed_chunks) / float(row.size_chunks), 0.0), 1.0)

    def _to_int(self, value: object) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def _hash_torrent(self, torrent_data: bytes) -> str | None:
        try:
            decoded = bencodepy.decode(torrent_data)
            info = decoded.get(b"info")
            if info:
                return hashlib.sha1(bencodepy.encode(info)).hexdigest()
        except (ValueError, TypeError, KeyError):
            return None
        return None

    async def _apply_file_priorities_after_add(self, torrent_hash: str, file_priorities: list[int]) -> None:
        for attempt in range(5):
            files = await self.get_torrent_files(torrent_hash)
            if files and len(files) >= len(file_priorities):
                selected = [index for index, priority in enumerate(file_priorities) if int(priority) > 0]
                unselected = [index for index, priority in enumerate(file_priorities) if int(priority) <= 0]
                if unselected:
                    await self.set_file_priority(torrent_hash, unselected, 0)
                if selected:
                    await self.set_file_priority(torrent_hash, selected, 1)
                return
            await asyncio.sleep(0.2 * (attempt + 1))
