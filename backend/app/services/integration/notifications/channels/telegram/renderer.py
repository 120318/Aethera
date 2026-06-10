from __future__ import annotations

import json
from datetime import datetime
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import quote, urlencode

from pydantic import BaseModel, Field, field_validator

from app.schemas.domain.event import Event, EventLevel, EventType
from app.services.i18n.message_renderer import render_message


class TelegramImportedFileMeta(BaseModel):
    destination_path: str = ""
    episode_number: int | None = None
    episode_numbers: list[int] = Field(default_factory=list)


class TelegramEventMeta(BaseModel):
    resource_title: str = ""
    torrent_name: str = ""
    file_path: str = ""
    video_path: str = ""
    path: str = ""
    reason: str = ""
    error: str = ""
    error_key: str = ""
    error_params: Mapping[str, str] = Field(default_factory=lambda: {})
    selected_episodes: list[int] = Field(default_factory=list)
    imported_files: list[TelegramImportedFileMeta] = Field(default_factory=list)
    episode_number: int | None = None

    @field_validator(
        "resource_title",
        "torrent_name",
        "file_path",
        "video_path",
        "path",
        "reason",
        "error",
        "error_key",
        mode="before",
    )
    @classmethod
    def _none_to_empty(cls, value) -> str:
        if value is None:
            return ""
        return str(value)


def escape_markdown(value: str) -> str:
    escaped = value or ""
    for char in "\\_*[]()~`>#+-=|{}.!":
        escaped = escaped.replace(char, f"\\{char}")
    return escaped


def _text(key: str, locale: str, params: Mapping[str, str] | None = None) -> str:
    return render_message(key, params or {}, locale=locale)


def _meta(event: Event) -> TelegramEventMeta:
    if not event.meta:
        return TelegramEventMeta()
    try:
        json.loads(event.meta)
    except json.JSONDecodeError:
        return TelegramEventMeta()
    return TelegramEventMeta.model_validate_json(event.meta)


def _path_name(value: str | None) -> str:
    normalized = str(value or "").strip()
    return Path(normalized).name or normalized


def _episode_range(values) -> list[int]:
    normalized: set[int] = set()
    for value in values or []:
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        if number > 0:
            normalized.add(number)
    return sorted(normalized)


def _format_episode_range(values, locale: str) -> str:
    episodes = _episode_range(values)
    if not episodes:
        return ""

    ranges: list[tuple[int, int]] = []
    start = episodes[0]
    end = episodes[0]
    for value in episodes[1:]:
        if value == end + 1:
            end = value
            continue
        ranges.append((start, end))
        start = value
        end = value
    ranges.append((start, end))

    parts = [str(start) if start == end else f"{start}-{end}" for start, end in ranges]
    return _text("telegram.fields.episodes", locale, {"episodes": ", ".join(parts)})


def _download_episodes(meta: TelegramEventMeta) -> list[int]:
    return _episode_range(meta.selected_episodes)


def _imported_episodes(meta: TelegramEventMeta) -> list[int]:
    episodes: list[int] = []
    for item in meta.imported_files:
        episodes.extend(_episode_range(item.episode_numbers))
        episodes.extend(_episode_range([item.episode_number]))
    return episodes


def _event_episodes(event: Event, meta: TelegramEventMeta) -> list[int]:
    if event.type == EventType.DOWNLOAD_COMPLETED:
        return _download_episodes(meta)
    if event.type == EventType.MEDIA_IMPORT_COMPLETED:
        return _imported_episodes(meta)
    if event.type in {EventType.DANMU_GENERATE_COMPLETED, EventType.DANMU_GENERATE_FAILED}:
        return _episode_range([meta.episode_number])
    return []


def _media_line(event: Event, meta: TelegramEventMeta, locale: str) -> str:
    if not event.media:
        return _text("telegram.fields.system", locale)
    parts = [event.media.title]
    if event.media.season_number:
        parts.append(_text("telegram.fields.season", locale, {"season": str(event.media.season_number)}))
    episode_text = _format_episode_range(_event_episodes(event, meta), locale)
    if episode_text:
        parts.append(episode_text)
    return " · ".join(parts)


def _resource_line(event: Event, meta: TelegramEventMeta, locale: str) -> str:
    resource = (
        meta.torrent_name
        or meta.resource_title
        or _message_param(event, "torrent_name")
        or _message_param(event, "resource_title")
        or _indexer_site_resource(event)
        or _path_name(meta.file_path)
        or _path_name(meta.video_path)
        or _path_name(meta.path)
        or ""
    )
    if not resource:
        return ""
    return _text("telegram.fields.resource", locale, {"resource": str(resource)})


def _message_param(event: Event, name: str) -> str:
    if name not in event.message_params:
        return ""
    return str(event.message_params[name])


