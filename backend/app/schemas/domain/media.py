from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.media_id import MediaID, MediaIDModel
from app.schemas.domain.media_context import MediaCapabilities, MediaPrimarySource
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.schedule import MediaScheduleSummary, MovieReleaseDateDetail, ScheduleAiring, SchedulePlatform
from app.schemas.domain.vendor import Vendor


class Avatar(BaseModel):
    model_config = ConfigDict(extra="ignore")

    large: Optional[str] = None
    normal: Optional[str] = None


class PersonInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: Optional[str] = None
    id: Optional[str] = None
    avatar: Optional[Avatar] = None
    character: Optional[str] = None
    roles: List[str] = Field(default_factory=list)
    latin_name: Optional[str] = None


class EpisodeInfo(BaseModel):
    id: int | None = None
    season_number: int
    episode_number: int
    air_date: str | None = None
    title: str | None = None
    overview: str | None = None
    runtime: int | None = None
    still_path: str | None = None
    vote_average: float | None = None
    vote_count: int | None = None

    @field_validator("season_number", "episode_number")
    @classmethod
    def validate_positive_numbers(cls, value: int) -> int:
        if int(value) <= 0:
            raise ValueError("episode identifiers must be positive integers")
        return int(value)


class SeasonDetails(BaseModel):
    id: int | None = None
    season_number: int
    name: str | None = None
    overview: str | None = None
    air_date: str | None = None
    poster_path: str | None = None
    episode_count: int | None = None
    episodes: list[EpisodeInfo] = Field(default_factory=list)

    @field_validator("season_number")
    @classmethod
    def validate_season_number(cls, value: int) -> int:
        if int(value) <= 0:
            raise ValueError("season_number must be a positive integer")
        return int(value)


class MediaSeasonInfo(BaseModel):
    season_number: int
    name: Optional[str] = None
    air_date: Optional[str] = None
    episode_count: Optional[int] = None
    episode_count_override: Optional[int] = None
    poster_path: Optional[str] = None
    douban_id: Optional[str] = None
    douban_vote_average: Optional[float] = None
    douban_rating_count: Optional[int] = None


class MediaTarget(MediaIDModel):
    season_number: Optional[int] = None

    @model_validator(mode="after")
    def validate_target_contract(self) -> "MediaTarget":
        if self.season_number is not None and self.season_number <= 0:
            raise ValueError("season_number must be a positive integer when present")
        if self.media_id.media_type == MediaType.movie and self.season_number is not None:
            raise ValueError("movie media target must not include season_number")
        if type(self) is MediaTarget and self.media_id.media_type == MediaType.tv and self.season_number is None:
            raise ValueError("tv media target must include season_number")
        return self


class MediaIdentity(MediaTarget):
    title: str
    year: int

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("title must be non-empty")
        return normalized

    @field_validator("year")
    @classmethod
    def validate_year(cls, value: int) -> int:
        if int(value) <= 0:
            raise ValueError("year must be a positive integer")
        return int(value)


class MediaExecutionSnapshot(MediaIdentity):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    imdb_id: Optional[str] = None
    douban_id: Optional[str] = None
    tmdb_id: Optional[int] = None
    seasons_count: Optional[int] = None
    episodes_count: Optional[int] = None
    aired_episode_count: int = 0
    next_episode_to_air: Optional[EpisodeInfo] = None
    theatrical_release_date: Optional[str] = None
    digital_release_date: Optional[str] = None
    physical_release_date: Optional[str] = None

    @property
    def media_type(self) -> MediaType:
        return self.media_id.media_type


class MediaFullInfo(MediaIdentity):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    media_id: MediaID
    original_title: Optional[str] = None
    media_type: MediaType = Field(..., description="movie|tv")
    imdb_id: Optional[str] = None
    douban_id: Optional[str] = None
    tmdb_id: Optional[int] = None
    primary_metadata_source: MediaPrimarySource = "douban"
    metadata_capabilities: MediaCapabilities = Field(default_factory=MediaCapabilities)
    tvdb_id: Optional[str] = None
    overview: Optional[str] = None
    genres: List[str] = []
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    logo_path: Optional[str] = None
    actors: List[PersonInfo] = Field(default_factory=list)
    directors: List[PersonInfo] = Field(default_factory=list)
    studios: List[str] = Field(default_factory=list)
    duration: Optional[str] = None
    vendors: List[Vendor] = Field(default_factory=list)
    rating_count: Optional[int] = None
    vote_average: Optional[float] = None
    vote_count: Optional[int] = None
    rating_source: Optional[str] = None
    douban_vote_average: Optional[float] = None
    douban_rating_count: Optional[int] = None
    tmdb_vote_average: Optional[float] = None
    tmdb_rating_count: Optional[int] = None
    release_date: Optional[str] = None
    first_air_date: Optional[str] = None
    episodes_count: Optional[int] = None
    episode_count_override: Optional[int] = None
    seasons_count: Optional[int] = None
    season_number: Optional[int] = None
    seasons: List[MediaSeasonInfo] = Field(default_factory=list)
    next_episode_to_air: Optional[EpisodeInfo] = None
    status_label: Optional[str] = None
    aired_episode_count: int = 0
    latest_aired_episode: Optional[EpisodeInfo] = None
    premiere_release_date: Optional[str] = None
    theatrical_limited_release_date: Optional[str] = None
    theatrical_release_date: Optional[str] = None
    digital_release_date: Optional[str] = None
    physical_release_date: Optional[str] = None
    tv_release_date: Optional[str] = None
    release_dates: List[MovieReleaseDateDetail] = Field(default_factory=list)
    networks: List[SchedulePlatform] = Field(default_factory=list)
    online_platforms: List[SchedulePlatform] = Field(default_factory=list)
    schedule: Optional[MediaScheduleSummary] = None
    airings: List[ScheduleAiring] = Field(default_factory=list)
    status: Optional[str] = None
    viewed: bool = False
    original_language: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def model_dump(self, **kwargs):
        data = super().model_dump(**kwargs)
        if isinstance(data.get("created_at"), datetime):
            data["created_at"] = data["created_at"].isoformat()
        if isinstance(data.get("updated_at"), datetime):
            data["updated_at"] = data["updated_at"].isoformat()
        return data

    @model_validator(mode="after")
    def validate_season_number_contract(self) -> "MediaFullInfo":
        if self.season_number is not None and self.season_number <= 0:
            raise ValueError("season_number must be a positive integer when present")
        if self.media_type == MediaType.movie and self.season_number is not None:
            raise ValueError("movie media must not include season_number")
        return self


MediaFullInfo.model_rebuild()


class MediaSimpleInfo(MediaIdentity):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    media_id: MediaID
    media_type: MediaType = Field(..., description="movie|tv")
    imdb_id: Optional[str] = None
    douban_id: Optional[str] = None
    tmdb_id: Optional[int] = None
    primary_metadata_source: MediaPrimarySource = "douban"
    metadata_capabilities: MediaCapabilities = Field(default_factory=MediaCapabilities)
    seasons_count: Optional[int] = None
    season_number: Optional[int] = None
    seasons: List[MediaSeasonInfo] = Field(default_factory=list)
    episodes_count: Optional[int] = None
    aired_episode_count: int = 0

    @model_validator(mode="after")
    def validate_season_number_contract(self) -> "MediaSimpleInfo":
        if self.season_number is not None and self.season_number <= 0:
            raise ValueError("season_number must be a positive integer when present")
        if self.media_type == MediaType.movie and self.season_number is not None:
            raise ValueError("movie media must not include season_number")
        return self
