from __future__ import annotations

from enum import Enum

from pydantic import BaseModel

from app.schemas.domain.media_types import MediaType


class MediaSourceName(str, Enum):
    douban = "douban"
    tmdb = "tmdb"


class MediaSourceLookup(BaseModel):
    source: MediaSourceName
    source_id: str
    media_type: MediaType


class MediaTMDBMappingRequiredData(MediaSourceLookup):
    title: str
    year: int
    search_query: str | None = None
    season_number: int | None = None
    douban_id: str | None = None
