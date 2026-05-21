from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.media_id import MediaID
from app.schemas.domain.media import MediaIdentity


class EventLevel(str, Enum):
    info = "info"
    warning = "warning"
    error = "error"


class EventActor(str, Enum):
    system = "system"
    user = "user"


class EventSource(str, Enum):
    base = "base"
    addon = "addon"


class EventType(str, Enum):
    DOWNLOAD_STARTED = "download.started"
    DOWNLOAD_COMPLETED = "download.completed"
    DOWNLOAD_FAILED = "download.failed"
    DOWNLOAD_TASK_DOWNLOADER_CHANGED = "download.task.downloader_changed"
    DOWNLOAD_TASK_DOWNLOADER_CHANGE_FAILED = "download.task.downloader_change_failed"
    DOWNLOAD_TASK_STORAGE_CHANGE_STARTED = "download.task.storage_change_started"
    DOWNLOAD_TASK_STORAGE_CHANGED = "download.task.storage_changed"
    DOWNLOAD_TASK_STORAGE_CHANGE_FAILED = "download.task.storage_change_failed"
    MEDIA_IMPORT_STARTED = "media.import.started"
    MEDIA_IMPORT_COMPLETED = "media.import.completed"
    MEDIA_IMPORT_FAILED = "media.import.failed"
    MEDIA_SERVER_SYNC_STARTED = "media_server_sync.started"
    MEDIA_SERVER_SYNC_COMPLETED = "media_server_sync.completed"
    MEDIA_SERVER_SYNC_FAILED = "media_server_sync.failed"
    DANMU_GENERATE_STARTED = "danmu.generate.started"
    DANMU_GENERATE_COMPLETED = "danmu.generate.completed"
    DANMU_GENERATE_FAILED = "danmu.generate.failed"
    MEDIA_DELETED = "media.deleted"
    LIBRARY_FILE_MISSING = "library.file.missing"
    SUBSCRIPTION_ENABLED = "subscription.enabled"
    SUBSCRIPTION_DISABLED = "subscription.disabled"
    SUBSCRIPTION_ENDED_MANUAL = "subscription.ended.manual"
    SUBSCRIPTION_ENDED_MOVIE_COMPLETED = "subscription.ended.movie_completed"
    SUBSCRIPTION_ENDED_MOVIE_DOWNLOADING_COMPLETED = "subscription.ended.movie_downloading_completed"
    SUBSCRIPTION_ENDED_MOVIE_TARGET_COMPLETED = "subscription.ended.movie_target_completed"
    SUBSCRIPTION_ENDED_TV_COMPLETED = "subscription.ended.tv_completed"
    SUBSCRIPTION_ENDED_TV_UPGRADE_COMPLETED = "subscription.ended.tv_upgrade_completed"
    SUBSCRIPTION_ENDED_TV_TARGET_COMPLETED = "subscription.ended.tv_target_completed"
    FOLLOW_ENABLED = "follow.enabled"
    FOLLOW_DISABLED = "follow.disabled"
    FOLLOW_RELEASED = "follow.released"
    FOLLOW_DIGITAL_RELEASED = "follow.digital_released"
    FOLLOW_PHYSICAL_RELEASED = "follow.physical_released"
    SUBSCRIPTION_RUN_COMPLETED = "subscription.run.completed"
    SUBSCRIPTION_RUN_FAILED = "subscription.run.failed"
    PILOT_EPISODE_QUEUED = "pilot.episode.queued"
    ADDON_RUN_STARTED = "addon.run.started"
    ADDON_RUN_COMPLETED = "addon.run.completed"
    ADDON_RUN_FAILED = "addon.run.failed"
    ADDON_RUN_SKIPPED = "addon.run.skipped"
    NOTIFICATION_SENT = "notification.sent"
    NOTIFICATION_FAILED = "notification.failed"


class EventEntityRef(BaseModel):
    type: str
    id: str


class EventCreate(BaseModel):
    type: EventType
    level: EventLevel = EventLevel.info
    message_key: str | None = None
    message_params: dict[str, str] = Field(default_factory=dict)
    task_id: str | None = None
    subscription_id: str | None = None
    actor: EventActor = EventActor.system
    source: EventSource = EventSource.base
    addon_id: str | None = None
    addon_name: str | None = None
    entities: list[EventEntityRef] = Field(default_factory=list)
    correlation_id: str | None = None
    action_id: str | None = None


class MediaEventCreate(EventCreate):
    media: MediaIdentity


class Event(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ts: datetime = Field(default_factory=datetime.now)
    type: EventType
    level: EventLevel = EventLevel.info
    message_key: str | None = None
    message_params: dict[str, str] = Field(default_factory=dict)

    media: MediaIdentity | None = None
    task_id: Optional[str] = None
    subscription_id: Optional[str] = None

    actor: EventActor = EventActor.system
    source: EventSource = EventSource.base
    addon_id: Optional[str] = None
    addon_name: Optional[str] = None

    entities: list[EventEntityRef] = Field(default_factory=list)
    meta: str = ""
    correlation_id: Optional[str] = None
    action_id: Optional[str] = None

    @property
    def media_id(self) -> MediaID | None:
        return self.media.media_id if self.media else None

    @property
    def media_title(self) -> str | None:
        return self.media.title if self.media else None

    @property
    def media_year(self) -> int | None:
        return self.media.year if self.media else None
