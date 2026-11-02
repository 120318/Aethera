from __future__ import annotations

from app.addons.registry import (
    AddonArtifactTypeSpec,
    AddonCommandSpec,
    AddonDescriptor,
    AddonJobSpec,
    AddonProviderSpec,
    AddonRegistry,
    AddonResourceActionSpec,
    AddonSettingsSectionSpec,
)
from app.schemas.config import AddonsConfig, NotificationChannelConfig
from app.schemas.domain.action import ActionSource
from app.schemas.domain.command import (
    AddonRunCommandRecordPayload,
    AddonRunCommandRequestPayload,
    CommandCreateRequest,
    CommandInitiator,
    CommandResult,
    CommandTargetType,
    CommandType,
)
from app.schemas.domain.addon_events import MediaImportCompletedEventMeta
from app.schemas.domain.event import Event
from app.schemas.domain.media import MediaTarget
from app.services.application.commands.service import command_service
from app.services.audit.event_service import event_service
from app.services.domain.library.service import library_service
from app.services.application.workflows.danmu import danmu_application_service
from app.services.application.workflows.notifications import notification_application_service
from app.services.application.workflows.subtitles import subtitle_application_service
from app.services.platform.auth_provider_service import auth_provider_service
from app.services.platform.notification_channel_service import notification_channel_service


def _auth_enabled(config: AddonsConfig) -> bool:
    return config.auth.enabled and any(auth_provider_service.supports(provider.type) for provider in config.auth.providers)


def _notifications_enabled(config: AddonsConfig) -> bool:
    if not config.notifications.enabled:
        return False
    return any(_notification_channel_ready(channel) for channel in config.notifications.channels)


def _notification_channel_ready(channel: NotificationChannelConfig) -> bool:
    if not channel.enabled or not notification_channel_service.supports(channel.type):
        return False
    return notification_channel_service.get_channel(channel.type).is_configured(channel)


def _notification_event_patterns() -> list[str]:
    return ["*"]


def _danmu_enabled(config: AddonsConfig) -> bool:
    return config.danmu.enabled


def _subtitles_enabled(config: AddonsConfig) -> bool:
    return config.subtitles.enabled and config.subtitles.provider == "opensubtitles" and bool(config.subtitles.api_key.strip())


async def _enqueue_subtitle_event(event: Event) -> None:
    config = subtitle_application_service.config()
    if not config.auto_fill_enabled:
        return
    try:
        meta = MediaImportCompletedEventMeta.model_validate_json(event.meta)
    except ValueError:
        return
    season_number = event.media.season_number if event.media else None
    body = CommandCreateRequest(
        type=CommandType.ADDON_RUN,
        initiator=CommandInitiator.SYSTEM,
        payload=AddonRunCommandRequestPayload(
            addon_id="subtitles",
            operation_id="fill_missing",
            target=MediaTarget(media_id=meta.media_id, season_number=season_number),
            event_id=event.id,
        ),
    )
    await command_service.create_command_with_uniq_key(
        body,
        uniq_key=f"command:addon.run:subtitles:fill_missing:event:{event.id}",
        source=ActionSource.addon,
    )


async def _run_subtitle_fill_operation(payload: AddonRunCommandRecordPayload) -> CommandResult:
    result = await subtitle_application_service.fill_missing(
        payload.target.media_id,
        season_number=payload.target.season_number,
    )
    return CommandResult(
        result_count=result.installed_count,
        failed_count=result.failed_count,
    )


def _danmu_event_patterns() -> list[str]:
    return ["media.import.completed"]


def _danmu_jobs() -> list[AddonJobSpec]:
    config = danmu_application_service.config()
    if not config.enabled or not config.backfill_enabled:
        return []
    return [
        AddonJobSpec(
            id="danmu.backfill",
            name="Danmu Backfill",
            trigger="interval",
            interval_seconds=config.backfill_interval_seconds,
            max_instances=1,
            handler=danmu_application_service.run_backfill,
        )
    ]


