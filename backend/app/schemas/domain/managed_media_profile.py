from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.domain.media import MediaSeasonInfo, PersonInfo
from app.schemas.domain.media_context import MediaCapabilities, MediaPrimarySource
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.schedule import MovieReleaseDateDetail, ScheduleAiring, ScheduleEpisode, SchedulePlatform
from app.schemas.domain.vendor import Vendor
from app.schemas.media_id import MediaID


class ManagedMediaProfile(BaseModel):
    media_id: MediaID
    media_type: MediaType
    title: str
    original_title: Optional[str] = None
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    logo_path: Optional[str] = None
    year: Optional[int] = None
    overview: Optional[str] = None
    genres: list[str] = Field(default_factory=list)
    imdb_id: Optional[str] = None
    tmdb_id: Optional[int] = None
    primary_metadata_source: MediaPrimarySource = "douban"
    metadata_capabilities: MediaCapabilities = Field(default_factory=MediaCapabilities)
    tvdb_id: Optional[str] = None
    actors: list[PersonInfo] = Field(default_factory=list)
    directors: list[PersonInfo] = Field(default_factory=list)
    studios: list[str] = Field(default_factory=list)
    vendors: list[Vendor] = Field(default_factory=list)
    duration: Optional[str] = None
    rating_count: Optional[int] = None
    vote_average: Optional[float] = None
    vote_count: Optional[int] = None
    rating_source: Optional[str] = None
    douban_vote_average: Optional[float] = None
    douban_rating_count: Optional[int] = None
    tmdb_vote_average: Optional[float] = None
    tmdb_rating_count: Optional[int] = None
    release_date: Optional[str] = None
    seasons_count: Optional[int] = None
    episodes_count: Optional[int] = None
    seasons: list[MediaSeasonInfo] = Field(default_factory=list)
    status: Optional[str] = None
    original_language: Optional[str] = None

    status_label: Optional[str] = None
    first_air_date: Optional[str] = None
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
    networks: list[SchedulePlatform] = Field(default_factory=list)
    online_platforms: list[SchedulePlatform] = Field(default_factory=list)
    airings: list[ScheduleAiring] = Field(default_factory=list)

    is_active: bool = True
    last_seen_at: float
    inactive_since: Optional[float] = None
    detail_ready: bool = False
    simple_info_updated_at: Optional[float] = None
    detail_updated_at: Optional[float] = None
    schedule_updated_at: Optional[float] = None
    created_at: float
    updated_at: float
