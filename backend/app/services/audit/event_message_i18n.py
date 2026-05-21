from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from app.schemas.domain.event import Event, EventCreate, EventType, MediaEventCreate


EVENT_KEY_BY_TYPE = {
    EventType.DOWNLOAD_STARTED: "eventMessages.downloadStarted",
    EventType.DOWNLOAD_COMPLETED: "eventMessages.downloadCompleted",
    EventType.DOWNLOAD_FAILED: "eventMessages.downloadFailed",
    EventType.DOWNLOAD_TASK_DOWNLOADER_CHANGED: "eventMessages.downloadTaskDownloaderChanged",
    EventType.DOWNLOAD_TASK_DOWNLOADER_CHANGE_FAILED: "eventMessages.downloadTaskDownloaderChangeFailed",
    EventType.DOWNLOAD_TASK_STORAGE_CHANGE_STARTED: "eventMessages.downloadTaskStorageChangeStarted",
    EventType.DOWNLOAD_TASK_STORAGE_CHANGED: "eventMessages.downloadTaskStorageChanged",
    EventType.DOWNLOAD_TASK_STORAGE_CHANGE_FAILED: "eventMessages.downloadTaskStorageChangeFailed",
    EventType.MEDIA_IMPORT_STARTED: "eventMessages.mediaImportStarted",
    EventType.MEDIA_IMPORT_COMPLETED: "eventMessages.mediaImportCompleted",
    EventType.MEDIA_IMPORT_FAILED: "eventMessages.mediaImportFailed",
    EventType.MEDIA_SERVER_SYNC_STARTED: "eventMessages.mediaServerSyncStarted",
    EventType.MEDIA_SERVER_SYNC_COMPLETED: "eventMessages.mediaServerSyncCompleted",
    EventType.MEDIA_SERVER_SYNC_FAILED: "eventMessages.mediaServerSyncFailed",
    EventType.DANMU_GENERATE_STARTED: "eventMessages.danmuGenerateStarted",
    EventType.DANMU_GENERATE_COMPLETED: "eventMessages.danmuGenerateCompleted",
    EventType.DANMU_GENERATE_FAILED: "eventMessages.danmuGenerateFailed",
    EventType.MEDIA_DELETED: "eventMessages.mediaDeleted",
    EventType.LIBRARY_FILE_MISSING: "eventMessages.libraryFileMissing",
    EventType.SUBSCRIPTION_ENABLED: "eventMessages.subscriptionEnabled",
    EventType.SUBSCRIPTION_DISABLED: "eventMessages.subscriptionDisabled",
    EventType.SUBSCRIPTION_ENDED_MANUAL: "eventMessages.subscriptionEndedManual",
    EventType.SUBSCRIPTION_ENDED_MOVIE_COMPLETED: "eventMessages.subscriptionEndedMovieCompleted",
    EventType.SUBSCRIPTION_ENDED_MOVIE_DOWNLOADING_COMPLETED: "eventMessages.subscriptionEndedMovieDownloadingCompleted",
    EventType.SUBSCRIPTION_ENDED_MOVIE_TARGET_COMPLETED: "eventMessages.subscriptionEndedMovieTargetCompleted",
    EventType.SUBSCRIPTION_ENDED_TV_COMPLETED: "eventMessages.subscriptionEndedTvCompleted",
    EventType.SUBSCRIPTION_ENDED_TV_UPGRADE_COMPLETED: "eventMessages.subscriptionEndedTvUpgradeCompleted",
    EventType.SUBSCRIPTION_ENDED_TV_TARGET_COMPLETED: "eventMessages.subscriptionEndedTvTargetCompleted",
    EventType.FOLLOW_ENABLED: "eventMessages.followEnabled",
    EventType.FOLLOW_DISABLED: "eventMessages.followDisabled",
    EventType.FOLLOW_RELEASED: "eventMessages.followReleased",
    EventType.FOLLOW_DIGITAL_RELEASED: "eventMessages.followDigitalReleased",
    EventType.FOLLOW_PHYSICAL_RELEASED: "eventMessages.followPhysicalReleased",
    EventType.SUBSCRIPTION_RUN_COMPLETED: "eventMessages.subscriptionRunCompleted",
    EventType.SUBSCRIPTION_RUN_FAILED: "eventMessages.subscriptionRunFailed",
    EventType.PILOT_EPISODE_QUEUED: "eventMessages.pilotEpisodeQueued",
    EventType.ADDON_RUN_STARTED: "eventMessages.addonRunStarted",
    EventType.ADDON_RUN_COMPLETED: "eventMessages.addonRunCompleted",
    EventType.ADDON_RUN_FAILED: "eventMessages.addonRunFailed",
    EventType.ADDON_RUN_SKIPPED: "eventMessages.addonRunSkipped",
    EventType.NOTIFICATION_SENT: "eventMessages.notificationSent",
    EventType.NOTIFICATION_FAILED: "eventMessages.notificationFailed",
}