async def _run_danmu_operation(payload: AddonRunCommandRecordPayload) -> CommandResult:
    if payload.event_id:
        event = event_service.get_event(payload.event_id)
        if event is None:
            raise ValueError("Trigger event does not exist")
        await danmu_application_service.handle_event(event)
        return CommandResult()
    if payload.task_id:
        count = await danmu_application_service.run_for_task(payload.task_id)
        return CommandResult(result_count=count)
    if payload.file_id:
        library_file = await library_service.find_file_by_id(payload.file_id)
        if library_file is None:
            raise ValueError("Library file does not exist")
        files = [library_file]
        if payload.package_root:
            media_files = await library_service.get_files_by_media(library_file.media_id)
            files = [
                item
                for item in media_files
                if item.task_id == library_file.task_id
                and library_service.matches_package_root(item, payload.package_root)
            ]
        count = await danmu_application_service.run_for_library_files(files)
        return CommandResult(result_count=count)
    raise ValueError("Danmu generation requires a task, library file, or event")


async def _enqueue_danmu_event(event: Event) -> None:
    try:
        meta = MediaImportCompletedEventMeta.model_validate_json(event.meta)
    except ValueError:
        return
    season_number = event.media.season_number if event.media else None
    body = CommandCreateRequest(
        type=CommandType.ADDON_RUN,
        initiator=CommandInitiator.SYSTEM,
        payload=AddonRunCommandRequestPayload(
            addon_id="danmu",
            operation_id="generate",
            target=MediaTarget(media_id=meta.media_id, season_number=season_number),
            event_id=event.id,
        ),
    )
    await command_service.create_command_with_uniq_key(
        body,
        uniq_key=f"command:addon.run:danmu:generate:event:{event.id}",
        source=ActionSource.addon,
    )


def register_addons(registry: AddonRegistry) -> None:
    notification_channel_service.discover_and_register()
    registry.register(
        AddonDescriptor(
            name="auth",
            display_name="Auth",
            is_enabled=_auth_enabled,
        )
    )
    registry.register(
        AddonDescriptor(
            name="notifications",
            display_name="Notifications",
            is_enabled=_notifications_enabled,
            subscribed_event_patterns=_notification_event_patterns,
            event_handler=notification_application_service.handle_event,
        )
    )
    registry.register(
        AddonDescriptor(
            name="subtitles",
            display_name="Subtitles",
            is_enabled=_subtitles_enabled,
            subscribed_event_patterns=_danmu_event_patterns,
            event_handler=_enqueue_subtitle_event,
            commands=[
                AddonCommandSpec(
                    id="fill_missing",
                    handler=_run_subtitle_fill_operation,
                )
            ],
            resource_actions=[
                AddonResourceActionSpec(
                    id="subtitles.search.library_file",
                    target_type=CommandTargetType.LIBRARY_FILE,
                    interaction_kind="dialog",
                )
            ],
            artifact_types=[AddonArtifactTypeSpec(id="subtitle")],
            providers=[AddonProviderSpec(capability="subtitles", id="opensubtitles")],
            settings_sections=[AddonSettingsSectionSpec(id="subtitles")],
        )
    )
    registry.register(
        AddonDescriptor(
            name="danmu",
            display_name="Danmu",
            is_enabled=_danmu_enabled,
            subscribed_event_patterns=_danmu_event_patterns,
            scheduled_jobs=_danmu_jobs,
            event_handler=_enqueue_danmu_event,
            commands=[
                AddonCommandSpec(
                    id="generate",
                    handler=_run_danmu_operation,
                )
            ],
            resource_actions=[
                AddonResourceActionSpec(
                    id="danmu.generate.task",
                    command_id="generate",
                    target_type=CommandTargetType.TASK,
                ),
                AddonResourceActionSpec(
                    id="danmu.generate.library_file",
                    command_id="generate",
                    target_type=CommandTargetType.LIBRARY_FILE,
                ),
            ],
            artifact_types=[
                AddonArtifactTypeSpec(id="danmu_xml"),
                AddonArtifactTypeSpec(id="danmu_ass"),
            ],
            providers=[
                AddonProviderSpec(capability="danmu", id=provider_id)
                for provider_id in ["iqiyi", "bilibili", "youku", "qq"]
            ],
            settings_sections=[AddonSettingsSectionSpec(id="danmu")],
        )
    )
