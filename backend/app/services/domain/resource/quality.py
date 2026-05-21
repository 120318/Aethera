from __future__ import annotations

from app.schemas.domain.quality_ranking import (
    QUALITY_AUDIO_CHANNELS_VALUES,
    QUALITY_AUDIO_CODEC_VALUES,
    QUALITY_HDR_TYPE_VALUES,
    QUALITY_RESOURCE_FORM_VALUES,
    QUALITY_RESOLUTION_VALUES,
    QUALITY_SOURCE_VALUES,
    QUALITY_VIDEO_CODEC_VALUES,
    QualityRankingConfig,
)
from app.schemas.domain.quality_values import AudioChannelsValue, AudioCodecValue, HdrTypeValue, ResourceFormValue, ResolutionValue, SourceValue, VideoCodecValue
from app.schemas.domain.resource_attributes import ResourceAttributes

RESOLUTION_2160P, RESOLUTION_1440P, RESOLUTION_1080P, RESOLUTION_720P, RESOLUTION_576P, RESOLUTION_480P = QUALITY_RESOLUTION_VALUES
SOURCE_REMUX, SOURCE_UHD_BLURAY, SOURCE_BLURAY, SOURCE_HDTV, SOURCE_WEB_DL, SOURCE_WEBRIP, SOURCE_DVD, SOURCE_DVDRIP, SOURCE_HDCAM, SOURCE_R5, SOURCE_TC, SOURCE_TS, SOURCE_CAM = QUALITY_SOURCE_VALUES
RESOURCE_FORM_BLURAY_DISC, RESOURCE_FORM_VIDEO_FILE, RESOURCE_FORM_DVD_DISC = QUALITY_RESOURCE_FORM_VALUES
HDR_DOLBY_VISION, HDR_HDR10_PLUS, HDR_HDR10 = QUALITY_HDR_TYPE_VALUES
VIDEO_CODEC_AV1, VIDEO_CODEC_HEVC, VIDEO_CODEC_AVC = QUALITY_VIDEO_CODEC_VALUES
AUDIO_CODEC_FLAC, AUDIO_CODEC_DOLBY_ATMOS, AUDIO_CODEC_DTS_X, AUDIO_CODEC_TRUEHD, AUDIO_CODEC_DTS_HD_MA, AUDIO_CODEC_DTS_HD, AUDIO_CODEC_DTS, AUDIO_CODEC_DDP, AUDIO_CODEC_AC3, AUDIO_CODEC_AAC = QUALITY_AUDIO_CODEC_VALUES
AUDIO_CHANNELS_71, AUDIO_CHANNELS_51, AUDIO_CHANNELS_20, AUDIO_CHANNELS_10 = QUALITY_AUDIO_CHANNELS_VALUES

RESOLUTION_RANK = {
    RESOLUTION_2160P: 6,
    RESOLUTION_1440P: 5,
    RESOLUTION_1080P: 4,
    RESOLUTION_720P: 3,
    RESOLUTION_576P: 2,
    RESOLUTION_480P: 1,
}

SOURCE_RANK = {
    SOURCE_REMUX: 12,
    SOURCE_UHD_BLURAY: 11,
    SOURCE_BLURAY: 10,
    SOURCE_HDTV: 9,
    SOURCE_WEB_DL: 8,
    SOURCE_WEBRIP: 7,
    SOURCE_DVD: 6,
    SOURCE_DVDRIP: 5,
    SOURCE_HDCAM: 4,
    SOURCE_R5: 3,
    SOURCE_TC: 2,
    SOURCE_TS: 1,
    SOURCE_CAM: 0,
}

RESOURCE_FORM_RANK = {
    RESOURCE_FORM_BLURAY_DISC: 3,
    RESOURCE_FORM_VIDEO_FILE: 2,
    RESOURCE_FORM_DVD_DISC: 1,
}

HDR_TYPE_RANK = {
    HDR_DOLBY_VISION: 4,
    HDR_HDR10_PLUS: 3,
    HDR_HDR10: 2,
}

