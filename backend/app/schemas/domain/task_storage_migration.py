from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.domain.download import TaskStatus


class TaskStorageMigrationStatus(str, Enum):
    PENDING = "pending"
    CHECKING = "checking"
    FINALIZED = "finalized"
    FAILED = "failed"


class TaskStorageMigrationPhase(str, Enum):
    PREPARED = "prepared"
    SOURCE_PAUSED = "source_paused"
    TARGET_READY = "target_ready"
    CONTENT_MOVED = "content_moved"
    CHECKING = "checking"
    COMMITTING = "committing"
    FINALIZED = "finalized"
    FAILED = "failed"


class TaskStorageMigration(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action_id: str | None = None
    task_id: str
    torrent_hash: str
    source_downloader_id: str
    target_downloader_id: str
    source_directory_id: str
    target_directory_id: str
    source_save_path: str
    target_save_path: str
    source_content_path: str | None = None
    target_content_path: str | None = None
    previous_task_status: TaskStatus
    move_content: bool = True
    cleanup_source_torrent: bool = True
    phase: TaskStorageMigrationPhase = TaskStorageMigrationPhase.PREPARED
    source_paused: bool = False
    target_added_by_migration: bool = False
    content_moved: bool = False
    library_files_moved: bool = False
    status: TaskStorageMigrationStatus = TaskStorageMigrationStatus.PENDING
    reason: str | None = None
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    finalized_at: datetime | None = None
