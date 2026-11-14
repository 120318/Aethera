import subprocess
import sys

import pytest

from app.services.platform.domain_lock_service import DomainLockService

pytestmark = pytest.mark.health


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["download", "task"])
async def test_operation_lock_excludes_another_worker_and_releases_on_failure(tmp_path, operation):
    lock = DomainLockService(lock_root=tmp_path)
    child = """
import asyncio
import sys
from pathlib import Path
from app.services.platform.domain_lock_service import DomainLockService
async def check():
    lock = DomainLockService(lock_root=Path(sys.argv[1]))
    operation = lock.acquire_task_op('task-1') if sys.argv[2] == 'task' else lock.acquire_download_create('qb', 'HASH')
    async with operation as acquired:
        return 0 if acquired else 1
sys.exit(asyncio.run(check()))
"""

    def check_worker():
        return subprocess.run([sys.executable, "-c", child, str(tmp_path), operation], check=False, timeout=10).returncode

    with pytest.raises(RuntimeError):
        context = lock.acquire_task_op("task-1") if operation == "task" else lock.acquire_download_create("qb", "hash")
        async with context as acquired:
            assert acquired
            assert check_worker() == 1
            if operation == "task":
                assert await DomainLockService(lock_root=tmp_path).is_task_op_locked("task-1")
            async with lock.acquire_download_create("other-downloader", "hash") as independent:
                assert independent
            raise RuntimeError("worker operation failed")
    assert check_worker() == 0
    assert not await lock.is_task_op_locked("task-1")
