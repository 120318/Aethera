from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.domain.media_types import MediaType


class DanmuComment(BaseModel):
    time_seconds: float
    text: str
    mode: str = "scroll"
    color: str = "ffffff"


class DanmuEpisodeCandidate(BaseModel):
    provider: str
    episode_number: int | None = None
    title: str = ""
    duration_seconds: int | None = None
    external_id: str = ""


class DanmuFetchInput(BaseModel):
    media_type: MediaType | None = None
    episode_number: int | None = None
    absolute_episode_number: int | None = None
    episode_count: int | None = None
    title: str = ""
    season_number: int | None = None


class DanmuFetchResult(BaseModel):
    provider: str
    comments: list[DanmuComment] = Field(default_factory=list)
    source_id: str = ""
    source_duration_seconds: float | None = None
