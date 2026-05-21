from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.domain.media_types import MediaType
from app.schemas.media_id import MediaID
from app.schemas.domain.resource_attributes import ResourceAttributes

class LibraryFlags(BaseModel):
    in_library: bool = False
    multi_version: bool = False
    has_4k: bool = False
    has_hd: bool = False


class LibraryFile(BaseModel):
    """Library file model"""
    model_config = ConfigDict(validate_by_name=True, arbitrary_types_allowed=True)

    id: str
    task_id: str
    directory_id: str
    media_id: MediaID
    path: str
    file_name: str | None = None
    file_size: int | None = None
    file_index: int | None = None
    created_at: float
    resource_attributes: ResourceAttributes = Field(default_factory=ResourceAttributes)


class LibraryFileArtifactType(str, Enum):
    nfo = "nfo"
    danmu_xml = "danmu_xml"
    danmu_ass = "danmu_ass"
    poster = "poster"
    fanart = "fanart"
    logo = "logo"


class LibraryFileArtifactStatus(str, Enum):
    pending = "pending"
    succeeded = "succeeded"
    failed = "failed"
    skipped = "skipped"


class LibraryFileArtifact(BaseModel):
    model_config = ConfigDict(validate_by_name=True)

    id: str
    library_file_id: str
    artifact_type: LibraryFileArtifactType
    expected_path: str
    status: LibraryFileArtifactStatus = LibraryFileArtifactStatus.pending
    last_success_at: float | None = None
    last_error: str | None = None
    next_retry_at: float | None = None
    created_at: float
    updated_at: float


class LibraryPackageFileItem(BaseModel):
    id: str
    path: str
    file_name: str | None = None
    relative_path: str
    file_size: int | None = None
    file_index: int | None = None
    is_anchor: bool = False


class LibraryPackageSummary(BaseModel):
    id: str
    task_id: str
    directory_id: str
    media_id: MediaID
    file_name: str
    resource_title: str
    directory: str
    package_root: str
    file_count: int = 1
    total_size: int = 0
    created_at: float
    resource_attributes: ResourceAttributes = Field(default_factory=ResourceAttributes)
    files: list[LibraryPackageFileItem] = Field(default_factory=list)


class LibraryEpisode(BaseModel):
    """Library episode model"""
    model_config = ConfigDict(validate_by_name=True, arbitrary_types_allowed=True)

    media_id: MediaID
    season: int
    episode: int
    file_id: str
    created_at: float

class LibraryMeta(BaseModel):
    """Library metadata model"""
    model_config = ConfigDict(validate_by_name=True, arbitrary_types_allowed=True)

    media_id: MediaID
    status: str = "planned" # planned, active, archived
    created_at: float
    updated_at: float


class LibraryTaskFileHealth(BaseModel):
    total_primary_count: int = 0
    existing_primary_count: int = 0


class LibraryMediaLayoutEntry(BaseModel):
    file_id: str
    absolute_path: str
    file_size: int | None = None
    is_video: bool = False
    episode_numbers: list[int] = Field(default_factory=list)


class LibraryMediaLayout(BaseModel):
    media_id: MediaID
    media_type: MediaType
    entries: list[LibraryMediaLayoutEntry] = Field(default_factory=list)
    root_dirs: list[str] = Field(default_factory=list)
    primary_anchor_file: str | None = None
