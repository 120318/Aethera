from typing import Literal

from app.schemas.media_id import MediaID
from app.schemas.domain.media_types import MediaType
from pydantic import BaseModel, Field, field_serializer


class MediaSearchResult(BaseModel):
    media_id: MediaID | None = None
    source: Literal["douban", "tmdb"] | None = None
    source_id: str | None = None
    douban_id: str | None = None
    season_number: int | None = None
    title: str
    year: int
    vote_average: float | None = None
    media_type: MediaType
    poster_path: str | None = None
    overview: str | None = None
    original_language: str | None = None
    genre_ids: list[int] = Field(default_factory=list)
    rating_count: int | None = None
    subtitle: str | None = None
    subtitle_line1: str | None = None
    subtitle_line2: str | None = None
    viewed: bool = False

    @field_serializer("media_id", when_used="always")
    def serialize_media_id(self, value: MediaID | None) -> str | None:
        return value.to_string() if value else None
