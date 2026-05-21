from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.domain.download import DownloadTaskCreateInput
from app.schemas.domain.media import MediaExecutionSnapshot, MediaTarget
from app.schemas.domain.subscription import SubscriptionUnmatchedRule
from app.schemas.domain.subscription_filters import SubscriptionFilters
from app.schemas.media_id import MediaID


class CommandType(str, Enum):
    RESOURCE_SEARCH = "resource.search"
    SUBSCRIPTION_RUN = "subscription.run"
    TASK_CREATE = "task.create"
    PILOT_EPISODE = "pilot.episode"
    TASK_PAUSE = "task.pause"
    TASK_RESUME = "task.resume"
    TASK_TRANSFER = "task.transfer"
    TASK_STORAGE_CHANGE = "task.storage_change"
    TASK_MEDIA_SERVER_SYNC = "task.media_server_sync"
    TASK_DANMU_GENERATE = "task.danmu_generate"
    LIBRARY_FILE_DELETE = "library_file.delete"
    LIBRARY_FILE_STORAGE_CHANGE = "library_file.storage_change"
    LIBRARY_FILE_MEDIA_SERVER_SYNC = "library_file.media_server_sync"
    LIBRARY_FILE_DANMU_GENERATE = "library_file.danmu_generate"
    TASK_DELETE = "task.delete"
    MEDIA_DELETE = "media.delete"
    PROFILE_REFRESH = "profile.refresh"
    DIRECTORY_INTEGRITY_SCAN = "directory.integrity_scan"
    DIRECTORY_INTEGRITY_REPAIR = "directory.integrity_repair"


class CommandStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CommandTargetType(str, Enum):
    MEDIA = "media"
    TASK = "task"
    LIBRARY_FILE = "library_file"
    DIRECTORY = "directory"


class CommandInitiator(str, Enum):
    MANUAL = "manual"
    SCHEDULER = "scheduler"
    SYSTEM = "system"


class PayloadBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResourceSearchCommandRequestPayload(PayloadBase):
    target: MediaTarget
    site_ids: list[str] = Field(default_factory=list)


class SubscriptionRunCommandRequestPayload(PayloadBase):
    target: MediaTarget


class TaskCreateCommandRequestPayload(DownloadTaskCreateInput):
    model_config = ConfigDict(extra="forbid")


class PilotEpisodeCommandRequestPayload(PayloadBase):
    target: MediaTarget
    directory_id: str
    site_ids: list[str] = Field(default_factory=list)
    filters: SubscriptionFilters | None = None
    quality_profile_id: str | None = None
    unmatched_rules: list[SubscriptionUnmatchedRule] = Field(default_factory=list)


class TaskTransferCommandRequestPayload(PayloadBase):
    task_id: str


class TaskStorageChangeCommandRequestPayload(PayloadBase):
    task_id: str
    target_downloader_id: str
    target_directory_id: str
    cleanup_source_torrent: bool = True


class TaskMediaServerSyncCommandRequestPayload(PayloadBase):
    task_id: str


class TaskDanmuGenerateCommandRequestPayload(PayloadBase):
    task_id: str


class TaskPauseCommandRequestPayload(PayloadBase):
    task_id: str


class TaskResumeCommandRequestPayload(PayloadBase):
    task_id: str


class LibraryFileDeleteCommandRequestPayload(PayloadBase):
    file_id: str
    target: MediaTarget
    force: bool = False
    package_root: str = ""


class LibraryFileStorageChangeCommandRequestPayload(PayloadBase):
    file_id: str
    target: MediaTarget
    target_directory_id: str
    package_root: str = ""


class LibraryFileMediaServerSyncCommandRequestPayload(PayloadBase):
    file_id: str
    target: MediaTarget
    package_root: str = ""


class LibraryFileDanmuGenerateCommandRequestPayload(PayloadBase):
    file_id: str
    target: MediaTarget
    package_root: str = ""


class TaskDeleteCommandRequestPayload(PayloadBase):
    task_id: str
    delete_files: bool = True
    force: bool = False
    delete_library_files: bool = False
    delete_task: bool = True


class ProfileRefreshCommandRequestPayload(PayloadBase):
    target: MediaTarget


