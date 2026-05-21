from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from app.schemas.media_id import MediaID


class MediaExternalMappingRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    media_type: str
    media_id: MediaID
    tmdb_id: int | None = None
    imdb_id: str | None = None
    douban_id: str | None = None
    season_number: int | None = None
    episode_count_override: int | None = None
    updated_at: float | None = None
