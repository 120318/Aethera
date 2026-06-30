from pathlib import Path

from app.schemas.domain.addon_events import DanmuGenerateEventMeta, MediaServerSyncEventMeta
from app.schemas.domain.event import EventActor, EventEntityRef, EventLevel, EventSource, EventType, MediaEventCreate
from app.schemas.domain.media import MediaFullInfo
from app.schemas.domain.media_server_sync import MediaServerSyncTargetFile
from app.services.audit.event_service import event_service

_INFO_DANMU_FAILURE_KEYS = {
    "runtimeReasons.danmuDurationMismatch",
    "runtimeReasons.danmuNotFound",
}


def _danmu_event_level(event_type: EventType, error_key: str | None) -> EventLevel:
    if event_type != EventType.DANMU_GENERATE_FAILED:
        return EventLevel.info
    if error_key in _INFO_DANMU_FAILURE_KEYS:
        return EventLevel.info
    return EventLevel.error


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
    event_service.emit_media(
        MediaEventCreate(
            type=event_type,
            level=_danmu_event_level(event_type, error_key),
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
    nfo_count, image_count = _sync_artifact_counts(media, anchor_file, transfer_results)
    for path in target_paths:
        episode_numbers = _sync_event_episode_numbers(path, transfer_results)
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
                nfo_count=nfo_count,
                image_count=image_count,
                episode_number=episode_numbers[0] if len(episode_numbers) == 1 else None,
                episode_numbers=episode_numbers,
                trigger=trigger,
                error=error,
            ),
        )


def _sync_event_paths(anchor_file: str, transfer_results: list[MediaServerSyncTargetFile]) -> list[str]:
    paths = [item.destination_path for item in transfer_results if item.destination_path]
    if not paths and anchor_file:
        paths = [anchor_file]
    return sorted(set(paths))


def _sync_event_episode_numbers(path: str, transfer_results: list[MediaServerSyncTargetFile]) -> list[int]:
    episodes: set[int] = set()
    for item in transfer_results:
        if item.destination_path != path:
            continue
        for episode in [item.episode_number, *item.episode_numbers]:
            if episode and int(episode) > 0:
                episodes.add(int(episode))
    return sorted(episodes)


def _sync_artifact_counts(
    media: MediaFullInfo,
    anchor_file: str,
    transfer_results: list[MediaServerSyncTargetFile],
) -> tuple[int, int]:
    if not anchor_file:
        return (0, 0)
    media_root_dir = _media_root_dir(media, anchor_file)
    nfo_paths = _expected_nfo_paths(media, anchor_file, transfer_results, media_root_dir)
    image_paths: set[Path] = set()
    root = Path(media_root_dir)
    if media.poster_path:
        image_paths.add(root / "poster.jpg")
    if media.backdrop_path:
        image_paths.add(root / "fanart.jpg")
    if media.logo_path:
        image_paths.add(root / "logo.png")
    return (
        sum(1 for path in nfo_paths if path.exists()),
        sum(1 for path in image_paths if path.exists()),
    )


def _media_root_dir(media: MediaFullInfo, anchor_file: str) -> Path:
    anchor = Path(anchor_file)
    if media.media_type.value != "tv":
        return anchor.parent
    parent = anchor.parent
    if parent.name.lower().startswith("season"):
        return parent.parent
    return parent


def _expected_nfo_paths(
    media: MediaFullInfo,
    anchor_file: str,
    transfer_results: list[MediaServerSyncTargetFile],
    media_root_dir: Path,
) -> set[Path]:
    anchor = Path(anchor_file)
    if media.media_type.value != "tv":
        paths = {media_root_dir / "movie.nfo"}
        if anchor.suffix and anchor.suffix.lower() not in {".bdmv", ".ifo", ".vob"}:
            paths.add(anchor.with_suffix(".nfo"))
        return paths

    paths: set[Path] = {media_root_dir / "tvshow.nfo"}
    for target in transfer_results:
        if not target.destination_path:
            continue
        target_path = Path(target.destination_path)
        season_dir = target_path.parent
        if season_dir != media_root_dir:
            paths.add(season_dir / "season.nfo")
        if target.episode_number:
            paths.add(target_path.with_suffix(".nfo"))
        if target.episode_numbers:
            paths.add(target_path.with_suffix(".nfo"))
    return paths
