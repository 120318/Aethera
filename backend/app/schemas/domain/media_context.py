from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.domain.media_types import MediaType
from app.schemas.media_id import MediaID


MediaPrimarySource = Literal["douban", "tmdb"]


class MediaCapabilities(BaseModel):
    has_enhanced_detail: bool = False
    has_schedule: bool = False
    has_season_episode_detail: bool = False
    has_movie_release_window: bool = False
    has_watch_providers: bool = False
    can_generate_enhanced_nfo: bool = False


class ResolvedMediaContext(BaseModel):
    media_id: MediaID
    media_type: MediaType
    title: str
    year: int
    douban_id: str | None = None
    imdb_id: str | None = None
    tmdb_id: int | None = None
    season_number: int | None = None
    primary_metadata_source: MediaPrimarySource = "douban"
    metadata_capabilities: MediaCapabilities = Field(default_factory=MediaCapabilities)
