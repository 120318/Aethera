from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.domain.media_types import MediaType
from app.schemas.media_id import MediaID


class MediaServerSyncRunResult(BaseModel):
    skipped: bool = False
    reason: str | None = None
    processed: int = 0
    updated: int = 0
    failed: int = 0
    elapsed_seconds: float | None = None


class MediaServerSyncItemResult(BaseModel):
    media_server_id: str
    media_id: MediaID
    updated: bool = False
    failed: bool = False


class MediaServerSyncTargetFile(BaseModel):
    destination_path: str
    episode_number: int | None = None


class MediaServerChangeType(str, Enum):
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"


class MediaServerChange(BaseModel):
    media_id: MediaID | None = None
    target_path: str
    change_type: MediaServerChangeType
    is_media_root: bool = False
    reason: str | None = None


class MediaServerSyncInput(BaseModel):
    anchor_file: str | None = None
    media_root_dir: str | None = None
    transfer_results: list[MediaServerSyncTargetFile] = Field(default_factory=list)
    updated_paths: list[str] = Field(default_factory=list)


class MediaServerSyncDetectNeeds(BaseModel):
    should_run: bool
    missing_flags: list[str] = Field(default_factory=list)
    updated_paths: list[str] = Field(default_factory=list)
    transfer_results: list[MediaServerSyncTargetFile] = Field(default_factory=list)
    anchor_file: str | None = None
    media_root_dir: str | None = None


class MediaServerSyncState(BaseModel):
    media_server_id: str
    media_id: MediaID
    media_type: MediaType | None = None
    status: str = "active"
    last_check_at: float = 0
    last_success_at: float | None = None
    failure_count: int = 0
    last_error: str | None = None
    next_due_at: float = 0
    missing_flags: list[str] = Field(default_factory=list)
    updated_paths: list[str] = Field(default_factory=list)


class NfoFieldMap(BaseModel):
    values: dict[str, str] = Field(default_factory=dict)
