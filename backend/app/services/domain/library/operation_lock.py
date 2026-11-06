from __future__ import annotations

import asyncio
import fcntl
import hashlib
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, BinaryIO

from app.core.storage_paths import get_cache_dir


class LibraryFileOperationCoordinator:
    def __init__(self, lock_root: Path | None = None, retry_interval: float = 0.05) -> None:
        self._lock_root = lock_root
        self._retry_interval = retry_interval

    @asynccontextmanager
    async def lock(self, file_ids: list[str]) -> AsyncIterator[None]:
        handles: list[BinaryIO] = []
        root = self._lock_root or get_cache_dir() / "library-file-locks"
        root.mkdir(parents=True, exist_ok=True)
        try:
            for file_id in sorted(set(file_ids)):
                lock_name = hashlib.sha256(file_id.encode("utf-8")).hexdigest()
                handle = (root / f"{lock_name}.lock").open("a+b")
                try:
                    await self._acquire(handle)
                except BaseException:
                    handle.close()
                    raise
                handles.append(handle)
            yield
        finally:
            for handle in reversed(handles):
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                handle.close()

    async def _acquire(self, handle: BinaryIO) -> None:
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return
            except BlockingIOError:
                await asyncio.sleep(self._retry_interval)


library_file_operation_coordinator = LibraryFileOperationCoordinator()
