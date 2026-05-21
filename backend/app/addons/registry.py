import functools
import logging
from typing import Awaitable, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.config import AddonsConfig
from app.schemas.domain.action import ActionSource
from app.schemas.domain.event import Event
from app.services.application.events.consumer import event_consumer_service
from app.services.config.settings_service import settings_service

logger = logging.getLogger("app.addon_service")

AddonJobHandler = Callable[[], Awaitable[None] | None]
AddonEnabledChecker = Callable[[AddonsConfig], bool]
AddonEventHandler = Callable[[Event], Awaitable[None]]
AddonEventPatternsFactory = Callable[[], list[str]]
AddonJobsFactory = Callable[[], list["AddonJobSpec"]]


def _addon_enabled_default(_config: AddonsConfig) -> bool:
    return True


def _empty_event_patterns() -> list[str]:
    return []


def _empty_addon_jobs() -> list["AddonJobSpec"]:
    return []


class CronSpec(BaseModel):
    year: str | None = None
    month: str | None = None
    day: str | None = None
    week: str | None = None
    day_of_week: str | None = None
    hour: str | None = None
    minute: str | None = None
    second: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    timezone: str | None = None

    def present_items(self) -> list[tuple[str, str]]:
        items: list[tuple[str, str]] = []
        for key, value in self.model_dump(mode="python").items():
            if value is None or value == "":
                continue
            items.append((key, value))
        return items


class AddonJobSpec(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str
    name: str
    trigger: Literal["interval", "cron"]
    handler: AddonJobHandler
    interval_seconds: int | None = None
    interval_hours: int | None = None
    cron: CronSpec = Field(default_factory=CronSpec)
    max_instances: int = 1


class AddonDescriptor(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    display_name: str = ""
    exposed: bool = True
    is_enabled: AddonEnabledChecker = _addon_enabled_default
    subscribed_event_patterns: AddonEventPatternsFactory = _empty_event_patterns
    scheduled_jobs: AddonJobsFactory = _empty_addon_jobs
    event_handler: AddonEventHandler | None = None


class AddonRegistry:
    def __init__(self) -> None:
        self._addons: list[AddonDescriptor] = []

    def register(self, addon: AddonDescriptor) -> None:
        existing = self.get_addon(addon.name)
        if existing:
            logger.debug("Addon already registered: %s", addon.name)
            return
        self._addons.append(addon)

        patterns = addon.subscribed_event_patterns() or []
        if addon.event_handler is not None and patterns:
            event_consumer_service.register(
                name=addon.name,
                patterns=patterns,
                handler=functools.partial(self._handle_addon_event, addon.name),
                source_type=ActionSource.addon,
            )
        logger.debug("Registered addon: %s", addon.name)

    async def _handle_addon_event(self, addon_name: str, event: Event) -> None:
        addon = self.get_addon(addon_name)
        if not addon or addon.event_handler is None or not self.is_addon_enabled(addon_name):
            return
        await addon.event_handler(event)

    def discover_and_register(self) -> None:
        try:
            from app.addons.descriptors import register_addons

            register_addons(self)
        except (ImportError, RuntimeError, ValueError) as exc:
            logger.error("Failed to load addon descriptors: %s", exc)

    def list_addons(self) -> list[AddonDescriptor]:
        return list(self._addons)

    def list_addon_jobs(self) -> list[AddonJobSpec]:
        jobs: list[AddonJobSpec] = []
        for addon in self._addons:
            try:
                for job in addon.scheduled_jobs() or []:
                    jobs.append(job)
            except (AttributeError, RuntimeError, ValueError):
                continue
        return jobs

    def get_addon(self, name: str) -> AddonDescriptor | None:
        for addon in self._addons:
            if addon.name == name:
                return addon
        return None

    def is_addon_enabled(self, name: str) -> bool:
        addon = self.get_addon(name)
        if addon is None:
            return False
        return addon.is_enabled(settings_service.get_addons_config())

    def should_dispatch_event(self, event_type: str) -> bool:
        try:
            normalized = event_type.value
        except AttributeError:
            normalized = str(event_type or "")
        return not str(normalized).startswith("addon.run.")


addon_service = AddonRegistry()
