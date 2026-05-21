from pathlib import Path

from app.schemas.domain.addon_events import DanmuGenerateEventMeta, MediaServerSyncEventMeta
from app.schemas.domain.event import EventActor, EventEntityRef, EventLevel, EventSource, EventType, MediaEventCreate
from app.schemas.domain.media import MediaFullInfo
from app.schemas.domain.media_server_sync import MediaServerSyncTargetFile
from app.services.audit.event_service import event_service
from app.services.domain.alerts.workflow_alerts import (
    raise_danmu_alert,
    raise_media_server_sync_alert,
    resolve_danmu_alert,
    resolve_media_server_sync_alert,
)


def emit_danmu_generate_event(
    event_type: EventType,
    media: MediaFullInfo,
    video_path: Path,
    episode_number: int | None,
    action_id: str,
    task_id: str | None,
    *,
    provider: str | None = None,
    xml_path: Path | None = None,
    ass_path: Path | None = None,
    error: str = "",
    error_key: str | None = None,
) -> None:
    if event_type == EventType.DANMU_GENERATE_FAILED:
        raise_danmu_alert(
            media=media,
            video_path=video_path,
            action_id=action_id,
            task_id=task_id,
            provider=provider,
            error=error,
            error_key=error_key,
        )
    elif event_type == EventType.DANMU_GENERATE_COMPLETED:
        resolve_danmu_alert(video_path)
    event_service.emit_media(
        MediaEventCreate(
            type=event_type,
            level=EventLevel.error if event_type == EventType.DANMU_GENERATE_FAILED else EventLevel.info,
            media=media,
            task_id=task_id,
            actor=EventActor.system,
            source=EventSource.addon,
            action_id=action_id,
            entities=[
                EventEntityRef(type="media", id=str(media.media_id)),
                EventEntityRef(type="file", id=str(video_path)),
            ],
        ),
        meta=DanmuGenerateEventMeta(
            media_id=media.media_id,
            video_path=str(video_path),
            episode_number=episode_number,
            provider=provider,
            xml_path=str(xml_path) if xml_path else None,
            ass_path=str(ass_path) if ass_path else None,
            error=error,
            error_key=error_key,
        ),
    )


def emit_media_server_sync_events(
    event_type: EventType,
    media: MediaFullInfo,
    anchor_file: str,
    transfer_results: list[MediaServerSyncTargetFile],
    media_server_id: str,
    *,
    trigger: str,
    task_id: str | None = None,
    error: str = "",
) -> None:
    target_paths = _sync_event_paths(anchor_file, transfer_results)
    for path in target_paths:
        if event_type == EventType.MEDIA_SERVER_SYNC_FAILED:
            raise_media_server_sync_alert(
                media=media,
                file_path=path,
                media_server_id=media_server_id,
                task_id=task_id,
                error=error,
            )
        elif event_type == EventType.MEDIA_SERVER_SYNC_COMPLETED:
            resolve_media_server_sync_alert(media=media, file_path=path, media_server_id=media_server_id)
        event_service.emit_media(
            MediaEventCreate(
                type=event_type,
                level=EventLevel.error if event_type == EventType.MEDIA_SERVER_SYNC_FAILED else EventLevel.info,
                media=media,
                task_id=task_id,
                actor=EventActor.system,
                source=EventSource.base,
                entities=[
                    EventEntityRef(type="media", id=str(media.media_id)),
                    EventEntityRef(type="file", id=path),
                ],
            ),
            meta=MediaServerSyncEventMeta(
                media_id=media.media_id,
                media_server_id=media_server_id,
                file_path=path,
                file_count=len(target_paths),
                trigger=trigger,
                error=error,
            ),
        )


def _sync_event_paths(anchor_file: str, transfer_results: list[MediaServerSyncTargetFile]) -> list[str]:
    paths = [item.destination_path for item in transfer_results if item.destination_path]
    if not paths and anchor_file:
        paths = [anchor_file]
    return sorted(set(paths))
