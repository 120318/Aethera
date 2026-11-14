from __future__ import annotations

import asyncio
import fcntl
import hashlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from app.core.storage_paths import get_cache_dir
from app.schemas.media_id import MediaID


class DomainLockService:
    def __init__(self, lock_root: Path | None = None) -> None:
        self._registry_lock = asyncio.Lock()
        self._active_keys: set[str] = set()
        self._lock_root = lock_root

    @asynccontextmanager
    async def acquire_media_acquire(self, media_id: MediaID) -> AsyncIterator[bool]:
        async with self._acquire(f"media-acquire:{media_id}") as acquired:
            yield acquired

    @asynccontextmanager
    async def acquire_task_op(self, task_id: str) -> AsyncIterator[bool]:
        async with self._acquire_cross_process(f"task-op:{task_id}") as acquired:
            yield acquired

    async def is_task_op_locked(self, task_id: str) -> bool:
        async with self.acquire_task_op(task_id) as acquired:
            return not acquired

    @asynccontextmanager
    async def acquire_library_file_op(self, file_id: str) -> AsyncIterator[bool]:
        async with self._acquire(f"library-file-op:{file_id}") as acquired:
            yield acquired

    @asynccontextmanager
    async def acquire_media_delete(self, media_id: MediaID, mode: str) -> AsyncIterator[bool]:
        async with self._acquire(f"media-delete:{media_id}:{mode}") as acquired:
            yield acquired

    @asynccontextmanager
    async def acquire_profile_refresh(self, media_id: MediaID, season_number: int | None = None) -> AsyncIterator[bool]:
        season_part = f":season={season_number}" if season_number is not None and season_number > 0 else ":season=all"
        async with self._acquire(f"profile-refresh:{media_id}{season_part}") as acquired:
            yield acquired

    @asynccontextmanager
    async def acquire_download_create(self, downloader_id: str, torrent_hash: str) -> AsyncIterator[bool]:
        async with self._acquire_cross_process(f"download-create:{downloader_id}:{torrent_hash.lower()}") as acquired:
            yield acquired

    @asynccontextmanager
    async def _acquire_cross_process(self, key: str) -> AsyncIterator[bool]:
        # API edits and command-worker writes share task and downloader state.
        # A file lock, unlike the local registry, also excludes other processes and
        # is released by the OS if the worker exits; no lease timeout can expire mid-write.
        root = self._lock_root or get_cache_dir() / "domain-operation-locks"
        root.mkdir(parents=True, exist_ok=True)
        lock_name = hashlib.sha256(key.encode("utf-8")).hexdigest()
        with (root / f"{lock_name}.lock").open("a+b") as handle:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                yield False
                return
            try:
                yield True
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    @asynccontextmanager
    async def acquire_scheduler_job(self, job_name: str) -> AsyncIterator[bool]:
        async with self._acquire(f"scheduler:{job_name}") as acquired:
            yield acquired

    @asynccontextmanager
    async def acquire_storage_ops(self, keys: list[str]) -> AsyncIterator[bool]:
        normalized = sorted({key for key in keys if key})
        acquired_keys: list[str] = []
        acquired = True
        try:
            for key in normalized:
                lock_key = f"storage-op:{key}"
                if not await self._try_mark_acquired(lock_key):
                    acquired = False
                    break
                acquired_keys.append(lock_key)
            yield acquired
        finally:
            for key in acquired_keys:
                await self._release(key)

    @asynccontextmanager
    async def _acquire(self, key: str) -> AsyncIterator[bool]:
        acquired = await self._try_mark_acquired(key)
        try:
            yield acquired
        finally:
            if acquired:
                await self._release(key)

    async def _try_mark_acquired(self, key: str) -> bool:
        async with self._registry_lock:
            if key in self._active_keys:
                return False
            self._active_keys.add(key)
            return True

    async def _release(self, key: str) -> None:
        async with self._registry_lock:
            self._active_keys.discard(key)


domain_lock_service = DomainLockService()
