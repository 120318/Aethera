from __future__ import annotations

from pydantic import BaseModel

from app.schemas.domain.search_models import MediaSearchResult


class DiscoverList(BaseModel):
    key: str
    title: str = ""
    title_key: str
    items: list[MediaSearchResult]
    error: str | None = None


class DiscoverListMeta(BaseModel):
    key: str
    title: str = ""
    title_key: str
    enabled: bool = False
