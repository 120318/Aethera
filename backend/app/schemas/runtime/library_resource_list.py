from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.domain.quality_values import (
    AudioChannelsValue,
    AudioCodecValue,
    ColorDepthValue,
    HdrTypeValue,
    ResourceFormValue,
    ResolutionValue,
    SourceValue,
    VideoCodecValue,
)
from app.schemas.media_id import MediaID


class LibraryListAttributes(BaseModel):
    groups: list[str] | None = None
    tags: list[str] | None = None
    sources: list[SourceValue] | None = None
    versions: list[str] | None = None
    seasons: list[int] | None = None
    episodes: list[int] | None = None
    resolution: ResolutionValue | None = None
    video_codec: VideoCodecValue | None = None
    audio_codec: AudioCodecValue | None = None
    hdr_type: HdrTypeValue | None = None
    audio_channels: AudioChannelsValue | None = None
    color_depth: ColorDepthValue | None = None
    language: str | None = None
    subtitle: str | None = None
    desc: str | None = None
    content_type: str | None = None
    resource_form: ResourceFormValue | None = None
    package_layout: str | None = None
    disc_number: int | None = None
    disc_total: int | None = None


class LibraryResourceAction(str, Enum):
    VIEW_DETAIL = "view_detail"
    DELETE = "delete"
    MEDIA_SERVER_OPEN = "media_server_open"
    MEDIA_SERVER_SYNC = "media_server_sync"
    DANMU_GENERATE = "danmu_generate"
    CHANGE_DIRECTORY = "change_directory"


class LibraryResourceActionState(BaseModel):
    action: LibraryResourceAction
    available: bool = True
    loading: bool = False
    disabled: bool = False
    disabled_reason_key: str | None = None
    disabled_reason_params: dict[str, str] = Field(default_factory=dict)
    active_command_id: str | None = None
    active_command_type: str | None = None


class LibraryResourceListItem(BaseModel):
    id: str
    file_name: str
    resource_title: str
    task_id: str
    directory_id: str
    directory_name: str
    directory: str | None = None
    size: int
    created_at: float
    attributes: LibraryListAttributes
    is_package: bool = False
    file_count: int = 1
    package_root: str | None = None
    actions: list[LibraryResourceAction] = Field(default_factory=list)
    action_states: list[LibraryResourceActionState] = Field(default_factory=list)


class LibraryMediaServerTarget(BaseModel):
    media_id: MediaID
    season_number: int | None = None


class LibraryMediaServerLinkResolveRequest(BaseModel):
    file_id: str
    target: LibraryMediaServerTarget
    package_root: str = ""


class LibraryMediaServerLinkResolveResponse(BaseModel):
    detail_url: str
    media_server_id: str
    media_server_type: str


class LibraryListResponse(BaseModel):
    media_id: MediaID
    total_episodes: int = 0
    resources: list[LibraryResourceListItem]
