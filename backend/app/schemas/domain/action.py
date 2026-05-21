from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.media_id import MediaID
from app.schemas.domain.media import MediaIdentity


class ActionKind(str, Enum):
    command = "command"
    scheduler = "scheduler"
    addon = "addon"


class ActionStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"
    skipped = "skipped"


class ActionActor(str, Enum):
    user = "user"
    system = "system"


class ActionTrigger(str, Enum):
    manual = "manual"
    scheduler = "scheduler"
    event = "event"
    api = "api"
    system = "system"


class ActionSource(str, Enum):
    api = "api"
    scheduler = "scheduler"
    addon = "addon"
    system = "system"


class ActionTargetType(str, Enum):
    media = "media"
    task = "task"
    library_file = "library_file"
    directory = "directory"
    scheduler_job = "scheduler_job"
    event_consumer = "event_consumer"
    notification_channel = "notification_channel"
    danmu_sidecar = "danmu_sidecar"


class ActionName(str, Enum):
    resource_search = "resource.search"
    subscription_run = "subscription.run"
    task_create = "task.create"
    pilot_episode = "pilot.episode"
    task_pause = "task.pause"
    task_resume = "task.resume"
    task_transfer = "task.transfer"
    task_storage_change = "task.storage_change"
    task_media_server_sync = "task.media_server_sync"
    task_danmu_generate = "task.danmu_generate"
    library_file_delete = "library_file.delete"
    library_file_storage_change = "library_file.storage_change"
    library_file_media_server_sync = "library_file.media_server_sync"
    library_file_danmu_generate = "library_file.danmu_generate"
    task_delete = "task.delete"
    media_delete = "media.delete"
    profile_refresh = "profile.refresh"
    directory_integrity_scan = "directory.integrity_scan"
    directory_integrity_repair = "directory.integrity_repair"
    sync_active_downloads = "sync_active_downloads"
    process_completed_tasks = "process_completed_tasks"
    subscription_sweep = "subscription_sweep"
    follow_reminder_sweep = "follow_reminder_sweep"
    schedule_refresh_sweep = "schedule_refresh_sweep"
    directory_integrity_audit = "directory_integrity_audit"
    cleanup_inactive_managed_media_profiles = "cleanup_inactive_managed_media_profiles"
    media_server_sync_incremental_sweep = "media_server_sync_incremental_sweep"
    cleanup_expired_sessions = "cleanup_expired_sessions"
    event_dispatch = "event.dispatch"
    notification_send = "notification.send"
    danmu_generate = "danmu.generate"


class ActionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ts: datetime = Field(default_factory=datetime.now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    kind: ActionKind
    action_name: str
    status: ActionStatus

    actor: ActionActor = ActionActor.system
    trigger: ActionTrigger = ActionTrigger.system
    source: ActionSource = ActionSource.system

    target_type: ActionTargetType | None = None
    target_id: str | None = None

    media: MediaIdentity | None = None
    media_id: MediaID | None = None
    task_id: str | None = None
    subscription_id: str | None = None

    correlation_id: str | None = None
    message_key: str | None = None
    message_params: dict[str, str] = Field(default_factory=dict)
    error: str | None = None
    duration_ms: int | None = None
    meta: str = ""