VIDEO_CODEC_RANK = {
    VIDEO_CODEC_AV1: 3,
    VIDEO_CODEC_HEVC: 2,
    VIDEO_CODEC_AVC: 1,
}

AUDIO_CODEC_RANK = {
    AUDIO_CODEC_FLAC: 10,
    AUDIO_CODEC_DOLBY_ATMOS: 9,
    AUDIO_CODEC_DTS_X: 8,
    AUDIO_CODEC_TRUEHD: 7,
    AUDIO_CODEC_DTS_HD_MA: 6,
    AUDIO_CODEC_DTS_HD: 5,
    AUDIO_CODEC_DTS: 4,
    AUDIO_CODEC_DDP: 3,
    AUDIO_CODEC_AC3: 2,
    AUDIO_CODEC_AAC: 1,
}

AUDIO_CHANNELS_RANK = {
    AUDIO_CHANNELS_71: 3,
    AUDIO_CHANNELS_51: 2,
    AUDIO_CHANNELS_20: 1,
    AUDIO_CHANNELS_10: 0,
}

_RESOLUTION_ALIASES = {
    "4k": RESOLUTION_2160P,
    "2160": RESOLUTION_2160P,
    "uhd": RESOLUTION_2160P,
}

_SOURCE_ALIASES = {
    "uhd bluray": SOURCE_UHD_BLURAY,
    "uhd blu ray": SOURCE_UHD_BLURAY,
    "bluray": SOURCE_BLURAY,
    "blu ray": SOURCE_BLURAY,
    "bdrip": SOURCE_BLURAY,
    "webdl": SOURCE_WEB_DL,
    "web dl": SOURCE_WEB_DL,
    "webrip": SOURCE_WEBRIP,
    "web rip": SOURCE_WEBRIP,
    "dvd": SOURCE_DVD,
    "dvd video": SOURCE_DVD,
    "dvdrip": SOURCE_DVDRIP,
    "dvd rip": SOURCE_DVDRIP,
    "remux": SOURCE_REMUX,
    "cam": SOURCE_CAM,
    "ts": SOURCE_TS,
    "tc": SOURCE_TC,
    "r5": SOURCE_R5,
    "hdcam": SOURCE_HDCAM,
}

_RESOURCE_FORM_ALIASES = {
    "video": RESOURCE_FORM_VIDEO_FILE,
    "video file": RESOURCE_FORM_VIDEO_FILE,
    "file": RESOURCE_FORM_VIDEO_FILE,
    "bluray disc": RESOURCE_FORM_BLURAY_DISC,
    "blu ray disc": RESOURCE_FORM_BLURAY_DISC,
    "blu-ray disc": RESOURCE_FORM_BLURAY_DISC,
    "bdmv": RESOURCE_FORM_BLURAY_DISC,
    "dvd disc": RESOURCE_FORM_DVD_DISC,
    "video_ts": RESOURCE_FORM_DVD_DISC,
}

_VIDEO_CODEC_ALIASES = {
    "h264": VIDEO_CODEC_AVC,
    "x264": VIDEO_CODEC_AVC,
    "avc": VIDEO_CODEC_AVC,
    "h265": VIDEO_CODEC_HEVC,
    "x265": VIDEO_CODEC_HEVC,
    "hevc": VIDEO_CODEC_HEVC,
    "av1": VIDEO_CODEC_AV1,
}

_AUDIO_CODEC_ALIASES = {
    "atmos": AUDIO_CODEC_DOLBY_ATMOS,
    "dolby atmos": AUDIO_CODEC_DOLBY_ATMOS,
    "truehd": AUDIO_CODEC_TRUEHD,
    "dts hd ma": AUDIO_CODEC_DTS_HD_MA,
    "dts-hd ma": AUDIO_CODEC_DTS_HD_MA,
    "dts x": AUDIO_CODEC_DTS_X,
    "dts-x": AUDIO_CODEC_DTS_X,
    "dts hd": AUDIO_CODEC_DTS_HD,
    "dts-hd": AUDIO_CODEC_DTS_HD,
    "dts": AUDIO_CODEC_DTS,
    "ddp": AUDIO_CODEC_DDP,
    "eac3": AUDIO_CODEC_DDP,
    "e-ac3": AUDIO_CODEC_DDP,
    "aac": AUDIO_CODEC_AAC,
    "ac3": AUDIO_CODEC_AC3,
    "flac": AUDIO_CODEC_FLAC,
}

