from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CacheProviderStats(BaseModel):
    model_config = ConfigDict(extra="ignore")

    total: int = 0


class CacheStats(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool = True
    directory: str = ""
    total_entries: int = 0
    provider_stats: dict[str, CacheProviderStats] = Field(default_factory=dict)


class TorrentCacheCleanupResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    removed_by_age: int = 0
    removed_by_count: int = 0
    failed: int = 0

    @property
    def total_removed(self) -> int:
        return self.removed_by_age + self.removed_by_count


class CacheCleanupResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    expired_runtime_entries: int = 0
    torrent: TorrentCacheCleanupResult = Field(default_factory=TorrentCacheCleanupResult)
