from datetime import datetime
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.media_id import MediaIDModel, MediaID
from app.schemas.domain.media import MediaExecutionSnapshot
from app.schemas.domain.resource_attributes import ResourceAttributes
from app.schemas.domain.resource_search import ResourceSearchResult
from app.schemas.domain.torrent import TorrentMetadata, TorrentFileItem


class TaskStatus(str, Enum):
    """Task status enum for state machine"""

    PENDING = "pending"
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    ERROR = "error"
    FINISHED = "finished"
    TRANSFERRING = "transferring"
    MIGRATING = "migrating"
    COMPLETED = "completed"
    PARTIAL_MISSING = "partial_missing"
    SEEDING_ABSENT = "seeding_absent"
    FILE_MISSING = "file_missing"
    VOID = "void"


class TaskErrorStage(str, Enum):
    DOWNLOAD = "download"
    TRANSFER = "transfer"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class TaskEpisodeCoverageSource(str, Enum):
    PARSED_CONTEXT = "parsed_context"
    FILE_METADATA = "file_metadata"
    TASK_CONTEXT = "task_context"
    UNKNOWN = "unknown"


class TaskEpisodeCoverage(BaseModel):
    season_number: int | None = None
    episode_numbers: list[int] = Field(default_factory=list)
    source: TaskEpisodeCoverageSource = TaskEpisodeCoverageSource.UNKNOWN
    season_mismatch: bool = False
    episode_mismatch: bool = False

    @property
    def has_known_season(self) -> bool:
        return self.season_number is not None and self.season_number > 0


class TaskContext(BaseModel):
    """Internal helper."""

    model_config = ConfigDict(from_attributes=True)

    # Internal note.
    indexer: str | None = None
    download_url: str
    page_url: str | None = None

    # Internal note.
    resource_title: str | None = None  # Internal note.
    media: MediaExecutionSnapshot
    parsed_attributes: ResourceAttributes | None = None  # Internal note.

    # Internal note.
    directory_id: str
    selected_files: list[int] = []

    # Internal note.
    search_result: ResourceSearchResult | None = None


class TaskData(MediaIDModel):
    """Model for download task data stored in the database."""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        from_attributes=True,
    )

    id: str
    torrent_hash: str

    status: TaskStatus
    error_stage: TaskErrorStage | None = None
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    error_key: str | None = None
    error_params: dict[str, str] = Field(default_factory=dict)

    context: TaskContext

    downloader_id: str | None = None
    download_client: str | None = Field(default=None, description="Field description")
    download_client_url: str | None = Field(default=None, description="Field description")
    save_path: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    metadata: TorrentMetadata | None = None


TaskData.model_rebuild()


class TransferFileResult(BaseModel):
    """Model for individual file transfer result."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    source_path: str
    destination_path: str
    file_item: TorrentFileItem
    file_index: int
    episode_number: int | None = None
    episode_numbers: list[int] = Field(default_factory=list)


class DownloadFileInfo(BaseModel):
    """Model for a file within a download."""

    index: int
    name: str
    size: int
    progress: float
    priority: int
    is_selected: bool = True


class DownloadInfo(BaseModel):
    """Model for download information."""

    hash: str
    name: str
    size: int
    progress: float
    state: str
    save_path: str
    added_on: datetime
    completion_on: datetime | None = None
    content_path: str = ""
    category: str | None = None
    tags: list[str] = Field(default_factory=list)


class TransferResult(BaseModel):
    """Result of a transfer operation."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    transferred_files: list[TransferFileResult]
    success: bool = True
    error_key: str | None = None
    error_params: dict[str, str] = Field(default_factory=dict)
    files: list[DownloadFileInfo] | None = None


class BatchJobResult(BaseModel):
    """Result of a batch job operation."""

    processed: int = 0
    updated: int = 0
    completed: int = 0
    errors: int = 0
    error: str | None = None


class DownloadTaskCreateInput(BaseModel):
    media: MediaExecutionSnapshot
    directory_id: str
    selected_files: list[int] | None = None
    result_id: str


class TaskFieldPatch(BaseModel):
    status: TaskStatus | None = None
    progress: float | None = Field(default=None, ge=0.0, le=1.0)
    error_key: str | None = None
    error_params: dict[str, str] | None = None
    error_stage: TaskErrorStage | None = None
    updated_at: datetime | None = None
