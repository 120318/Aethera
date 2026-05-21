from typing import Literal, Optional

from pydantic import BaseModel, Field
from app.schemas.domain.media_types import MediaType


class SchedulePlatform(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    logo: Optional[str] = None
    url: Optional[str] = None
    region: Optional[str] = None


class ScheduleEpisode(BaseModel):
    season_number: Optional[int] = None
    episode_number: Optional[int] = None
    air_date: Optional[str] = None
    title: Optional[str] = None


class MovieReleaseDateDetail(BaseModel):
    region: Optional[str] = None
    type: Optional[int] = None
    release_date: Optional[str] = None
    certification: Optional[str] = None
    note: Optional[str] = None
    descriptors: list[str] = Field(default_factory=list)
    language: Optional[str] = None


class MediaScheduleSummary(BaseModel):
    media_type: MediaType
    status_label: Optional[str] = None
    first_air_date: Optional[str] = None
    networks: list[SchedulePlatform] = Field(default_factory=list)
    aired_episode_count: int = 0
    latest_aired_episode: Optional[ScheduleEpisode] = None
    next_episode_to_air: Optional[ScheduleEpisode] = None
    premiere_release_date: Optional[str] = None
    theatrical_limited_release_date: Optional[str] = None
    theatrical_release_date: Optional[str] = None
    digital_release_date: Optional[str] = None
    physical_release_date: Optional[str] = None
    tv_release_date: Optional[str] = None
    release_dates: list[MovieReleaseDateDetail] = Field(default_factory=list)
    online_platforms: list[SchedulePlatform] = Field(default_factory=list)


class ScheduleAiring(BaseModel):
    date: str
    kind: Literal["movie_theatrical_release", "movie_digital_release", "movie_physical_release", "tv_episode_air"]
    season_number: Optional[int] = None
    episode_number: Optional[int] = None
    episode_title: Optional[str] = None
    platforms: list[SchedulePlatform] = Field(default_factory=list)
