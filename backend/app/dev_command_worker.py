import logging
import os
import subprocess
import sys
import time
from pathlib import Path

from watchfiles import run_process

from app.core.logging_config import setup_logging
from app.services.config.settings_service import settings_service

settings_service.ensure_initialized()
setup_logging()
logger = logging.getLogger("app.dev_command_worker")
logging.getLogger("watchfiles").setLevel(logging.WARNING)
logging.getLogger("watchfiles.main").setLevel(logging.WARNING)
logging.getLogger("watchfiles.watcher").setLevel(logging.WARNING)


def _run_worker_process() -> None:
    command = [sys.executable, "-m", "app.command_worker"]
    while True:
        try:
            result = subprocess.run(command, check=False)
        except KeyboardInterrupt:
            return
        except InterruptedError:
            return

        if result.returncode in [0, -15]:
            return

        logger.warning("Worker process exited with code %s", result.returncode)
        logger.warning("Restarting worker process in 1s")
        time.sleep(1)


def main() -> None:
    watch_path = os.getenv("BACKEND_RELOAD_DIR", "/app/app")
    logger.info("Starting dev command worker reloader for %s", watch_path)
    run_process(Path(watch_path), target=_run_worker_process)


if __name__ == "__main__":
    main()
