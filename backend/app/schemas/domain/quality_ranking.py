from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from app.schemas.domain.quality_values import (
    AudioChannelsValue,
    AudioCodecValue,
    HdrTypeValue,
    ResourceFormValue,
    ResolutionValue,
    SourceValue,
    VideoCodecValue,
    QUALITY_AUDIO_CHANNELS_VALUES,
    QUALITY_AUDIO_CODEC_VALUES,
    QUALITY_HDR_TYPE_VALUES,
    QUALITY_RESOURCE_FORM_VALUES,
    QUALITY_RESOLUTION_VALUES,
    QUALITY_SOURCE_VALUES,
    QUALITY_VIDEO_CODEC_VALUES,
)

QUALITY_DIMENSION_RESOLUTION = "resolution"
QUALITY_DIMENSION_SOURCE = "source"
QUALITY_DIMENSION_RESOURCE_FORM = "resource_form"
QUALITY_DIMENSION_HDR_TYPE = "hdr_type"
QUALITY_DIMENSION_VIDEO_CODEC = "video_codec"
QUALITY_DIMENSION_AUDIO_CODEC = "audio_codec"
QUALITY_DIMENSION_AUDIO_CHANNELS = "audio_channels"

QUALITY_DIMENSION_ORDER_DEFAULT = [
    QUALITY_DIMENSION_RESOLUTION,
    QUALITY_DIMENSION_SOURCE,
    QUALITY_DIMENSION_RESOURCE_FORM,
    QUALITY_DIMENSION_HDR_TYPE,
    QUALITY_DIMENSION_VIDEO_CODEC,
    QUALITY_DIMENSION_AUDIO_CODEC,
    QUALITY_DIMENSION_AUDIO_CHANNELS,
]

QUALITY_KNOWN_VALUES = {
    QUALITY_DIMENSION_RESOLUTION: QUALITY_RESOLUTION_VALUES,
    QUALITY_DIMENSION_SOURCE: QUALITY_SOURCE_VALUES,
    QUALITY_DIMENSION_RESOURCE_FORM: QUALITY_RESOURCE_FORM_VALUES,
    QUALITY_DIMENSION_HDR_TYPE: QUALITY_HDR_TYPE_VALUES,
    QUALITY_DIMENSION_VIDEO_CODEC: QUALITY_VIDEO_CODEC_VALUES,
    QUALITY_DIMENSION_AUDIO_CODEC: QUALITY_AUDIO_CODEC_VALUES,
    QUALITY_DIMENSION_AUDIO_CHANNELS: QUALITY_AUDIO_CHANNELS_VALUES,
}


def _normalize_order(values: list | None, known_values: list) -> list:
    seen: set[str] = set()
    normalized: list = []
    for value in values or []:
        if value not in known_values or str(value) in seen:
            continue
        normalized.append(value)
        seen.add(str(value))
    for value in known_values:
        if str(value) not in seen:
            normalized.append(value)
    return normalized


class QualityRankingConfig(BaseModel):
    dimension_order: list[str] = Field(default_factory=lambda: list(QUALITY_DIMENSION_ORDER_DEFAULT))
    resolution: list[ResolutionValue] = Field(default_factory=lambda: list(QUALITY_RESOLUTION_VALUES))
    source: list[SourceValue] = Field(default_factory=lambda: list(QUALITY_SOURCE_VALUES))
    resource_form: list[ResourceFormValue] = Field(default_factory=lambda: list(QUALITY_RESOURCE_FORM_VALUES))
    hdr_type: list[HdrTypeValue] = Field(default_factory=lambda: list(QUALITY_HDR_TYPE_VALUES))
    video_codec: list[VideoCodecValue] = Field(default_factory=lambda: list(QUALITY_VIDEO_CODEC_VALUES))
    audio_codec: list[AudioCodecValue] = Field(default_factory=lambda: list(QUALITY_AUDIO_CODEC_VALUES))
    audio_channels: list[AudioChannelsValue] = Field(default_factory=lambda: list(QUALITY_AUDIO_CHANNELS_VALUES))

    @model_validator(mode="after")
    def normalize(self) -> "QualityRankingConfig":
        self.dimension_order = _normalize_order(self.dimension_order, QUALITY_DIMENSION_ORDER_DEFAULT)
        self.resolution = _normalize_order(self.resolution, QUALITY_RESOLUTION_VALUES)
        self.source = _normalize_order(self.source, QUALITY_SOURCE_VALUES)
        self.resource_form = _normalize_order(self.resource_form, QUALITY_RESOURCE_FORM_VALUES)
        self.hdr_type = _normalize_order(self.hdr_type, QUALITY_HDR_TYPE_VALUES)
        self.video_codec = _normalize_order(self.video_codec, QUALITY_VIDEO_CODEC_VALUES)
        self.audio_codec = _normalize_order(self.audio_codec, QUALITY_AUDIO_CODEC_VALUES)
        self.audio_channels = _normalize_order(self.audio_channels, QUALITY_AUDIO_CHANNELS_VALUES)
        return self

    def rank_map_for(self, dimension: str) -> dict[str, int]:
        ordered = self._ordered_values_for_dimension(dimension)
        size = len(ordered)
        return {str(value): size - index for index, value in enumerate(ordered)}

    def _ordered_values_for_dimension(self, dimension: str) -> list:
        if dimension == QUALITY_DIMENSION_RESOLUTION:
            return self.resolution
        if dimension == QUALITY_DIMENSION_SOURCE:
            return self.source
        if dimension == QUALITY_DIMENSION_RESOURCE_FORM:
            return self.resource_form
        if dimension == QUALITY_DIMENSION_HDR_TYPE:
            return self.hdr_type
        if dimension == QUALITY_DIMENSION_VIDEO_CODEC:
            return self.video_codec
        if dimension == QUALITY_DIMENSION_AUDIO_CODEC:
            return self.audio_codec
        if dimension == QUALITY_DIMENSION_AUDIO_CHANNELS:
            return self.audio_channels
        return []
