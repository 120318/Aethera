import functools
import logging
from typing import Awaitable, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.config import AddonsConfig
from app.schemas.domain.action import ActionSource
from app.schemas.domain.command import AddonRunCommandRecordPayload, CommandResult, CommandTargetType
from app.schemas.domain.event import Event
from app.services.application.events.consumer import event_consumer_service
from app.services.config.settings_service import settings_service

logger = logging.getLogger("app.addon_service")

AddonJobHandler = Callable[[], Awaitable[None] | None]
AddonEnabledChecker = Callable[[AddonsConfig], bool]
AddonEventHandler = Callable[[Event], Awaitable[None]]
AddonEventPatternsFactory = Callable[[], list[str]]
AddonJobsFactory = Callable[[], list["AddonJobSpec"]]
AddonCommandHandler = Callable[[AddonRunCommandRecordPayload], Awaitable[CommandResult]]


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


class AddonContributionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)


class AddonCommandSpec(AddonContributionSpec):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    handler: AddonCommandHandler | None = None


class AddonResourceActionSpec(AddonContributionSpec):
    command_id: str | None = Field(default=None, min_length=1)
    target_type: CommandTargetType
    interaction_kind: str = Field(default="command", min_length=1)


class AddonArtifactTypeSpec(AddonContributionSpec):
    pass


class AddonProviderSpec(AddonContributionSpec):
    capability: str = Field(min_length=1)


class AddonSettingsSectionSpec(AddonContributionSpec):
    interaction_kind: str = Field(default="schema", min_length=1)


class AddonDescriptor(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    display_name: str = ""
    exposed: bool = True
    is_enabled: AddonEnabledChecker = _addon_enabled_default
    subscribed_event_patterns: AddonEventPatternsFactory = _empty_event_patterns
    scheduled_jobs: AddonJobsFactory = _empty_addon_jobs
    event_handler: AddonEventHandler | None = None
    commands: list[AddonCommandSpec] = Field(default_factory=list)
    resource_actions: list[AddonResourceActionSpec] = Field(default_factory=list)
    artifact_types: list[AddonArtifactTypeSpec] = Field(default_factory=list)
    providers: list[AddonProviderSpec] = Field(default_factory=list)
    settings_sections: list[AddonSettingsSectionSpec] = Field(default_factory=list)


class AddonRegistry:
    def __init__(self) -> None:
        self._addons: list[AddonDescriptor] = []
        self._command_owners: dict[str, str] = {}
        self._resource_action_owners: dict[str, str] = {}
        self._artifact_type_owners: dict[str, str] = {}
        self._provider_owners: dict[str, str] = {}
        self._settings_section_owners: dict[str, str] = {}

    def register(self, addon: AddonDescriptor) -> None:
        existing = self.get_addon(addon.name)
        if existing:
            logger.debug("Addon already registered: %s", addon.name)
            return
        self._validate_contributions(addon)
        self._addons.append(addon)
        self._claim_contributions(addon)

        patterns = addon.subscribed_event_patterns() or []
        if addon.event_handler is not None and patterns:
            event_consumer_service.register(
                name=addon.name,
                patterns=patterns,
                handler=functools.partial(self._handle_addon_event, addon.name),
                source_type=ActionSource.addon,
            )
        logger.debug("Registered addon: %s", addon.name)

    def _validate_contributions(self, addon: AddonDescriptor) -> None:
        command_ids = {item.id for item in addon.commands}
        for action in addon.resource_actions:
            if action.command_id is not None and action.command_id not in command_ids:
                raise ValueError(f"Resource action {action.id} in addon {addon.name} references " f"undeclared command {action.command_id}")
        self._validate_ids(addon.name, "command", [item.id for item in addon.commands], self._command_owners)
        self._validate_ids(
            addon.name,
            "resource action",
            [item.id for item in addon.resource_actions],
            self._resource_action_owners,
        )
        self._validate_ids(
            addon.name,
            "artifact type",
            [item.id for item in addon.artifact_types],
            self._artifact_type_owners,
        )
        self._validate_ids(
            addon.name,
            "provider",
            [self._provider_key(item) for item in addon.providers],
            self._provider_owners,
        )
        self._validate_ids(
            addon.name,
            "settings section",
            [item.id for item in addon.settings_sections],
            self._settings_section_owners,
        )

    @staticmethod
    def _validate_ids(
        addon_name: str,
        contribution_type: str,
        contribution_ids: list[str],
        owners: dict[str, str],
    ) -> None:
        seen: set[str] = set()
        for contribution_id in contribution_ids:
            if contribution_id in seen:
                raise ValueError(f"Duplicate {contribution_type} id in addon {addon_name}: {contribution_id}")
            seen.add(contribution_id)
            owner = owners.get(contribution_id)
            if owner is not None:
                raise ValueError(f"Duplicate {contribution_type} id {contribution_id}: owned by {owner} and {addon_name}")

    def _claim_contributions(self, addon: AddonDescriptor) -> None:
        self._claim_ids(addon.name, [item.id for item in addon.commands], self._command_owners)
        self._claim_ids(addon.name, [item.id for item in addon.resource_actions], self._resource_action_owners)
        self._claim_ids(addon.name, [item.id for item in addon.artifact_types], self._artifact_type_owners)
        self._claim_ids(
            addon.name,
            [self._provider_key(item) for item in addon.providers],
            self._provider_owners,
        )
        self._claim_ids(addon.name, [item.id for item in addon.settings_sections], self._settings_section_owners)

    @staticmethod
    def _claim_ids(addon_name: str, contribution_ids: list[str], owners: dict[str, str]) -> None:
        for contribution_id in contribution_ids:
            owners[contribution_id] = addon_name

    @staticmethod
    def _provider_key(provider: AddonProviderSpec) -> str:
        return f"{provider.capability}:{provider.id}"

    async def _handle_addon_event(self, addon_name: str, event: Event) -> None:
        addon = self.get_addon(addon_name)
        if not addon or addon.event_handler is None or not self.is_addon_enabled(addon_name):
            return
        await addon.event_handler(event)

    def discover_and_register(self) -> None:
        try:
            from app.addons.descriptors import register_addons

            register_addons(self)
        except (ImportError, RuntimeError) as exc:
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

    def get_command(self, addon_name: str, command_id: str) -> AddonCommandSpec | None:
        addon = self.get_addon(addon_name)
        if addon is None:
            return None
        for command in addon.commands:
            if command.id == command_id:
                return command
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
