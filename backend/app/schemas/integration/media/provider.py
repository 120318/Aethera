from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.domain.media import EpisodeInfo, MediaSeasonInfo, PersonInfo, SeasonDetails
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.schedule import MovieReleaseDateDetail
from app.schemas.domain.vendor import Vendor


class ProviderRating(BaseModel):
    value: float | None = None
    count: int | None = None


class ProviderSearchItem(BaseModel):
    provider_id: str
    title: str
    year: int | None = None
    media_type: MediaType
    rating: ProviderRating = Field(default_factory=ProviderRating)
    poster_path: str | None = None
    overview: str | None = None
    original_language: str | None = None
    genre_ids: list[int] = Field(default_factory=list)
    subtitle: str | None = None


class ProviderMediaDetail(BaseModel):
    provider_id: str
    title: str
    original_title: str | None = None
    media_type: MediaType
    year: int | None = None
    overview: str | None = None
    genres: list[str] = Field(default_factory=list)
    poster_path: str | None = None
    rating: ProviderRating = Field(default_factory=ProviderRating)
    duration: str | None = None
    vendors: list[Vendor] = Field(default_factory=list)
    release_date: str | None = None
    original_language: str | None = None
    season_number: int | None = None
    episodes_count: int | None = None


class ProviderCredits(BaseModel):
    actors: list[PersonInfo] = Field(default_factory=list)
    directors: list[PersonInfo] = Field(default_factory=list)


class ProviderExternalIds(BaseModel):
    imdb_id: str | None = None
    tvdb_id: str | None = None


class ProviderMediaBundle(BaseModel):
    provider_id: str
    title: str
    original_title: str | None = None
    media_type: MediaType
    overview: str | None = None
    poster_path: str | None = None
    backdrop_path: str | None = None
    logo_path: str | None = None
    rating: ProviderRating = Field(default_factory=ProviderRating)
    status: str | None = None
    original_language: str | None = None
    runtime: str | None = None
    episodes_count: int | None = None
    seasons_count: int | None = None
    release_date: str | None = None
    premiere_release_date: str | None = None
    theatrical_limited_release_date: str | None = None
    theatrical_release_date: str | None = None
    digital_release_date: str | None = None
    physical_release_date: str | None = None
    tv_release_date: str | None = None
    release_dates: list[MovieReleaseDateDetail] = Field(default_factory=list)
    first_air_date: str | None = None
    genres: list[str] = Field(default_factory=list)
    actors: list[PersonInfo] = Field(default_factory=list)
    directors: list[PersonInfo] = Field(default_factory=list)
    studios: list[str] = Field(default_factory=list)
    networks: list[ProviderPlatformInfo] = Field(default_factory=list)
    seasons: list[MediaSeasonInfo] = Field(default_factory=list)
    selected_season_details: SeasonDetails | None = None
    next_episode_to_air: EpisodeInfo | None = None
    external_ids: ProviderExternalIds = Field(default_factory=ProviderExternalIds)
    vendors: list[Vendor] = Field(default_factory=list)


class ProviderPlatformInfo(BaseModel):
    id: str | None = None
    name: str | None = None
    logo: str | None = None
    url: str | None = None
    region: str | None = None


class ProviderWatchProviders(BaseModel):
    link: str | None = None
    flatrate: list[ProviderPlatformInfo] = Field(default_factory=list)
    ads: list[ProviderPlatformInfo] = Field(default_factory=list)
    free: list[ProviderPlatformInfo] = Field(default_factory=list)
    buy: list[ProviderPlatformInfo] = Field(default_factory=list)
    rent: list[ProviderPlatformInfo] = Field(default_factory=list)


class ProviderReleaseDateEntry(BaseModel):
    type: int | None = None
    release_date: str | None = None
    certification: str | None = None
    note: str | None = None
    descriptors: list[str] = Field(default_factory=list)
    iso_639_1: str | None = None


class ProviderReleaseRegion(BaseModel):
    iso_3166_1: str | None = None
    release_dates: list[ProviderReleaseDateEntry] = Field(default_factory=list)


class ProviderScheduleDetail(BaseModel):
    status: str | None = None
    networks: list[ProviderPlatformInfo] = Field(default_factory=list)
    seasons: list[MediaSeasonInfo] = Field(default_factory=list)
