from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.media_id import MediaID
from app.schemas.domain.download import TaskStatus


class DownloadTaskEventMeta(BaseModel):
    task_id: str
    media_id: MediaID
    status: TaskStatus
    downloader_id: str | None = None
    resource_title: str | None = None
    torrent_name: str | None = None
    torrent_hash: str | None = None
    progress: float | None = None
    selected_files: list[int] = Field(default_factory=list)
    total_files: int | None = None


class DownloadFailedEventMeta(BaseModel):
    command_id: str
    media_id: MediaID
    resource_title: str | None = None
    result_id: str = ""
    directory_id: str = ""
    selected_files: list[int] = Field(default_factory=list)
    error: str = ""
    error_key: str | None = None
    error_params: dict[str, str] = Field(default_factory=dict)


class MediaDeletedEventMeta(BaseModel):
    media_id: MediaID | None = None
    directory_id: str
    task_id: str | None = None
    downloader_id: str | None = None
    torrent_hash: str | None = None
    paths: list[str] = Field(default_factory=list)
    media_root_dir: str | None = None
    delete_scope: str = "file"


class ImportedMediaFile(BaseModel):
    destination_path: str
    episode_number: int | None = None
    episode_numbers: list[int] = Field(default_factory=list)


class MediaImportCompletedEventMeta(BaseModel):
    task_id: str
    directory_id: str
    media_id: MediaID
    resource_title: str | None = None
    torrent_name: str | None = None
    file_path: str = ""
    imported_files: list[ImportedMediaFile] = Field(default_factory=list)


class MediaImportStartedEventMeta(BaseModel):
    task_id: str
    directory_id: str
    media_id: MediaID
    resource_title: str | None = None
    torrent_name: str | None = None


class MediaImportFailedEventMeta(BaseModel):
    task_id: str
    directory_id: str
    media_id: MediaID
    resource_title: str | None = None
    torrent_name: str | None = None
    error: str = ""
    error_key: str | None = None
    error_params: dict[str, str] = Field(default_factory=dict)


class MediaServerSyncEventMeta(BaseModel):
    media_id: MediaID
    media_server_id: str | None = None
    file_path: str = ""
    file_count: int = 0
    nfo_count: int = 0
    image_count: int = 0
    trigger: str = ""
    error: str = ""


class DanmuGenerateEventMeta(BaseModel):
    media_id: MediaID
    video_path: str
    episode_number: int | None = None
    provider: str | None = None
    xml_path: str | None = None
    ass_path: str | None = None
    error: str = ""
    error_key: str | None = None


class LibraryFileMissingEventMeta(BaseModel):
    task_id: str
    directory_id: str
    media_id: MediaID
    library_file_id: str
    path: str
