from __future__ import annotations

from typing import TYPE_CHECKING

from app.schemas.constants.event_types import EventTypes
from app.schemas.domain.action import ActionActor, ActionKind, ActionName, ActionSource, ActionStatus, ActionTargetType, ActionTrigger
from app.schemas.domain.action_meta import TaskStorageMigrationActionMeta
from app.schemas.domain.addon_events import DownloadTaskEventMeta
from app.schemas.domain.download import TaskData
from app.schemas.domain.event import EventActor, EventEntityRef, EventLevel, EventSource, MediaEventCreate
from app.schemas.domain.task_storage_migration import TaskStorageMigration
from app.services.audit.action_service import action_service
from app.services.audit.event_service import event_service

if TYPE_CHECKING:
    from app.services.domain.download.downloader_change import TaskDownloaderChangePreview


def create_migration_action(task: TaskData, migration: TaskStorageMigration) -> str:
    action_id = f"storage-migration:{migration.id}"
    media = task.context.media
    action = action_service.create_action(
        action_id=action_id,
        kind=ActionKind.command,
        action_name=ActionName.task_storage_change.value,
        status=ActionStatus.running,
        actor=ActionActor.user,
        trigger=ActionTrigger.manual,
        source=ActionSource.api,
        target_type=ActionTargetType.task,
        target_id=task.id,
        media_id=task.media_id,
        task_id=task.id,
        correlation_id=migration.id,
        started_at=migration.updated_at,
        meta=TaskStorageMigrationActionMeta(
            migration_id=migration.id,
            target_label=f"{media.title.strip()} ({media.year})",
            source_downloader_id=migration.source_downloader_id,
            target_downloader_id=migration.target_downloader_id,
            source_directory_id=migration.source_directory_id,
            target_directory_id=migration.target_directory_id,
        ),
    )
    return action.id


def mark_migration_action_completed(migration: TaskStorageMigration) -> None:
    if migration.action_id:
        action_service.mark_completed(migration.action_id)


def mark_migration_action_failed(migration: TaskStorageMigration, reason: str) -> None:
    if migration.action_id:
        action_service.mark_failed(migration.action_id, error=reason)


def emit_change_started(task: TaskData, migration: TaskStorageMigration) -> None:
    event_service.emit_media(
        MediaEventCreate(
            type=EventTypes.DOWNLOAD_TASK_STORAGE_CHANGE_STARTED,
            message_params=_migration_message_params(migration),
            media=task.context.media,
            task_id=task.id,
            actor=EventActor.user,
            source=EventSource.base,
            entities=_build_event_entities(task),
            action_id=migration.action_id,
        ),
        meta=_build_event_meta(task),
    )


def emit_change_succeeded(task: TaskData, migration: TaskStorageMigration) -> None:
    event_service.emit_media(
        MediaEventCreate(
            type=EventTypes.DOWNLOAD_TASK_STORAGE_CHANGED,
            message_params=_migration_message_params(migration),
            media=task.context.media,
            task_id=task.id,
            actor=EventActor.user,
            source=EventSource.base,
            entities=_build_event_entities(task),
            action_id=migration.action_id,
        ),
        meta=_build_event_meta(task),
    )


def emit_change_failed(task: TaskData, preview: TaskDownloaderChangePreview, reason: str) -> None:
    event_service.emit_media(
        MediaEventCreate(
            type=EventTypes.DOWNLOAD_TASK_STORAGE_CHANGE_FAILED,
            level=EventLevel.error,
            message_params={
                "reason": reason,
                "blockers": ",".join(preview.blockers),
                "source_downloader_id": preview.current_downloader_id or task.downloader_id or "",
                "target_downloader_id": preview.target_downloader_id or "",
                "source_directory_id": preview.current_directory_id or task.context.directory_id or "",
                "target_directory_id": preview.target_directory_id or "",
                "source_save_path": preview.current_save_path or task.save_path or "",
                "target_save_path": preview.target_save_path or "",
                "move_content": str(preview.move_content).lower(),
            },
            media=task.context.media,
            task_id=task.id,
            actor=EventActor.user,
            source=EventSource.base,
            entities=_build_event_entities(task),
        ),
        meta=_build_event_meta(task),
    )


def emit_migration_failed(task: TaskData, migration: TaskStorageMigration, reason: str) -> None:
    event_service.emit_media(
        MediaEventCreate(
            type=EventTypes.DOWNLOAD_TASK_STORAGE_CHANGE_FAILED,
            level=EventLevel.error,
            message_params={"reason": reason, "blockers": ",".join(migration.blockers), **_migration_message_params(migration)},
            media=task.context.media,
            task_id=task.id,
            actor=EventActor.user,
            source=EventSource.base,
            entities=_build_event_entities(task),
            action_id=migration.action_id,
        ),
        meta=_build_event_meta(task),
    )


def _migration_message_params(migration: TaskStorageMigration) -> dict[str, str]:
    return {
        "source_downloader_id": migration.source_downloader_id,
        "target_downloader_id": migration.target_downloader_id,
        "source_directory_id": migration.source_directory_id,
        "target_directory_id": migration.target_directory_id,
        "source_save_path": migration.source_save_path,
        "target_save_path": migration.target_save_path,
        "move_content": str(migration.move_content).lower(),
        "cleanup_source_torrent": str(migration.cleanup_source_torrent).lower(),
    }


def _build_event_meta(task: TaskData) -> DownloadTaskEventMeta:
    return DownloadTaskEventMeta(
        task_id=task.id,
        media_id=task.media_id,
        status=task.status,
        downloader_id=task.downloader_id,
        resource_title=task.context.resource_title,
        torrent_name=task.metadata.name if task.metadata else None,
        torrent_hash=task.torrent_hash,
        progress=task.progress,
        selected_files=list(task.context.selected_files or []),
        total_files=len(task.metadata.files) if task.metadata and task.metadata.files else None,
    )


def _build_event_entities(task: TaskData) -> list[EventEntityRef]:
    return [
        EventEntityRef(type="task", id=task.id),
        EventEntityRef(type="media", id=str(task.media_id)),
    ]
