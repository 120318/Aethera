import hashlib
import os
import time
import uuid
from datetime import datetime

import pytest

os.environ.setdefault("DATA_PATH", f"/tmp/aethera-test-data-{uuid.uuid4()}")

from app.schemas.domain.resource_search import ResourceSearchResult
from app.services.integration.torrent import TorrentService
from app.services.platform.runtime_cache import RuntimeCache


def _write_torrent_cache_file(cache_dir, name: str, *, age_seconds: int):
    path = cache_dir / name
    path.write_bytes(b"torrent")
    timestamp = time.time() - age_seconds
    os.utime(path, (timestamp, timestamp))
    return path


def test_torrent_cache_cleanup_removes_expired_files_and_ignores_other_files(tmp_path):
    service = TorrentService()
    service.torrent_cache_dir = str(tmp_path)

    expired = _write_torrent_cache_file(tmp_path, "expired.torrent", age_seconds=900)
    fresh = _write_torrent_cache_file(tmp_path, "fresh.torrent", age_seconds=10)
    other = _write_torrent_cache_file(tmp_path, "note.txt", age_seconds=900)

    result = service.cleanup_cache(max_age_seconds=60, max_files=10)

    assert result.removed_by_age == 1
    assert result.removed_by_count == 0
    assert result.failed == 0
    assert not expired.exists()
    assert fresh.exists()
    assert other.exists()


def test_torrent_cache_cleanup_trims_oldest_files_when_count_exceeds_limit(tmp_path):
    service = TorrentService()
    service.torrent_cache_dir = str(tmp_path)

    oldest = _write_torrent_cache_file(tmp_path, "oldest.torrent", age_seconds=50)
    middle = _write_torrent_cache_file(tmp_path, "middle.torrent", age_seconds=40)
    newest = _write_torrent_cache_file(tmp_path, "newest.torrent", age_seconds=30)

    result = service.cleanup_cache(max_age_seconds=3600, max_files=2)

    assert result.removed_by_age == 0
    assert result.removed_by_count == 1
    assert not oldest.exists()
    assert middle.exists()
    assert newest.exists()


def test_torrent_store_persists_by_hash_and_does_not_overwrite(tmp_path):
    service = TorrentService()
    service.torrent_store_dir = str(tmp_path)
    torrent_hash = "a" * 40

    path = service.store_blob(torrent_hash, b"first")
    second_path = service.store_blob(torrent_hash.upper(), b"second")

    assert path == second_path
    assert path and path.name == f"{torrent_hash}.torrent"
    assert service.load_stored_blob(torrent_hash) == b"first"


@pytest.mark.asyncio
async def test_torrent_cache_hit_refreshes_cache_file_mtime(tmp_path):
    service = TorrentService()
    service.torrent_cache_dir = str(tmp_path)
    detail_url = "https://example.test/details/1"
    cache_key = hashlib.md5(detail_url.encode("utf-8")).hexdigest()
    cache_path = tmp_path / f"{cache_key}.torrent"
    cache_path.write_bytes(b"d4:infod6:lengthi1e4:name8:file.txtee")
    old_timestamp = time.time() - 3600
    os.utime(cache_path, (old_timestamp, old_timestamp))

    result = ResourceSearchResult(
        id="r1",
        title="File",
        site="site",
        category="movie",
        size="1 B",
        seeders=1,
        leechers=0,
        publish_date=datetime.now(),
        download_url="https://example.test/download/1",
        detail_url=detail_url,
        result_id="site:r1",
    )

    await service.fetch_blob(result)

    assert cache_path.stat().st_mtime > old_timestamp


def test_runtime_cache_cleanup_expired_entries(tmp_path):
    cache = RuntimeCache(tmp_path)
    cache.set("indexer:search:expired", {"value": 1}, ttl=1)
    time.sleep(1.1)

    removed = cache.cleanup_expired()

    assert removed == 1
    assert not cache.has("indexer:search:expired")


def test_runtime_cache_none_ttl_survives_expired_cleanup(tmp_path):
    cache = RuntimeCache(tmp_path)
    cache.set("indexer:search:persistent", {"value": 1}, ttl=None)

    removed = cache.cleanup_expired()

    assert removed == 0
    assert cache.has("indexer:search:persistent")
