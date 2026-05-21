"""DiskCache-backed runtime payload cache adapter."""
import logging
import sqlite3

from app.schemas.runtime.cache_runtime import CacheStats
from app.services.platform.runtime_cache import runtime_cache

logger = logging.getLogger("app.services.cache")


class RuntimePayloadCacheService:
    def __init__(self) -> None:
        self.enabled = True

    def _generate_cache_key(self, provider: str, cache_type: str, identifier: str) -> str:
        return f"{provider}:{cache_type}:{identifier}"

    async def read(self, provider: str, cache_type: str, identifier: str):
        if not self.enabled:
            return None
        try:
            cache_key = self._generate_cache_key(provider, cache_type, identifier)
            value = runtime_cache.read(cache_key)
            if value is None:
                logger.debug("Cache miss: %s", cache_key)
                return None
            logger.debug("Cache hit: %s", cache_key)
            return value
        except (sqlite3.Error, OSError, ValueError) as e:
            logger.error("Error getting cache for %s:%s:%s: %s", provider, cache_type, identifier, str(e))
            return None

    async def get(self, provider: str, cache_type: str, identifier: str):
        return await self.read(provider, cache_type, identifier)

    async def set(
        self,
        provider: str,
        cache_type: str,
        identifier: str,
        data,
        expire_seconds: int | None = None,
    ) -> bool:
        if not self.enabled:
            return False
        if expire_seconds is None:
            expire_seconds = 86400
        try:
            cache_key = self._generate_cache_key(provider, cache_type, identifier)
            runtime_cache.set(cache_key, data, expire_seconds)
            logger.debug("Cache set: %s (expires in %d seconds)", cache_key, expire_seconds)
            return True
        except (sqlite3.Error, OSError, ValueError) as e:
            logger.error("Error setting cache for %s:%s:%s: %s", provider, cache_type, identifier, str(e))
            return False

    async def delete(self, provider: str, cache_type: str, identifier: str) -> bool:
        if not self.enabled:
            return False
        try:
            cache_key = self._generate_cache_key(provider, cache_type, identifier)
            runtime_cache.delete(cache_key)
            logger.debug("Cache deleted: %s", cache_key)
            return True
        except (sqlite3.Error, OSError, ValueError) as e:
            logger.error("Error deleting cache for %s:%s:%s: %s", provider, cache_type, identifier, str(e))
            return False

    async def clear_expired(self) -> int:
        return 0

    async def clear_all(self, provider: str | None = None) -> bool:
        if not self.enabled:
            return False
        try:
            if provider:
                removed = runtime_cache.clear_by_prefix(f"{provider}:")
                logger.info("Cleared %d cache entries for provider: %s", removed, provider)
            else:
                runtime_cache.clear()
                logger.info("Cleared all cache")
            return True
        except (sqlite3.Error, OSError, ValueError) as e:
            logger.error("Error clearing cache: %s", str(e))
            return False

    async def get_stats(self) -> CacheStats:
        if not self.enabled:
            return CacheStats(enabled=False)
        try:
            return runtime_cache.stats()
        except (sqlite3.Error, OSError, ValueError) as e:
            logger.error("Error getting cache stats: %s", str(e))
            return CacheStats(enabled=True)


cache_service = RuntimePayloadCacheService()
