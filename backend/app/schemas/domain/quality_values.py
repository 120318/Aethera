from __future__ import annotations

from enum import StrEnum


class ResolutionValue(StrEnum):
    UHD_2160P = "2160p"
    QHD_1440P = "1440p"
    FHD_1080P = "1080p"
    HD_720P = "720p"
    SD_576P = "576p"
    SD_480P = "480p"


class SourceValue(StrEnum):
    REMUX = "REMUX"
    UHD_BLURAY = "UHD BluRay"
    BLURAY = "BluRay"
    HDTV = "HDTV"
    WEB_DL = "WEB-DL"
    WEBRIP = "WEBRip"
    DVD = "DVD"
    DVDRIP = "DVDRip"
    HDCAM = "HDCAM"
    R5 = "R5"
    TC = "TC"
    TS = "TS"
    CAM = "CAM"


class ResourceFormValue(StrEnum):
    VIDEO_FILE = "Video File"
    BLURAY_DISC = "BluRay Disc"
    DVD_DISC = "DVD Disc"


class ResourceKindValue(StrEnum):
    VIDEO_FILE = "video_file"
    ORIGINAL_DISC = "original_disc"


class HdrTypeValue(StrEnum):
    DOLBY_VISION = "Dolby Vision"
    HDR10_PLUS = "HDR10+"
    HDR10 = "HDR10"
    HDR = "HDR"


class VideoCodecValue(StrEnum):
    AV1 = "AV1"
    HEVC = "HEVC"
    AVC = "AVC"


class AudioCodecValue(StrEnum):
    FLAC = "FLAC"
    DOLBY_ATMOS = "Dolby Atmos"
    DTS_X = "DTS-X"
    TRUEHD = "TrueHD"
    DTS_HD_MA = "DTS-HD MA"
    DTS_HD = "DTS-HD"
    DTS = "DTS"
    DDP = "DDP"
    AC3 = "AC3"
    AAC = "AAC"


class AudioChannelsValue(StrEnum):
    CHANNELS_71 = "7.1"
    CHANNELS_51 = "5.1"
    CHANNELS_20 = "2.0"
    CHANNELS_10 = "1.0"


class ColorDepthValue(StrEnum):
    BIT_12 = "12bit"
    BIT_10 = "10bit"
    BIT_8 = "8bit"


QUALITY_RESOLUTION_VALUES = list(ResolutionValue)
QUALITY_SOURCE_VALUES = list(SourceValue)
QUALITY_RESOURCE_KIND_VALUES = list(ResourceKindValue)
QUALITY_RESOURCE_FORM_VALUES = [
    ResourceFormValue.BLURAY_DISC,
    ResourceFormValue.VIDEO_FILE,
    ResourceFormValue.DVD_DISC,
]
QUALITY_HDR_TYPE_VALUES = [
    HdrTypeValue.DOLBY_VISION,
    HdrTypeValue.HDR10_PLUS,
    HdrTypeValue.HDR10,
]
QUALITY_VIDEO_CODEC_VALUES = list(VideoCodecValue)
QUALITY_AUDIO_CODEC_VALUES = list(AudioCodecValue)
QUALITY_AUDIO_CHANNELS_VALUES = list(AudioChannelsValue)
QUALITY_COLOR_DEPTH_VALUES = list(ColorDepthValue)
