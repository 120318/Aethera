from pydantic import BaseModel, Field

from app.schemas.domain.media_types import MediaType


class SiteInfo(BaseModel):
    """Internal helper."""
    id: str
    name: str
    description: str
    language: str
    type: str


class SiteSearchCapabilities(BaseModel):
    supports_search: bool = True
    supports_movie_search: bool = True
    supports_tv_search: bool = True
    search_params: set[str] = Field(default_factory=set)
    movie_search_params: set[str] = Field(default_factory=set)
    tv_search_params: set[str] = Field(default_factory=set)
    supports_doubanid: bool = False
    supports_imdbid: bool = False
    supports_q: bool = True
    supports_movie: bool = True
    supports_tv: bool = True


class IndexerSiteSetting(BaseModel):
    site_id: str
    enabled: bool = True
    disable_title: bool = False
    disable_imdb: bool = False
    disable_douban: bool = False
    media_types: list[MediaType] | None = None


def supported_media_types_from_caps(capabilities: SiteSearchCapabilities) -> set[MediaType]:
    supported_media_types: set[MediaType] = set()
    if capabilities.supports_movie:
        supported_media_types.add(MediaType.movie)
    if capabilities.supports_tv:
        supported_media_types.add(MediaType.tv)
    return supported_media_types


def effective_media_types_from_caps(
    capabilities: SiteSearchCapabilities,
    media_types: list[MediaType] | None,
) -> set[MediaType]:
    supported_media_types = supported_media_types_from_caps(capabilities)
    if media_types is None:
        return supported_media_types
    requested_media_types = set(media_types)
    return requested_media_types & supported_media_types
