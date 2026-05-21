from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path

import httpx

from app.core.storage_paths import get_torrent_cache_dir, get_torrent_store_dir
from app.schemas.domain.resource_search import ResourceSearchResult
from app.schemas.runtime.cache_runtime import TorrentCacheCleanupResult

logger = logging.getLogger("app.services.torrent")


class TorrentService:
    def __init__(self) -> None:
        default_cache = get_torrent_cache_dir()
        default_cache.mkdir(parents=True, exist_ok=True)
        self.torrent_cache_dir = str(default_cache)
        default_store = get_torrent_store_dir()
        default_store.mkdir(parents=True, exist_ok=True)
        self.torrent_store_dir = str(default_store)

    async def fetch_blob(self, result: ResourceSearchResult) -> bytes:
        cache_identity = (result.detail_url or "").strip() or (result.download_url or "").strip()
        download_url = (result.download_url or "").strip()
        if not cache_identity or not download_url:
            raise ValueError("Missing torrent cache identity or download URL")

        cache_key = hashlib.md5(cache_identity.encode("utf-8")).hexdigest()
        cache_path = Path(self.torrent_cache_dir) / f"{cache_key}.torrent"

        if cache_path.exists():
            try:
                blob = cache_path.read_bytes()
                cache_path.touch()
                logger.debug("Torrent cache hit: detail_url=%s download_url=%s", result.detail_url, download_url)
                return blob
            except OSError as exc:
                logger.warning("Failed to read torrent cache file %s: %s", cache_path, exc)

        logger.debug("Downloading torrent payload: detail_url=%s download_url=%s", result.detail_url, download_url)
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(download_url)
                response.raise_for_status()
                blob = response.content
            cache_path.write_bytes(blob)
            return blob
        except (httpx.HTTPError, OSError) as exc:
            logger.error("Failed to download torrent from %s: %s", download_url, exc)
            raise ValueError(f"Failed to download torrent: {exc}") from exc

    def store_blob(self, torrent_hash: str | None, blob: bytes) -> Path | None:
        normalized_hash = self._normalize_hash(torrent_hash)
        if not normalized_hash or not blob:
            return None
        store_dir = Path(self.torrent_store_dir)
        store_dir.mkdir(parents=True, exist_ok=True)
        store_path = store_dir / f"{normalized_hash}.torrent"
        if store_path.exists():
            return store_path
        store_path.write_bytes(blob)
        return store_path

    def load_stored_blob(self, torrent_hash: str | None) -> bytes | None:
        normalized_hash = self._normalize_hash(torrent_hash)
        if not normalized_hash:
            return None
        store_path = Path(self.torrent_store_dir) / f"{normalized_hash}.torrent"
        if not store_path.exists() or not store_path.is_file():
            return None
        try:
            return store_path.read_bytes()
        except OSError as exc:
            logger.warning("Failed to read stored torrent file %s: %s", store_path, exc)
            return None

    def cleanup_cache(self, *, max_age_seconds: int, max_files: int) -> TorrentCacheCleanupResult:
        cache_dir = Path(self.torrent_cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        now = time.time()
        age_limit = max(0, int(max_age_seconds))
        file_limit = max(0, int(max_files))
        result = TorrentCacheCleanupResult()

        for cache_file in self._torrent_cache_files(cache_dir):
            try:
                age_seconds = now - cache_file.stat().st_mtime
                if age_seconds <= age_limit:
                    continue
                cache_file.unlink()
                result.removed_by_age += 1
            except OSError as exc:
                result.failed += 1
                logger.warning("Failed to remove expired torrent cache file %s: %s", cache_file, exc)

        remaining_files = self._torrent_cache_files(cache_dir)
        overflow = len(remaining_files) - file_limit
        if overflow <= 0:
            return result

        for cache_file in remaining_files[:overflow]:
            try:
                cache_file.unlink()
                result.removed_by_count += 1
            except OSError as exc:
                result.failed += 1
                logger.warning("Failed to trim torrent cache file %s: %s", cache_file, exc)

        return result

    def _torrent_cache_files(self, cache_dir: Path) -> list[Path]:
        files: list[Path] = []
        for item in cache_dir.iterdir():
            if not item.is_file() or item.suffix != ".torrent":
                continue
            files.append(item)
        return sorted(files, key=lambda path: path.stat().st_mtime)

    def _normalize_hash(self, torrent_hash: str | None) -> str:
        value = str(torrent_hash or "").strip().lower()
        if len(value) != 40:
            return ""
        return value if all(char in "0123456789abcdef" for char in value) else ""


torrent_service = TorrentService()
