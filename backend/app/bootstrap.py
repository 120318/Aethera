import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

from app.services.config.settings_service import settings_service
from app.core.logging_config import setup_logging

settings_service.ensure_initialized()
setup_logging()
logger = logging.getLogger("app.bootstrap")

BOOTSTRAP_PID_FILE = Path("/tmp/aethera-bootstrap.pid")


class BackendBootstrap:
    def __init__(self) -> None:
        config = settings_service.ensure_initialized()
        self.mode = self._resolve_mode(config)
        self.hot_reload = self._resolve_hot_reload(self.mode)
        self.host = os.getenv("BACKEND_HOST", "0.0.0.0")
        self.port = os.getenv("BACKEND_PORT", "3001")
        self.uvicorn_workers = max(1, int(os.getenv("UVICORN_WORKERS", "4")))
        self.command_worker_count = 1
        self._processes: List[subprocess.Popen] = []
        self._stopping = False

    @staticmethod
    def _resolve_mode(config) -> str:
        backend_mode = (os.getenv("BACKEND_MODE", "prod") or "prod").strip().lower()
        return backend_mode if backend_mode in {"dev", "prod"} else "prod"

    @staticmethod
    def _resolve_hot_reload(mode: str) -> bool:
        raw = (
            os.getenv("AETHERA_BACKEND_HOT_RELOAD")
            or os.getenv("AETHERA_DEV_HOT_RELOAD")
            or os.getenv("BACKEND_HOT_RELOAD")
        )
        if raw is None:
            return mode == "dev"
        return raw.strip().lower() in {"1", "true", "yes", "on"}

    def _build_server_command(self) -> List[str]:
        command = [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            self.host,
            "--port",
            self.port,
        ]
        if self.hot_reload:
            command.extend(["--reload", "--reload-dir", "/app/app"])
        else:
            command.extend(["--workers", str(self.uvicorn_workers)])
        return command

    def _build_command_worker_command(self) -> List[str]:
        if self.hot_reload:
            return [sys.executable, "-m", "app.dev_command_worker"]
        return [sys.executable, "-m", "app.command_worker"]

    def _build_scheduler_command(self) -> List[str]:
        if self.hot_reload:
            return [sys.executable, "-m", "app.dev_scheduler_worker"]
        return [sys.executable, "-m", "app.scheduler_worker"]

    def _build_event_worker_command(self) -> List[str]:
        if self.hot_reload:
            return [sys.executable, "-m", "app.dev_event_worker"]
        return [sys.executable, "-m", "app.event_worker"]

    def _start_process(self, command: List[str], name: str) -> subprocess.Popen:
        logger.info("Starting %s: %s", name, " ".join(command))
        process = subprocess.Popen(command)
        process._bootstrap_name = name  # type: ignore[attr-defined]
        self._processes.append(process)
        return process

    def _stop_processes(self) -> None:
        if self._stopping:
            return
        self._stopping = True

        for process in self._processes:
            if process.poll() is None:
                logger.info("Stopping %s pid=%s", getattr(process, "_bootstrap_name", "process"), process.pid)
                process.terminate()

        deadline = time.time() + 10
        for process in self._processes:
            if process.poll() is not None:
                continue
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            try:
                process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                continue

        for process in self._processes:
            if process.poll() is None:
                logger.warning("Killing %s pid=%s", getattr(process, "_bootstrap_name", "process"), process.pid)
                process.kill()
                process.wait()

    def _handle_signal(self, signum, _frame) -> None:
        logger.info("Received signal %s, shutting down backend bootstrap", signum)
        self._stop_processes()
        raise SystemExit(0)

    def run(self) -> int:
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)
        BOOTSTRAP_PID_FILE.write_text(str(os.getpid()), encoding="utf-8")

        self._start_process(self._build_server_command(), "web")
        for worker_index in range(self.command_worker_count):
            self._start_process(self._build_command_worker_command(), f"command-worker-{worker_index + 1}")
        self._start_process(self._build_event_worker_command(), "event-worker")
        self._start_process(self._build_scheduler_command(), "scheduler")

        try:
            while True:
                for process in self._processes:
                    return_code = process.poll()
                    if return_code is None:
                        continue
                    logger.error(
                        "%s exited unexpectedly with code %s",
                        getattr(process, "_bootstrap_name", "process"),
                        return_code,
                    )
                    self._stop_processes()
                    return return_code or 0
                time.sleep(1)
        finally:
            self._stop_processes()
            try:
                BOOTSTRAP_PID_FILE.unlink(missing_ok=True)
            except OSError:
                logger.warning("Failed to remove bootstrap pid file: %s", BOOTSTRAP_PID_FILE)


def main() -> None:
    bootstrap = BackendBootstrap()
    exit_code = bootstrap.run()
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
