import subprocess
import sys

import pytest

from app.services.platform.domain_lock_service import DomainLockService

pytestmark = pytest.mark.health


@pytest.mark.asyncio
async def test_download_lock_excludes_another_worker_and_releases_on_failure(tmp_path):
    lock = DomainLockService(download_lock_root=tmp_path)
    child = """
import asyncio
import sys
from pathlib import Path
from app.services.platform.domain_lock_service import DomainLockService
async def check():
    lock = DomainLockService(download_lock_root=Path(sys.argv[1]))
    async with lock.acquire_download_create('qb', 'HASH') as acquired:
        return 0 if acquired else 1
sys.exit(asyncio.run(check()))
"""

    def check_worker():
        return subprocess.run([sys.executable, "-c", child, str(tmp_path)], check=False, timeout=10).returncode

    with pytest.raises(RuntimeError):
        async with lock.acquire_download_create("qb", "hash") as acquired:
            assert acquired
            assert check_worker() == 1
            async with lock.acquire_download_create("other-downloader", "hash") as independent:
                assert independent
            raise RuntimeError("worker operation failed")
    assert check_worker() == 0