class MediaDeleteCommandRequestPayload(PayloadBase):
    target: MediaTarget
    mode: Literal["tasks_only", "tasks_and_library"]
    delete_files: bool = True
    force: bool = False


class DirectoryIntegrityRepairCommandRequestPayload(PayloadBase):
    scan_id: str
    item_ids: list[str] = Field(default_factory=list)


class DirectoryIntegrityScanCommandRequestPayload(PayloadBase):
    directory_id: str | None = None


CommandRequestPayload = (
    ResourceSearchCommandRequestPayload
    | SubscriptionRunCommandRequestPayload
    | TaskCreateCommandRequestPayload
    | PilotEpisodeCommandRequestPayload
    | TaskTransferCommandRequestPayload
    | TaskStorageChangeCommandRequestPayload
    | TaskMediaServerSyncCommandRequestPayload
    | TaskDanmuGenerateCommandRequestPayload
    | TaskPauseCommandRequestPayload
    | TaskResumeCommandRequestPayload
    | LibraryFileDeleteCommandRequestPayload
    | LibraryFileStorageChangeCommandRequestPayload
    | LibraryFileMediaServerSyncCommandRequestPayload
    | LibraryFileDanmuGenerateCommandRequestPayload
    | TaskDeleteCommandRequestPayload
    | ProfileRefreshCommandRequestPayload
    | MediaDeleteCommandRequestPayload
    | DirectoryIntegrityScanCommandRequestPayload
    | DirectoryIntegrityRepairCommandRequestPayload
)


class ResourceSearchCommandRecordPayload(PayloadBase):
    media: MediaExecutionSnapshot
    site_ids: list[str] = Field(default_factory=list)


class SubscriptionRunCommandRecordPayload(PayloadBase):
    target: MediaTarget


class TaskCreateCommandRecordPayload(DownloadTaskCreateInput):
    model_config = ConfigDict(extra="forbid")
    resource_title: str | None = None


class PilotEpisodeCommandRecordPayload(PayloadBase):
    media: MediaExecutionSnapshot
    directory_id: str
    site_ids: list[str] = Field(default_factory=list)
    filters: SubscriptionFilters | None = None
    quality_profile_id: str | None = None
    unmatched_rules: list[SubscriptionUnmatchedRule] = Field(default_factory=list)


class TaskTransferCommandRecordPayload(PayloadBase):
    resolved_task_id: str
    target: MediaTarget


class TaskStorageChangeCommandRecordPayload(PayloadBase):
    resolved_task_id: str
    target: MediaTarget
    target_downloader_id: str
    target_directory_id: str
    cleanup_source_torrent: bool = True


class TaskMediaServerSyncCommandRecordPayload(PayloadBase):
    resolved_task_id: str
    target: MediaTarget


class TaskDanmuGenerateCommandRecordPayload(PayloadBase):
    resolved_task_id: str
    target: MediaTarget


class TaskPauseCommandRecordPayload(PayloadBase):
    resolved_task_id: str
    target: MediaTarget


class TaskResumeCommandRecordPayload(PayloadBase):
    resolved_task_id: str
    target: MediaTarget


class LibraryFileDeleteCommandRecordPayload(PayloadBase):
    file_id: str
    target: MediaTarget
    force: bool = False
    package_root: str = ""


class LibraryFileStorageChangeCommandRecordPayload(PayloadBase):
    file_id: str
    target: MediaTarget
    target_directory_id: str
    package_root: str = ""


class LibraryFileMediaServerSyncCommandRecordPayload(PayloadBase):
    file_id: str
    target: MediaTarget
    package_root: str = ""


class LibraryFileDanmuGenerateCommandRecordPayload(PayloadBase):
    file_id: str
    target: MediaTarget
    package_root: str = ""


class TaskDeleteCommandRecordPayload(PayloadBase):
    resolved_task_id: str
    target: MediaTarget
    delete_files: bool = True
    force: bool = False
    delete_library_files: bool = False
    delete_task: bool = True


class ProfileRefreshCommandRecordPayload(PayloadBase):
    target: MediaTarget


class MediaDeleteCommandRecordPayload(PayloadBase):
    target: MediaTarget
    mode: Literal["tasks_only", "tasks_and_library"]
    delete_files: bool = True
    force: bool = False


