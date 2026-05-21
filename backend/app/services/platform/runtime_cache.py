from __future__ import annotations

import logging
from pathlib import Path
from typing import TypeVar, cast

from diskcache import Cache
from pydantic import BaseModel

from app.core.storage_paths import get_cache_dir
from app.db.sql.serialization import to_jsonable
from app.schemas.runtime.cache_runtime import CacheProviderStats, CacheStats

logger = logging.getLogger("app.services.platform.runtime_cache")
CacheValue = TypeVar("CacheValue")


class RuntimeCache:
    def __init__(self, directory: Path | None = None) -> None:
        cache_dir = directory or get_cache_dir()
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.directory = cache_dir
        self._cache = Cache(str(cache_dir))

    def get(self, key: str):
        if key not in self._cache:
            return None
        return self._cache[key]

    def read(self, key: str):
        if key not in self._cache:
            return None
        return self._cache[key]

    def set(self, key: str, value, ttl: int | None) -> None:
        self._cache.set(key, to_jsonable(value), expire=ttl)

    def delete(self, key: str) -> bool:
        return bool(self._cache.pop(key, default=None) is not None)

    def has(self, key: str) -> bool:
        return key in self._cache

    def clear(self) -> None:
        self._cache.clear()

    def cleanup_expired(self) -> int:
        return int(self._cache.expire())

    def clear_by_prefix(self, prefix: str) -> int:
        removed = 0
        for key in list(self._cache.iterkeys()):
            if type(key) is not str or not key.startswith(prefix):
                continue
            self._cache.pop(key, default=None)
            removed += 1
        return removed

    def items_by_prefix(self, prefix: str):
        items = []
        for key in self._cache.iterkeys():
            if type(key) is not str or not key.startswith(prefix):
                continue
            try:
                items.append((key, self._cache[key]))
            except KeyError:
                logger.debug("Skipping expired runtime cache key during prefix scan: %s", key)
        return items

    def stats(self) -> CacheStats:
        total_entries = 0
        provider_stats = {}
        for key in self._cache.iterkeys():
            if type(key) is not str:
                continue
            total_entries += 1
            parts = key.split(":", 1)
            provider = parts[0] if parts else "unknown"
            bucket = provider_stats.setdefault(provider, CacheProviderStats())
            bucket.total += 1
        return CacheStats(
            enabled=True,
            directory=str(self.directory),
            total_entries=total_entries,
            provider_stats=provider_stats,
        )


runtime_cache = RuntimeCache()