_HDR_TYPE_ALIASES = {
    "dv": HDR_DOLBY_VISION,
    "dolby vision": HDR_DOLBY_VISION,
    "hdr10+": HDR_HDR10_PLUS,
    "hdr10": HDR_HDR10,
    "hdr": HDR_HDR10,
}


def normalize_resolution(value) -> str | None:
    return _normalize_known(value, RESOLUTION_RANK, _RESOLUTION_ALIASES)


def normalize_source(value) -> str | None:
    return _normalize_known(value, SOURCE_RANK, _SOURCE_ALIASES)


def normalize_resource_form(value) -> str | None:
    return _normalize_known(value, RESOURCE_FORM_RANK, _RESOURCE_FORM_ALIASES)


def normalize_hdr_type(value) -> str | None:
    return _normalize_known(value, HDR_TYPE_RANK, _HDR_TYPE_ALIASES)


def normalize_video_codec(value) -> str | None:
    return _normalize_known(value, VIDEO_CODEC_RANK, _VIDEO_CODEC_ALIASES)


def normalize_audio_codec(value) -> str | None:
    return _normalize_known(value, AUDIO_CODEC_RANK, _AUDIO_CODEC_ALIASES)


def normalize_audio_channels(value) -> str | None:
    normalized = _normalize_known(value, AUDIO_CHANNELS_RANK, {})
    if normalized in {AUDIO_CHANNELS_20, AUDIO_CHANNELS_10}:
        return None
    return normalized


def primary_source(values: list[str] | None) -> str | None:
    if not values:
        return None
    ranked = [
        (_rank_or_zero(normalize_source(value), SOURCE_RANK), normalize_source(value))
        for value in values
    ]
    ranked = [item for item in ranked if item[1] is not None]
    if not ranked:
        return values[0]
    return max(ranked, key=lambda item: item[0])[1]


def compare_resource_attributes(
    existing_attrs: ResourceAttributes,
    incoming_attrs: ResourceAttributes,
) -> tuple[str, int] | None:
    for dimension, existing_value, incoming_value, ranking in quality_dimension_comparisons(
        existing_attrs,
        incoming_attrs,
        QualityRankingConfig(),
    ):
        comparison = _compare_ranked(existing_value, incoming_value, ranking)
        if comparison is not None:
            return dimension, comparison
    return None


def quality_sort_key(attrs: ResourceAttributes, ranking: QualityRankingConfig | None = None) -> tuple[int, ...]:
    active_ranking = ranking or QualityRankingConfig()
    values = normalized_quality_values(attrs)
    return tuple(
        _dimension_rank(active_ranking, dimension, values[dimension])
        for dimension in active_ranking.dimension_order
    )


def quality_dimension_comparisons(
    existing_attrs: ResourceAttributes,
    incoming_attrs: ResourceAttributes,
    ranking: QualityRankingConfig | None = None,
) -> list[tuple[str, str | None, str | None, dict[str, int]]]:
    active_ranking = ranking or QualityRankingConfig()
    existing_values = normalized_quality_values(existing_attrs)
    incoming_values = normalized_quality_values(incoming_attrs)
    return [
        (
            dimension,
            existing_values[dimension],
            incoming_values[dimension],
            active_ranking.rank_map_for(dimension),
        )
        for dimension in active_ranking.dimension_order
    ]


def normalized_quality_values(attrs: ResourceAttributes) -> dict[str, str | None]:
    return {
        "resolution": normalize_resolution(attrs.resolution),
        "source": normalize_source(primary_source(attrs.sources)),
        "resource_form": normalize_resource_form(attrs.resource_form),
        "hdr_type": normalize_hdr_type(attrs.hdr_type),
        "video_codec": normalize_video_codec(attrs.video_codec),
        "audio_codec": normalize_audio_codec(attrs.audio_codec),
        "audio_channels": normalize_audio_channels(attrs.audio_channels),
    }


