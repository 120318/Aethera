from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class DirectoryIntegrityScope(str, Enum):
    library = "library"
    download = "download"


class DirectoryIntegrityIssueType(str, Enum):
    unmanaged_library_file = "unmanaged_library_file"
    missing_library_file = "missing_library_file"
    task_missing_library_file = "task_missing_library_file"
    library_file_missing_task = "library_file_missing_task"
    unmanaged_download_entry = "unmanaged_download_entry"
    missing_download_file = "missing_download_file"
    missing_downloader_torrent = "missing_downloader_torrent"
    unhealthy_downloader_torrent = "unhealthy_downloader_torrent"


def default_directory_integrity_issue_types() -> list[DirectoryIntegrityIssueType]:
    return list(DirectoryIntegrityIssueType)


class DirectoryIntegrityPolicy(BaseModel):
    directory_id: str
    enabled: bool = True
    scan_library: bool = True
    scan_download: bool = True
    issue_types: list[DirectoryIntegrityIssueType] = Field(default_factory=default_directory_integrity_issue_types)

    @classmethod
    def default_for_directory(cls, directory_id: str) -> "DirectoryIntegrityPolicy":
        return cls(directory_id=directory_id)


class DirectoryIntegrityItem(BaseModel):
    id: str
    issue_type: DirectoryIntegrityIssueType
    scope: DirectoryIntegrityScope
    directory_id: str
    directory_name: str = ""
    display_name: str = ""
    path: str
    relative_path: str = ""
    size: int | None = None
    file_created_at: float | None = None
    record_created_at: float | None = None
    task_completed_at: float | None = None
    library_file_name: str = ""
    library_file_id: str | None = None
    task_id: str | None = None
    media_id: str | None = None
    media_title: str = ""
    media_year: int | None = None
    downloader_state: str = ""
    downloader_status_message: str = ""
    tracker_messages: list[str] = Field(default_factory=list)
    repairable: bool = True
    repair_action: str = ""
    reason: str = ""


class DirectoryIntegrityCountSummary(BaseModel):
    total: int = 0
    repairable: int = 0
    unmanaged_library_files: int = 0
    missing_library_files: int = 0
    tasks_missing_library_files: int = 0
    library_files_missing_tasks: int = 0
    unmanaged_download_entries: int = 0
    missing_download_files: int = 0
    missing_downloader_torrents: int = 0
    unhealthy_downloader_torrents: int = 0


class DirectoryIntegrityDirectorySummary(DirectoryIntegrityCountSummary):
    directory_id: str
    directory_name: str = ""
    media_type: str = ""
    physical_size: int = 0
    logical_size: int = 0
    library_logical_size: int = 0
    download_logical_size: int = 0


class DirectoryIntegritySummary(DirectoryIntegrityCountSummary):
    physical_size: int = 0
    logical_size: int = 0
    library_logical_size: int = 0
    download_logical_size: int = 0
    directories: list[DirectoryIntegrityDirectorySummary] = Field(default_factory=list)


class DirectoryIntegrityResult(BaseModel):
    scan_id: str
    scanned_at: float
    summary: DirectoryIntegritySummary = Field(default_factory=DirectoryIntegritySummary)
    items: list[DirectoryIntegrityItem] = Field(default_factory=list)


class DirectoryIntegrityRepairRequest(BaseModel):
    scan_id: str
    item_ids: list[str] = Field(default_factory=list)


class DirectoryIntegrityRepairResult(BaseModel):
    requested_count: int = 0
    repaired_count: int = 0
    failed_count: int = 0


class DirectoryIntegrityPoliciesResponse(BaseModel):
    directories: list[dict[str, str | bool]] = Field(default_factory=list)
    policies: list[DirectoryIntegrityPolicy] = Field(default_factory=list)


class DirectoryIntegrityPoliciesUpdateRequest(BaseModel):
    policies: list[DirectoryIntegrityPolicy] = Field(default_factory=list)
