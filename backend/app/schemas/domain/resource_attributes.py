from enum import StrEnum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.domain.quality_values import (
    AudioChannelsValue,
    AudioCodecValue,
    ColorDepthValue,
    HdrTypeValue,
    ResourceFormValue,
    ResolutionValue,
    SourceValue,
    VideoCodecValue,
)

class ResourceFormEvidence(StrEnum):
    TITLE = "title"
    TORRENT_STRUCTURE = "torrent_structure"


class PackageLayoutValue(StrEnum):
    BDMV = "BDMV"
    ISO = "ISO"
    VIDEO_TS = "VIDEO_TS"


class ResourceAttributes(BaseModel):
    """Internal helper."""
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)

    # Internal note.
    title: Optional[str] = None
    desc: Optional[str] = None

    # Internal note.
    groups: List[str] = Field(default_factory=list)
    sources: List[SourceValue] = Field(default_factory=list)
    resource_form: Optional[ResourceFormValue] = None
    resource_form_evidence: Optional[ResourceFormEvidence] = None
    package_layout: Optional[PackageLayoutValue] = None
    versions: List[str] = Field(default_factory=list)
    seasons: List[int] = Field(default_factory=list)
    episodes: List[int] = Field(default_factory=lambda: [1])
    disc_number: Optional[int] = None
    disc_total: Optional[int] = None
    platforms: List[str] = Field(default_factory=list)

    # Internal note.
    resolution: Optional[ResolutionValue] = None
    video_codec: Optional[VideoCodecValue] = None
    audio_codec: Optional[AudioCodecValue] = None
    hdr_type: Optional[HdrTypeValue] = None
    audio_channels: Optional[AudioChannelsValue] = None
    color_depth: Optional[ColorDepthValue] = None

    # Internal note.
    content_type: Optional[str] = None
    language: Optional[str] = None
    subtitle: Optional[str] = None

    # Internal note.
    tmdb_id: Optional[str] = None
    imdb_id: Optional[str] = None
    year: Optional[int] = None
    release_year: Optional[int] = None
    release_date: Optional[str] = None
    first_air_date: Optional[str] = None
    runtime: Optional[str] = None
    episode_title: Optional[str] = None

    @model_validator(mode="after")
    def default_resource_form_evidence(self) -> "ResourceAttributes":
        if self.resource_form is not None and self.resource_form_evidence is None:
            self.resource_form_evidence = ResourceFormEvidence.TITLE
        return self

    @field_validator("hdr_type", mode="before")
    @classmethod
    def normalize_hdr_type(cls, value):
        if value == HdrTypeValue.HDR or value == HdrTypeValue.HDR.value:
            return HdrTypeValue.HDR10
        return value


class ResourceDisplayAttributes(ResourceAttributes):
    """Runtime-only attributes for API responses."""

    tags: List[str] = Field(default_factory=list)

class NamingContext(BaseModel):
    """Naming context for template formatting"""
    resource_title: str
    attributes: ResourceAttributes
    size: Optional[int] = None
    torrent_name: Optional[str] = None
    disc_package_name: Optional[str] = None
    season_number: Optional[int] = None
    media_type: Optional[str] = None
    naming_category: Optional[str] = None

class EnhancedResourceSchema(BaseModel):
    id: str = Field(...)
    title: str = Field(...)
    category: Optional[str] = None
    site: Optional[str] = None
    size: Optional[str] = None
    seeders: Optional[int] = None
    leechers: Optional[int] = None
    publish_date: Optional[str] = None
    download_url: Optional[str] = None
    detail_url: Optional[str] = None
    description: Optional[str] = None

    attributes: ResourceAttributes = Field(...)


class MediaInfo(BaseModel):
    id: str = Field(...)
    type: str = Field(...)
    media_title: Optional[str] = None
    season_number: Optional[int] = None