def _dimension_rank(
    ranking: QualityRankingConfig,
    dimension: str,
    value: str | None,
) -> int:
    if value is None:
        return 0
    rank_map = ranking.rank_map_for(dimension)
    if value not in rank_map:
        return 0
    return rank_map[value]


def resource_attributes_match(
    existing_attrs: ResourceAttributes,
    incoming_attrs: ResourceAttributes,
) -> bool:
    normalized_pairs = normalized_resource_attribute_pairs(existing_attrs, incoming_attrs)
    if not any(left is not None or right is not None for left, right in normalized_pairs):
        return False
    return all(left == right for left, right in normalized_pairs)


def has_comparable_resource_attributes(
    existing_attrs: ResourceAttributes,
    incoming_attrs: ResourceAttributes,
) -> bool:
    return any(left is not None or right is not None for left, right in normalized_resource_attribute_pairs(existing_attrs, incoming_attrs))


def has_any_resource_attributes(attrs: ResourceAttributes) -> bool:
    return any(
        value is not None
        for value in (
            normalize_resolution(attrs.resolution),
            normalize_source(primary_source(attrs.sources)),
            normalize_resource_form(attrs.resource_form),
            normalize_hdr_type(attrs.hdr_type),
            normalize_video_codec(attrs.video_codec),
            normalize_audio_codec(attrs.audio_codec),
            normalize_audio_channels(attrs.audio_channels),
        )
    )


def normalized_resource_attribute_pairs(
    existing_attrs: ResourceAttributes,
    incoming_attrs: ResourceAttributes,
) -> list[tuple[str | None, str | None]]:
    return [
        (normalize_resolution(existing_attrs.resolution), normalize_resolution(incoming_attrs.resolution)),
        (normalize_source(primary_source(existing_attrs.sources)), normalize_source(primary_source(incoming_attrs.sources))),
        (normalize_resource_form(existing_attrs.resource_form), normalize_resource_form(incoming_attrs.resource_form)),
        (normalize_hdr_type(existing_attrs.hdr_type), normalize_hdr_type(incoming_attrs.hdr_type)),
        (normalize_video_codec(existing_attrs.video_codec), normalize_video_codec(incoming_attrs.video_codec)),
        (normalize_audio_codec(existing_attrs.audio_codec), normalize_audio_codec(incoming_attrs.audio_codec)),
        (normalize_audio_channels(existing_attrs.audio_channels), normalize_audio_channels(incoming_attrs.audio_channels)),
    ]


def _compare_ranked(
    existing_value: str | None,
    incoming_value: str | None,
    ranking: dict[str, int],
) -> int | None:
    if existing_value is None or incoming_value is None:
        return None
    existing_rank = _rank_or_none(existing_value, ranking)
    incoming_rank = _rank_or_none(incoming_value, ranking)
    if existing_rank is None or incoming_rank is None or existing_rank == incoming_rank:
        return None
    return 1 if incoming_rank > existing_rank else -1


def _normalize_known(
    value: str | None,
    ranking: dict[str, int],
    aliases: dict[str, str],
) -> str | None:
    normalized = _normalize_token(value)
    if not normalized:
        return None
    if normalized in aliases:
        return aliases[normalized]
    for canonical in ranking:
        if _normalize_token(canonical) == normalized:
            return canonical
    return None


def _normalize_token(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower().replace("_", " ").replace(".", " ")
    normalized = " ".join(normalized.split())
    return normalized or None


def _rank_or_none(value: str | None, ranking: dict[str, int]) -> int | None:
    if value is None or value not in ranking:
        return None
    return ranking[value]


def _rank_or_zero(value: str | None, ranking: dict[str, int]) -> int:
    rank = _rank_or_none(value, ranking)
    return rank if rank is not None else 0
