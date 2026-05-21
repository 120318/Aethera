from __future__ import annotations

from pydantic import BaseModel
from app.schemas.domain.command import CommandInitiator
from app.schemas.domain.event import EventType
from app.schemas.runtime.scheduler_types import SchedulerJobSourceType


class CommandQueuedActionMeta(BaseModel):
    command_id: str
    initiator: CommandInitiator
    target_label: str


class TaskStorageMigrationActionMeta(BaseModel):
    migration_id: str
    target_label: str
    source_downloader_id: str
    target_downloader_id: str
    source_directory_id: str
    target_directory_id: str


class SchedulerQueuedActionMeta(BaseModel):
    job_id: str
    job_name: str
    source_type: SchedulerJobSourceType
    source_name: str


class EventDispatchQueuedActionMeta(BaseModel):
    consumer_name: str
    trigger_event_type: EventType
    trigger_event_id: str


class NotificationSendQueuedActionMeta(BaseModel):
    channel_type: str
    channel_name: str
    trigger_event_type: EventType
    trigger_event_id: str


class DanmuGenerateQueuedActionMeta(BaseModel):
    provider: str = ""
    video_path: str
    xml_path: str | None = None
    ass_path: str | None = None
    episode_number: int | None = None
    trigger_event_type: EventType | None = None
    trigger_event_id: str | None = None
