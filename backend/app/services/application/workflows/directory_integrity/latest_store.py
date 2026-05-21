from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

from app.schemas.runtime.directory_integrity import DirectoryIntegrityResult

logger = logging.getLogger("app.services.directory_integrity.latest_store")

LATEST_RESULT_PATH = Path(
    os.getenv("AETHERA_DIRECTORY_INTEGRITY_LATEST_PATH", "/config/cache/directory_integrity_latest.json")
)


class DirectoryIntegrityLatestStore:
    def __init__(self) -> None:
        self.path = LATEST_RESULT_PATH

    async def load(self) -> DirectoryIntegrityResult | None:
        if not self.path.exists():
            return None
        try:
            data = await asyncio.to_thread(self.path.read_text, encoding="utf-8")
            return DirectoryIntegrityResult.model_validate(json.loads(data))
        except (OSError, ValueError) as exc:
            logger.warning("Failed to load latest directory integrity result: %s", exc)
            return None

    async def save(self, result: DirectoryIntegrityResult) -> None:
        await asyncio.to_thread(self.path.parent.mkdir, parents=True, exist_ok=True)
        payload = result.model_dump_json(indent=2)
        await asyncio.to_thread(self.path.write_text, payload, encoding="utf-8")
