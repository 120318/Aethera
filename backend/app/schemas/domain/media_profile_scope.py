from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.schemas.domain.media import MediaSeasonInfo
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.schedule import MovieReleaseDateDetail, ScheduleEpisode
from app.schemas.media_id import MediaID


class MediaProfilePlatform(BaseModel):
    key: str
    id: str | None = None
    name: str | None = None
    logo: str | None = None
    region: str | None = None
    roles: list[str] = Field(default_factory=list)
    display_url: str | None = None
    fetch_url: str | None = None
    source: str | None = None

    @field_validator("key")
    @classmethod
    def validate_key(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("platform key must be non-empty")
        return normalized


class MediaProfileScopeAiring(BaseModel):
    date: str
    kind: str
    season_number: int | None = None
    episode_number: int | None = None
    episode_title: str | None = None
    platform_keys: list[str] = Field(default_factory=list)


class MediaProfileScope(BaseModel):
    media_id: MediaID
    season_number: int
    media_type: MediaType
    name: str | None = None
    air_date: str | None = None
    episode_count: int | None = None
    episode_count_override: int | None = None
    poster_path: str | None = None
    douban_id: str | None = None
    douban_vote_average: float | None = None
    douban_rating_count: int | None = None
    first_air_date: str | None = None
    status_label: str | None = None
    aired_episode_count: int = 0
    latest_aired_episode: ScheduleEpisode | None = None
    next_episode_to_air: ScheduleEpisode | None = None
    premiere_release_date: str | None = None
    theatrical_limited_release_date: str | None = None
    theatrical_release_date: str | None = None
    digital_release_date: str | None = None
    physical_release_date: str | None = None
    tv_release_date: str | None = None
    release_dates: list[MovieReleaseDateDetail] = Field(default_factory=list)
    platforms: list[MediaProfilePlatform] = Field(default_factory=list)
    airings: list[MediaProfileScopeAiring] = Field(default_factory=list)
    updated_at: float

    @field_validator("season_number")
    @classmethod
    def validate_scope_number(cls, value: int) -> int:
        if int(value) < 0:
            raise ValueError("season_number must be >= 0")
        return int(value)

    def to_season_info(self) -> MediaSeasonInfo:
        return MediaSeasonInfo(
            season_number=self.season_number,
            name=self.name,
            air_date=self.air_date,
            episode_count=self.episode_count,
            episode_count_override=self.episode_count_override,
            poster_path=self.poster_path,
            douban_id=self.douban_id,
            douban_vote_average=self.douban_vote_average,
            douban_rating_count=self.douban_rating_count,
        )
