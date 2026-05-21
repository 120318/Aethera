import re

from app.services.domain.resource.quality import (
    AUDIO_CHANNELS_20,
    AUDIO_CHANNELS_51,
    AUDIO_CHANNELS_71,
    AUDIO_CODEC_AAC,
    AUDIO_CODEC_AC3,
    AUDIO_CODEC_DDP,
    AUDIO_CODEC_DOLBY_ATMOS,
    AUDIO_CODEC_DTS,
    AUDIO_CODEC_DTS_HD,
    AUDIO_CODEC_DTS_HD_MA,
    AUDIO_CODEC_DTS_X,
    AUDIO_CODEC_FLAC,
    AUDIO_CODEC_TRUEHD,
    HDR_DOLBY_VISION,
    HDR_HDR10,
    HDR_HDR10_PLUS,
    RESOLUTION_2160P,
    RESOLUTION_1080P,
    RESOLUTION_720P,
    RESOLUTION_480P,
    VIDEO_CODEC_AV1,
    VIDEO_CODEC_AVC,
    VIDEO_CODEC_HEVC,
)


def extract_color_depth(title: str) -> str | None:
    if re.search(r'\b10[- ]?bit\b', title, re.IGNORECASE):
        return "10bit"
    if re.search(r'\b8[- ]?bit\b', title, re.IGNORECASE):
        return "8bit"
    if re.search(r'\b12[- ]?bit\b', title, re.IGNORECASE):
        return "12bit"
    return None


def extract_resolution(title: str) -> str | None:
    resolution_patterns = [
        (RESOLUTION_2160P, r'\b(4K|2160P|UHD)\b'),
        (RESOLUTION_1080P, r'\b1080P?\b'),
        (RESOLUTION_720P, r'\b720P?\b'),
        (RESOLUTION_480P, r'\b480P?\b'),
    ]
    for canonical, pattern in resolution_patterns:
        if re.search(pattern, title, re.IGNORECASE):
            return canonical
    return None


def extract_video_codec(title: str) -> str | None:
    codec_patterns = {
        VIDEO_CODEC_HEVC: r'\b(HEVC|H\.?265|X\.?265)\b',
        VIDEO_CODEC_AVC: r'\b(AVC|H\.?264|X\.?264)\b',
        VIDEO_CODEC_AV1: r'\bAV1\b',
    }
    for codec, pattern in codec_patterns.items():
        if re.search(pattern, title, re.IGNORECASE):
            return codec
    return None


def extract_audio_codec(title: str) -> str | None:
    ordered_patterns = [
        (AUDIO_CODEC_DOLBY_ATMOS, r'\b(Dolby\s*Atmos|Atmos)\b|杜比全景声|全景声|E-?AC-?3\s+JOC|Enhanced\s+AC-?3\s+with\s+Joint\s+Object\s+Coding'),
        (AUDIO_CODEC_TRUEHD, r'\b(TRUEHD|TRUE[-_. ]?HD)\b'),
        (AUDIO_CODEC_DTS_HD_MA, r'\bDTS[-_. ]?HD[-_. ]*MA\b'),
        (AUDIO_CODEC_DTS_X, r'\bDTS[-_. ]?X\b|DTS：X|临境音'),
        (AUDIO_CODEC_DTS_HD, r'\bDTS[-_. ]?HD\b'),
        (AUDIO_CODEC_DTS, r'\bDTS(?=\b|\d)'),
        (AUDIO_CODEC_DDP, r'\b(DDP|E-?AC3|EAC3)(?=\b|\d)'),
        (AUDIO_CODEC_AAC, r'\bAAC\b'),
        (AUDIO_CODEC_AC3, r'\bAC3\b'),
        (AUDIO_CODEC_FLAC, r'\bFLAC\b'),
    ]
    for codec, pattern in ordered_patterns:
        if re.search(pattern, title, re.IGNORECASE):
            return codec
    return None


def extract_hdr_type(title: str) -> str | None:
    hdr_patterns = {
        HDR_DOLBY_VISION: r'\b(DV|DOVI|DOLBY.?VISION)\b|杜比视界',
        HDR_HDR10_PLUS: r'\bHDR10\+(?=\W|$)',
        HDR_HDR10: r'\bHDR10(?!\+)\b|\bHDR\b',
    }
    for hdr_type, pattern in hdr_patterns.items():
        if re.search(pattern, title, re.IGNORECASE):
            return hdr_type
    return None


def extract_audio_channels(title: str) -> str | None:
    channel_patterns = {
        AUDIO_CHANNELS_71: r'(?<!\d)7\.1(?!\d)',
        AUDIO_CHANNELS_51: r'(?<!\d)5\.1(?!\d)',
        AUDIO_CHANNELS_20: r'(?<!\d)2\.0(?!\d)',
    }
    for channels, pattern in channel_patterns.items():
        if re.search(pattern, title, re.IGNORECASE):
            return channels
    return None
