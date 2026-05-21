from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.domain.download import TaskData, TaskErrorStage, TaskStatus
from app.schemas.domain.resource_attributes import ResourceDisplayAttributes
from app.schemas.domain.torrent_status import TorrentState


class TaskPhase(str, Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    READY_TO_IMPORT = "ready_to_import"
    IMPORTING = "importing"
    MIGRATING = "migrating"
    COMPLETED = "completed"
    ATTENTION = "attention"
    FAILED = "failed"


class TaskPhaseGroup(str, Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    READY_TO_IMPORT = "ready_to_import"
    IMPORTING = "importing"
    MIGRATING = "migrating"
    COMPLETED = "completed"
    ATTENTION = "attention"
    FAILED = "failed"


class TaskAction(str, Enum):
    VIEW_DETAIL = "view_detail"
    PAUSE = "pause"
    RESUME = "resume"
    TRANSFER = "transfer"
    MEDIA_SERVER_SYNC = "media_server_sync"
    DANMU_GENERATE = "danmu_generate"
    CHANGE_DOWNLOADER = "change_downloader"
    DELETE = "delete"


class TaskActionState(BaseModel):
    action: TaskAction
    available: bool = True
    loading: bool = False
    disabled: bool = False
    disabled_reason_key: str | None = None
    disabled_reason_params: dict[str, str] = Field(default_factory=dict)
    active_command_id: str | None = None
    active_command_type: str | None = None


class TaskRealtimeView(BaseModel):
    available: bool = False
    torrent_state: TorrentState | None = None
    download_speed: int = 0
    upload_speed: int = 0
    eta: int = 0
    num_seeds: int = 0
    num_leechs: int = 0
    progress: float | None = None


class TaskViewItem(BaseModel):
    id: str
    status: TaskStatus
    phase: TaskPhase
    phase_group: TaskPhaseGroup
    phase_label: str = ""
    phase_label_key: str
    actions: list[TaskAction] = Field(default_factory=list)
    action_states: list[TaskActionState] = Field(default_factory=list)

    error_stage: TaskErrorStage | None = None
    error_key: str | None = None
    error_params: dict[str, str] = Field(default_factory=dict)
    attention_reason_key: str | None = None
    attention_reason_params: dict[str, str] = Field(default_factory=dict)

    progress: float = 0.0
    created_at: datetime
    save_path: str | None = None
    directory_id: str | None = None
    directory_name: str | None = None
    media_type: str | None = None
    media_id: str | None = None
    torrent_hash: str
    downloader_id: str | None = None
    download_client: str | None = None
    download_client_url: str | None = None
    title: str | None = None
    description: str | None = None
    size: int = 0
    indexer: str | None = None
    site: str | None = None
    page_url: str | None = None
    detail_url: str | None = None
    torrent_url: str | None = None
    attributes: ResourceDisplayAttributes = Field(default_factory=ResourceDisplayAttributes)
    selected_season: int | None = None
    selected_episodes: list[int] = Field(default_factory=list)
    partial_selection: bool = False
    has_primary_library_files: bool = False
    realtime: TaskRealtimeView = Field(default_factory=TaskRealtimeView)
    active_command_type: str | None = None
    active_command_id: str | None = None


class TaskDetailResponseModel(BaseModel):
    task: TaskViewItem
    raw_task: TaskData | None = None
