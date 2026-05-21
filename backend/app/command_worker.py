import asyncio
import logging
import signal

from app.core.logging_config import setup_logging
from app.services.config.settings_service import settings_service
from app.db.migration_guard import assert_database_schema_is_current
from app.services.application.commands.service import command_service
from app.addons.registry import addon_service
from app.services.application.workflows.media_server_sync import register_media_server_sync
from app.services.domain.subscription.repair_service import subscription_repair_service

settings_service.ensure_initialized()
setup_logging()
logger = logging.getLogger("app.command_worker")


class CommandWorker:
    def __init__(self, poll_interval: float = 1.0):
        self.poll_interval = poll_interval
        self._stop_event = asyncio.Event()

    def request_stop(self) -> None:
        self._stop_event.set()

    async def run(self) -> None:
        logger.info("Command worker startup")
        assert_database_schema_is_current()
        await subscription_repair_service.repair_missing_media_snapshots()
        addon_service.discover_and_register()
        register_media_server_sync()
        await command_service.reset_running_commands()

        try:
            while not self._stop_event.is_set():
                handled = await command_service.run_next_queued_command()
                if handled:
                    continue

                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=self.poll_interval)
                except asyncio.TimeoutError:
                    continue
        finally:
            logger.info("Command worker shutdown")


async def main() -> None:
    worker = CommandWorker()
    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, worker.request_stop)
        except NotImplementedError:
            logger.warning("Signal handler unavailable for %s", sig)

    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