class DirectoryIntegrityRepairCommandRecordPayload(PayloadBase):
    scan_id: str
    item_ids: list[str] = Field(default_factory=list)


class DirectoryIntegrityScanCommandRecordPayload(PayloadBase):
    directory_id: str | None = None


CommandRecordPayload = (
    ResourceSearchCommandRecordPayload
    | SubscriptionRunCommandRecordPayload
    | TaskCreateCommandRecordPayload
    | PilotEpisodeCommandRecordPayload
    | TaskTransferCommandRecordPayload
    | TaskStorageChangeCommandRecordPayload
    | TaskMediaServerSyncCommandRecordPayload
    | TaskDanmuGenerateCommandRecordPayload
    | TaskPauseCommandRecordPayload
    | TaskResumeCommandRecordPayload
    | LibraryFileDeleteCommandRecordPayload
    | LibraryFileStorageChangeCommandRecordPayload
    | LibraryFileMediaServerSyncCommandRecordPayload
    | LibraryFileDanmuGenerateCommandRecordPayload
    | TaskDeleteCommandRecordPayload
    | ProfileRefreshCommandRecordPayload
    | MediaDeleteCommandRecordPayload
    | DirectoryIntegrityScanCommandRecordPayload
    | DirectoryIntegrityRepairCommandRecordPayload
)


REQUEST_PAYLOAD_BY_TYPE: dict[CommandType, type[PayloadBase]] = {
    CommandType.RESOURCE_SEARCH: ResourceSearchCommandRequestPayload,
    CommandType.SUBSCRIPTION_RUN: SubscriptionRunCommandRequestPayload,
    CommandType.TASK_CREATE: TaskCreateCommandRequestPayload,
    CommandType.PILOT_EPISODE: PilotEpisodeCommandRequestPayload,
    CommandType.TASK_TRANSFER: TaskTransferCommandRequestPayload,
    CommandType.TASK_STORAGE_CHANGE: TaskStorageChangeCommandRequestPayload,
    CommandType.TASK_MEDIA_SERVER_SYNC: TaskMediaServerSyncCommandRequestPayload,
    CommandType.TASK_DANMU_GENERATE: TaskDanmuGenerateCommandRequestPayload,
    CommandType.TASK_PAUSE: TaskPauseCommandRequestPayload,
    CommandType.TASK_RESUME: TaskResumeCommandRequestPayload,
    CommandType.LIBRARY_FILE_DELETE: LibraryFileDeleteCommandRequestPayload,
    CommandType.LIBRARY_FILE_STORAGE_CHANGE: LibraryFileStorageChangeCommandRequestPayload,
    CommandType.LIBRARY_FILE_MEDIA_SERVER_SYNC: LibraryFileMediaServerSyncCommandRequestPayload,
    CommandType.LIBRARY_FILE_DANMU_GENERATE: LibraryFileDanmuGenerateCommandRequestPayload,
    CommandType.TASK_DELETE: TaskDeleteCommandRequestPayload,
    CommandType.MEDIA_DELETE: MediaDeleteCommandRequestPayload,
    CommandType.PROFILE_REFRESH: ProfileRefreshCommandRequestPayload,
    CommandType.DIRECTORY_INTEGRITY_SCAN: DirectoryIntegrityScanCommandRequestPayload,
    CommandType.DIRECTORY_INTEGRITY_REPAIR: DirectoryIntegrityRepairCommandRequestPayload,
}