def _string_params(payload) -> dict[str, str]:
    if type(payload) is not dict:
        return {}
    params: dict[str, str] = {}
    for key, value in payload.items():
        if value is None:
            continue
        if type(value) in (dict, list):
            params[key] = json.dumps(value, ensure_ascii=False, sort_keys=True)
        else:
            params[key] = str(value)
    return params


def _path_name(path: str | None) -> str:
    normalized = (path or "").strip()
    return Path(normalized).name or normalized


def _first_present(*values: str | None) -> str:
    for value in values:
        normalized = (value or "").strip()
        if normalized:
            return normalized
    return ""


def event_message_key(event_type: EventType) -> str:
    return EVENT_KEY_BY_TYPE.get(event_type, "eventMessages.generic")


def event_message_params(event: EventCreate, meta: BaseModel | None = None) -> dict[str, str]:
    media = event.media if type(event) in (MediaEventCreate, Event) else None
    meta_payload = meta.model_dump(mode="json") if meta else {}
    if not meta_payload and type(event) is Event and event.meta:
        try:
            meta_payload = json.loads(event.meta)
        except json.JSONDecodeError:
            meta_payload = {}

    params = _string_params(meta_payload)
    if media:
        params.setdefault("title", media.title)
        params.setdefault("year", str(media.year))
        params.setdefault("media_id", str(media.media_id))
    params.setdefault("task_id", event.task_id or "")
    params.setdefault("subscription_id", event.subscription_id or "")
    params.setdefault("addon_name", event.addon_name or "")
    resource_title = _first_present(params.get("torrent_name"), params.get("resource_title"), params.get("title"))
    params["resource_title"] = resource_title
    params.setdefault("torrent_name", resource_title)

    for path_key in ("file_path", "video_path", "xml_path", "ass_path"):
        path_value = params.get(path_key)
        if path_value:
            params[f"{path_key}_name"] = _path_name(path_value)

    paths = meta_payload.get("paths") if type(meta_payload) is dict else None
    if type(paths) is list:
        params["path_count"] = str(len(paths))
        params["first_target"] = _path_name(str(paths[0])) if paths else ""

    imported_files = meta_payload.get("imported_files") if type(meta_payload) is dict else None
    if type(imported_files) is list:
        params["file_count"] = str(len(imported_files))
        first_file = imported_files[0] if imported_files else None
        first_path = str(first_file["destination_path"]) if type(first_file) is dict and "destination_path" in first_file else ""
        params["first_target"] = _path_name(first_path)

    selected_files = meta_payload.get("selected_files") if type(meta_payload) is dict else None
    if type(selected_files) is list:
        params["selected_count"] = str(len(selected_files))
        total_files = meta_payload.get("total_files") if type(meta_payload) is dict else None
        if type(total_files) is int and total_files > 0:
            params["total_files"] = str(total_files)

    return params


def attach_event_message_i18n(event: Event) -> Event:
    if not event.message_key:
        event.message_key = event_message_key(event.type)
    if not event.message_params:
        event.message_params = event_message_params(event)
    return event
