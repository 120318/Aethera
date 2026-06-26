from __future__ import annotations

from app.schemas.domain.event import Event, EventActor, EventType


DEFAULT_NOTIFICATION_EVENT_PATTERNS = [
    "download.failed",
    "download.task.downloader_change_failed",
    "download.task.storage_change_failed",
    "media.import.completed",
    "media.import.failed",
    "library.file.missing",
    "indexer.site.unhealthy",
    "follow.*",
    "subscription.ended.*",
    "media_server_sync.failed",
    "danmu.generate.failed",
]

NOTIFICATION_EVENT_PATTERNS = list(DEFAULT_NOTIFICATION_EVENT_PATTERNS)

MANUAL_NOTIFICATION_SUPPRESSED_EVENTS = {
    EventType.DOWNLOAD_COMPLETED,
    EventType.DOWNLOAD_FAILED,
    EventType.MEDIA_IMPORT_COMPLETED,
    EventType.MEDIA_IMPORT_FAILED,
}


def is_manual_notification_suppressed(event: Event) -> bool:
    return event.actor == EventActor.user and event.type in MANUAL_NOTIFICATION_SUPPRESSED_EVENTS
