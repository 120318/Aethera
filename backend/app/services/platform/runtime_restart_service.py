from __future__ import annotations

import logging
import os
import signal
import threading
import time
from pathlib import Path

logger = logging.getLogger("app.runtime_restart")

BOOTSTRAP_PID_FILE = Path("/tmp/aethera-bootstrap.pid")


class RuntimeRestartService:
    def request_backend_restart(self, delay_seconds: float = 0.3) -> bool:
        pid = self._read_bootstrap_pid()
        if pid is None:
            logger.warning("Backend restart skipped: bootstrap pid file missing")
            return False
        threading.Thread(
            target=self._request_restart_after_delay,
            args=(pid, delay_seconds),
            daemon=True,
            name="backend-restart",
        ).start()
        return True

    def _request_restart_after_delay(self, pid: int, delay_seconds: float) -> None:
        time.sleep(delay_seconds)
        try:
            os.kill(pid, signal.SIGTERM)
            logger.info("Requested backend restart: bootstrap_pid=%s", pid)
        except ProcessLookupError:
            logger.warning("Backend restart skipped: bootstrap pid not found pid=%s", pid)
        except OSError as exc:
            logger.warning("Backend restart failed: pid=%s error=%s", pid, exc)

    def _read_bootstrap_pid(self) -> int | None:
        try:
            raw = BOOTSTRAP_PID_FILE.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        if not raw:
            return None
        try:
            return int(raw)
        except ValueError:
            logger.warning("Invalid bootstrap pid file content: %s", raw)
            return None


runtime_restart_service = RuntimeRestartService()
