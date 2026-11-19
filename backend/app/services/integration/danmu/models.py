from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.domain.media_types import MediaType


class DanmuComment(BaseModel):
    time_seconds: float
    text: str
    mode: str = "scroll"
    color: str = "ffffff"


class DanmuEpisodeCandidate(BaseModel):
    """A provider video; sequence_index orders a catalog fetched from its beginning."""

    external_id: str
    titles: list[str] = Field(default_factory=list)
    episode_number: int | None = None
    sequence_index: int | None = None
    duration_seconds: float | None = None
    excluded: bool = False


class DanmuEpisodeMatch(BaseModel):
    candidate: DanmuEpisodeCandidate | None = None
    uses_issue_order: bool = False


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
