from __future__ import annotations

from app.schemas.config import Tag


DEFAULT_TAG_SEED_KEY = "default_tags_seeded"


DEFAULT_TAGS = [
    Tag(
        id="builtin-tag-zh-subtitle",
        name="中字",
        regex=r"中字|中文字幕|中文(?:特效)?字幕|简中|繁中|简繁(?:字幕)?|官方中文字幕",
    ),
    Tag(
        id="builtin-tag-en-subtitle",
        name="英字",
        regex=r"英字|英文字幕|英语字幕",
    ),
    Tag(
        id="builtin-tag-bilingual",
        name="双语",
        regex=r"双语(?:字幕|字母)?|中英(?:字幕|双字|双语)?|简英双语|中英特效字幕|国英双语|\bBILINGUAL\b|\bCHI[ ._-]?ENG\b",
    ),
    Tag(
        id="builtin-tag-styled-subtitle",
        name="特效",
        regex=r"特效(?:字幕|中字|双语|字母)?|注释特效字幕",
    ),
    Tag(
        id="builtin-tag-mandarin",
        name="国语",
        regex=r"国语|国配|国英|国语配音|央视国语|中影国语|陆配",
    ),
    Tag(
        id="builtin-tag-cantonese",
        name="粤语",
        regex=r"粤语|粤配|港配",
    ),
    Tag(
        id="builtin-tag-taiwan-dub",
        name="台配",
        regex=r"台配|台湾国语",
    ),
    Tag(
        id="builtin-tag-imax",
        name="IMAX",
        regex=r"\bIMAX\b|IMAX版",
    ),
    Tag(
        id="builtin-tag-diy",
        name="DIY",
        regex=r"\bDIY\b|DIY中字原盘|DIY字幕|DIY次世代",
    ),
    Tag(
        id="builtin-tag-60fps",
        name="60帧",
        regex=r"\b60\s*(?:FPS|帧)\b|帧率[:：]?\s*60",
    ),
    Tag(
        id="builtin-tag-hfr",
        name="高帧率",
        regex=r"\bHFR\b|高帧率|超高帧率",
    ),
    Tag(
        id="builtin-tag-high-bitrate",
        name="高码",
        regex=r"高码(?:率)?|高比特率|码率[:：]?\s*(?:[3-9]\d|[1-9]\d{2,})(?:\.\d+)?\s*(?:Mb/s|Mbps|MB/s)|Bitrate\s*[:：]?\s*(?:[3-9]\d|[1-9]\d{2,})(?:\.\d+)?\s*(?:Mb/s|Mbps|MB/s)",
    ),
    Tag(
        id="builtin-tag-open-matte",
        name="Open Matte",
        regex=r"\bOpen[ ._-]?Matte\b|开放遮幅",
    ),
    Tag(
        id="builtin-tag-ai-enhanced",
        name="AI增强",
        regex=r"\bAI[ ._-]?(?:Enhanced|Upscaled)\b|Topaz\s+Video\s+AI|\bRIFE\b|AI(?:增强|修复|补帧|插帧)",
    ),
    Tag(
        id="builtin-tag-3d",
        name="3D",
        regex=r"\b3D\b|\b(?:Half|Full)[ ._-]?(?:SBS|OU)\b",
    ),
]