RECORD_PAYLOAD_BY_TYPE: dict[CommandType, type[PayloadBase]] = {
    CommandType.RESOURCE_SEARCH: ResourceSearchCommandRecordPayload,
    CommandType.SUBSCRIPTION_RUN: SubscriptionRunCommandRecordPayload,
    CommandType.TASK_CREATE: TaskCreateCommandRecordPayload,
    CommandType.PILOT_EPISODE: PilotEpisodeCommandRecordPayload,
    CommandType.TASK_TRANSFER: TaskTransferCommandRecordPayload,
    CommandType.TASK_STORAGE_CHANGE: TaskStorageChangeCommandRecordPayload,
    CommandType.TASK_MEDIA_SERVER_SYNC: TaskMediaServerSyncCommandRecordPayload,
    CommandType.TASK_DANMU_GENERATE: TaskDanmuGenerateCommandRecordPayload,
    CommandType.TASK_PAUSE: TaskPauseCommandRecordPayload,
    CommandType.TASK_RESUME: TaskResumeCommandRecordPayload,
    CommandType.LIBRARY_FILE_DELETE: LibraryFileDeleteCommandRecordPayload,
    CommandType.LIBRARY_FILE_STORAGE_CHANGE: LibraryFileStorageChangeCommandRecordPayload,
    CommandType.LIBRARY_FILE_MEDIA_SERVER_SYNC: LibraryFileMediaServerSyncCommandRecordPayload,
    CommandType.LIBRARY_FILE_DANMU_GENERATE: LibraryFileDanmuGenerateCommandRecordPayload,
    CommandType.TASK_DELETE: TaskDeleteCommandRecordPayload,
    CommandType.MEDIA_DELETE: MediaDeleteCommandRecordPayload,
    CommandType.PROFILE_REFRESH: ProfileRefreshCommandRecordPayload,
    CommandType.DIRECTORY_INTEGRITY_SCAN: DirectoryIntegrityScanCommandRecordPayload,
    CommandType.DIRECTORY_INTEGRITY_REPAIR: DirectoryIntegrityRepairCommandRecordPayload,
}


def parse_command_request_payload(command_type: CommandType, payload) -> CommandRequestPayload:
    payload_cls = REQUEST_PAYLOAD_BY_TYPE[command_type]
    return payload_cls.model_validate(payload)


def parse_command_record_payload(command_type: CommandType, payload) -> CommandRecordPayload:
    payload_cls = RECORD_PAYLOAD_BY_TYPE[command_type]
    return payload_cls.model_validate(payload)


class CommandCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: CommandType
    initiator: CommandInitiator = CommandInitiator.MANUAL
    payload: CommandRequestPayload

    @model_validator(mode="before")
    @classmethod
    def parse_payload_for_type(cls, data):
        command_type = CommandType(data.get("type"))
        data["payload"] = parse_command_request_payload(command_type, data.get("payload"))
        return data

    @classmethod
    def from_task_create_input(
        cls,
        req: DownloadTaskCreateInput,
        *,
        initiator: CommandInitiator = CommandInitiator.MANUAL,
        command_type: CommandType = CommandType.TASK_CREATE,
    ) -> "CommandCreateRequest":
        if command_type != CommandType.TASK_CREATE:
            raise ValueError("from_task_create_input only supports task.create")
        return cls(
            type=command_type,
            initiator=initiator,
            payload=TaskCreateCommandRequestPayload(
                media=req.media,
                result_id=req.result_id,
                directory_id=req.directory_id,
                selected_files=list(req.selected_files or []),
            ),
        )


class CommandResult(BaseModel):
    result_count: int = 0
    task_id: str | None = None
    transferred_files_count: int = 0
    deleted_tasks_count: int = 0
    deleted_library_files_count: int = 0
    deleted_task: bool = False
    repaired_count: int = 0
    failed_count: int = 0


class CommandRecord(BaseModel):
    id: str
    type: CommandType
    status: CommandStatus = CommandStatus.QUEUED
    message_key: str | None = None
    message_params: dict[str, Any] = Field(default_factory=dict)
    payload: CommandRecordPayload
    result: CommandResult | None = None
    error: str | None = None
    error_key: str | None = None
    error_params: dict[str, Any] = Field(default_factory=dict)
    initiator: CommandInitiator = CommandInitiator.MANUAL
    media_id: MediaID | None = None
    target: MediaTarget | None = None
    target_season_number: int = 0
    uniq_key: str | None = None
    target_type: CommandTargetType
    target_id: str
    target_label: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def parse_payload_for_type(cls, data):
        command_type = CommandType(data.get("type"))
        data["payload"] = parse_command_record_payload(command_type, data.get("payload"))
        return data

    @model_validator(mode="after")
    def normalize_target_snapshot(self) -> "CommandRecord":
        if self.target is None and self.media_id is not None:
            season_number = self.target_season_number if self.target_season_number > 0 else None
            self.target = MediaTarget(media_id=self.media_id, season_number=season_number)
        if self.target is not None:
            self.target_season_number = int(self.target.season_number or 0)
            if self.media_id is None:
                self.media_id = self.target.media_id
        return self