def _indexer_site_resource(event: Event) -> str:
    if event.type != EventType.INDEXER_SITE_UNHEALTHY:
        return ""
    indexer = _message_param(event, "indexer_name") or _message_param(event, "indexer_id")
    site = _message_param(event, "site_name") or _message_param(event, "site_id")
    return " / ".join(part for part in (indexer, site) if part)


def _reason_line(event: Event, meta: TelegramEventMeta, locale: str) -> str:
    if event.level == EventLevel.info and not event.type.value.endswith(".failed"):
        return ""
    reason = meta.error or meta.reason or _message_param(event, "reason") or _message_param(event, "error")
    reason_key = meta.error_key or _message_param(event, "reason_key")
    if reason_key:
        reason = render_message(str(reason_key), {str(key): str(value) for key, value in meta.error_params.items()}, locale=locale)
    if not reason:
        return ""
    return _text("telegram.fields.reason", locale, {"reason": str(reason)})


def _time_line(ts: datetime, locale: str) -> str:
    return _text("telegram.fields.time", locale, {"time": ts.strftime("%Y-%m-%d %H:%M")})


def _detail_url(event: Event, public_base_url: str) -> str:
    base = public_base_url.strip().rstrip("/")
    if not base or not event.media_id:
        return ""
    path = f"/media/{quote(str(event.media_id), safe=':')}"
    query = ""
    if event.media and event.media.season_number:
        query = f"?{urlencode({'season': event.media.season_number})}"
    return f"{base}{path}{query}"


def _title_key(event: Event) -> str:
    keys = {
        EventType.DOWNLOAD_COMPLETED: "telegram.titles.downloadCompleted",
        EventType.DOWNLOAD_FAILED: "telegram.titles.downloadFailed",
        EventType.DOWNLOAD_TASK_DOWNLOADER_CHANGE_FAILED: "telegram.titles.downloadTaskDownloaderChangeFailed",
        EventType.DOWNLOAD_TASK_STORAGE_CHANGE_FAILED: "telegram.titles.downloadTaskStorageChangeFailed",
        EventType.MEDIA_IMPORT_COMPLETED: "telegram.titles.mediaImportCompleted",
        EventType.MEDIA_IMPORT_FAILED: "telegram.titles.mediaImportFailed",
        EventType.MEDIA_SERVER_SYNC_COMPLETED: "telegram.titles.mediaServerSyncCompleted",
        EventType.MEDIA_SERVER_SYNC_FAILED: "telegram.titles.mediaServerSyncFailed",
        EventType.DANMU_GENERATE_COMPLETED: "telegram.titles.danmuGenerateCompleted",
        EventType.DANMU_GENERATE_FAILED: "telegram.titles.danmuGenerateFailed",
        EventType.MEDIA_DELETED: "telegram.titles.mediaDeleted",
        EventType.LIBRARY_FILE_MISSING: "telegram.titles.libraryFileMissing",
        EventType.INDEXER_SITE_UNHEALTHY: "telegram.titles.indexerSiteUnhealthy",
        EventType.FOLLOW_RELEASED: "telegram.titles.followReleased",
        EventType.FOLLOW_DIGITAL_RELEASED: "telegram.titles.followDigitalReleased",
        EventType.FOLLOW_PHYSICAL_RELEASED: "telegram.titles.followPhysicalReleased",
        EventType.SUBSCRIPTION_ENDED_MOVIE_COMPLETED: "telegram.titles.subscriptionEnded",
        EventType.SUBSCRIPTION_ENDED_MOVIE_DOWNLOADING_COMPLETED: "telegram.titles.subscriptionEnded",
        EventType.SUBSCRIPTION_ENDED_MOVIE_TARGET_COMPLETED: "telegram.titles.subscriptionEnded",
        EventType.SUBSCRIPTION_ENDED_TV_COMPLETED: "telegram.titles.subscriptionEnded",
        EventType.SUBSCRIPTION_ENDED_TV_UPGRADE_COMPLETED: "telegram.titles.subscriptionEnded",
        EventType.SUBSCRIPTION_ENDED_TV_TARGET_COMPLETED: "telegram.titles.subscriptionEnded",
    }
    if event.type in keys:
        return keys[event.type]
    return "telegram.titles.generic"


def format_telegram_event(event: Event, *, locale: str, public_base_url: str) -> str:
    meta = _meta(event)
    title = f"[Aethera] {_text(_title_key(event), locale)}"
    lines = [
        f"*{escape_markdown(title)}*",
        escape_markdown(_media_line(event, meta, locale)),
        escape_markdown(_resource_line(event, meta, locale)),
        escape_markdown(_reason_line(event, meta, locale)),
        escape_markdown(_time_line(event.ts, locale)),
    ]
    detail_url = _detail_url(event, public_base_url)
    if detail_url:
        lines.append(f"[{escape_markdown(_text('telegram.actions.viewDetails', locale))}]({escape_markdown(detail_url)})")
    return "\n".join(line for line in lines if line)
