from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.domain.media_types import MediaType
from app.schemas.domain.schedule import SchedulePlatform
from app.schemas.media_id import MediaID


CalendarScope = Literal["all", "followed", "subscribed"]


class CalendarAiringItem(BaseModel):
    date: str
    kind: Literal["movie_release", "movie_theatrical_release", "movie_digital_release", "movie_physical_release", "tv_episode_air"]
    media_id: MediaID
    media_type: MediaType
    title: str
    year: int | None = None
    poster: str | None = None
    vote_average: float | None = None
    vote_count: int | None = None
    rating_count: int | None = None
    rating_source: str | None = None
    platforms: list[SchedulePlatform] = Field(default_factory=list)
    season_number: int | None = None
    episode_number: int | None = None
    episode_title: str | None = None


class CalendarAiringsResponse(BaseModel):
    from_date: str
    to_date: str
    scope: CalendarScope
    count: int
    data: list[CalendarAiringItem]
