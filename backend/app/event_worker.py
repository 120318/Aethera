import asyncio
import logging
import signal

from app.core.logging_config import setup_logging
from app.services.config.settings_service import settings_service
from app.db.migration_guard import assert_database_schema_is_current
from app.schemas.domain.action import ActionKind, ActionSource
from app.services.application.events.dispatch import event_dispatch_service
from app.addons.registry import addon_service
from app.services.application.workflows.media_server_sync import register_media_server_sync
from app.services.audit.action_catalog import ACTION_NAME_DANMU_GENERATE, ACTION_NAME_EVENT_DISPATCH
from app.services.audit.action_service import action_service

settings_service.ensure_initialized()
setup_logging()
logger = logging.getLogger("app.event_worker")


class EventWorker:
    def __init__(self, poll_interval: float = 1.0) -> None:
        self.poll_interval = poll_interval
        self._stop_event = asyncio.Event()

    def request_stop(self) -> None:
        self._stop_event.set()

    async def run(self) -> None:
        logger.info("Event worker startup")
        assert_database_schema_is_current()
        addon_service.discover_and_register()
        register_media_server_sync()
        await event_dispatch_service.reset_running_dispatches()
        reset_count = action_service.fail_active_actions(
            kinds=[ActionKind.addon],
            sources=[ActionSource.addon],
            action_names=[ACTION_NAME_EVENT_DISPATCH.value, ACTION_NAME_DANMU_GENERATE.value],
            error="Event worker restarted while action was active",
        )
        if reset_count:
            logger.warning("Event worker reset %d interrupted addon actions", reset_count)

        try:
            while not self._stop_event.is_set():
                handled = await event_dispatch_service.run_next_queued_dispatch()
                if handled:
                    continue

                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=self.poll_interval)
                except asyncio.TimeoutError:
                    continue
        finally:
            logger.info("Event worker shutdown")


async def main() -> None:
    worker = EventWorker()
    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, worker.request_stop)
        except NotImplementedError:
            logger.warning("Signal handler unavailable for %s", sig)

    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
