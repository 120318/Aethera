from datetime import datetime

from pydantic import BaseModel, Field, model_validator
from app.schemas.domain.media_types import MediaType
from app.schemas.media_id import MediaID


class MediaMonitorState(BaseModel):
    subscription_id: str | None = None
    subscribed: bool = False
    followed: bool = False
    last_run_at: float | None = None


class MediaIssueSnapshot(BaseModel):
    has_issues: bool = False
    codes: list[str] = Field(default_factory=list)
    summary: str = ""
    summary_key: str | None = None
    summary_params: dict[str, str] = Field(default_factory=dict)


class MediaTaskSummary(BaseModel):
    media_id: MediaID
    task_count: int = 0
    active_task_count: int = 0
    error_task_count: int = 0
    file_missing_task_count: int = 0
    seeding_absent_task_count: int = 0
    last_task_at: datetime | None = None
    last_task_message_key: str | None = None
    last_task_message_params: dict[str, str] = Field(default_factory=dict)


class MediaLibrarySummary(BaseModel):
    media_id: MediaID
    library_count: int = 0
    library_episode_count: int = 0
    original_disc_package_count: int = 0
    library_size: int = 0
    last_library_at: datetime | None = None


class MediaRecentEventSummary(BaseModel):
    media_id: MediaID
    last_event_at: datetime | None = None
    last_event_message_key: str | None = None
    last_event_message_params: dict[str, str] = Field(default_factory=dict)
    has_recent_error: bool = False
    has_recent_warning: bool = False


class MediaManagementSummary(BaseModel):
    total: int = 0
    subscribed: int = 0
    followed: int = 0
    downloading: int = 0
    in_library: int = 0
    issues: int = 0


class MediaManagementListRow(BaseModel):
    media_id: MediaID
    season_number: int | None = None
    title: str
    media_type: MediaType
    poster_path: str | None = None
    year: int
    subscribed: int = 0
    followed: int = 0
    task_count: int = 0
    active_task_count: int = 0
    error_task_count: int = 0
    file_missing_task_count: int = 0
    seeding_absent_task_count: int = 0
    library_count: int = 0
    library_episode_count: int = 0
    original_disc_package_count: int = 0
    library_size: int = 0
    activity_ts: float = 0.0
    last_task_ts: float | None = None
    last_library_ts: float | None = None
    last_event_ts: float | None = None
    last_artifact_ts: float | None = None
    last_event_message_key: str | None = None
    last_event_message_params: dict[str, str] = Field(default_factory=dict)
    has_recent_error: int = 0
    has_recent_warning: int = 0
    has_issues: bool = False

    @model_validator(mode="after")
    def validate_tv_season_scope(self) -> "MediaManagementListRow":
        if self.media_type == MediaType.tv and self.season_number is None:
            raise ValueError("tv media management row must include season_number")
        return self


class MediaManagementRowsPage(BaseModel):
    total: int
    rows: list[MediaManagementListRow] = Field(default_factory=list)


class MediaManagementListItem(BaseModel):
    media_id: MediaID
    season_number: int | None = None
    title: str
    media_type: MediaType
    year: int
    poster_path: str | None = None
    monitor: MediaMonitorState = Field(default_factory=MediaMonitorState)
    task_count: int = 0
    active_task_count: int = 0
    error_task_count: int = 0
    library_count: int = 0
    library_episode_count: int = 0
    original_disc_package_count: int = 0
    library_size: int = 0
    last_activity_at: datetime | None = None
    last_activity_message_key: str | None = None
    last_activity_message_params: dict[str, str] = Field(default_factory=dict)
    issues: MediaIssueSnapshot = Field(default_factory=MediaIssueSnapshot)

    @model_validator(mode="after")
    def validate_tv_season_scope(self) -> "MediaManagementListItem":
        if self.media_type == MediaType.tv and self.season_number is None:
            raise ValueError("tv media management item must include season_number")
        return self


class MediaManagementItemsPage(BaseModel):
    total: int
    items: list[MediaManagementListItem]
