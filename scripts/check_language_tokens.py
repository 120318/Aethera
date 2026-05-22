#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]

SKIP_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    "dist",
    "tmp",
    ".ruff_cache",
    ".pytest_cache",
    ".mypy_cache",
}

SKIP_PATHS = (
    "frontend/src/i18n/locales/*",
    "backend/app/services/i18n/locales/*",
    "backend/tests/*",
    "frontend/tests/*",
)

TEXT_EXTENSIONS = {
    ".py",
    ".sh",
    ".js",
    ".vue",
    ".md",
    ".json",
    ".toml",
    ".yaml",
    ".yml",
}

HAN_TOKEN_RE = re.compile(r"[A-Za-z]*[\u4e00-\u9fff]+[A-Za-z]*")
UNICODE_ESCAPE_RE = re.compile(r"\\u[0-9A-Fa-f]{4}")


TOKEN_ALLOWLIST: dict[str, tuple[str, tuple[str, ...]]] = {
    # Platform/provider identity tokens used for matching external data.
    "豆瓣": ("domain_match_token", ("backend/app/clients/douban.py", "frontend/src/i18n/locales/*")),
    "腾讯": ("domain_match_token", ("backend/app/services/integration/danmu/providers/qq.py", "backend/app/services/domain/resource/parser_rules.py")),
    "腾讯视频": (
        "domain_match_token",
        (
            "backend/alembic/versions/*",
            "backend/app/services/domain/media/schedule/platforms.py",
            "backend/app/services/domain/resource/parser_rules.py",
            "backend/tests/*",
            "frontend/src/utils/mediaPlatforms.js",
        ),
    ),
    "腾讯视频平台": (
        "domain_match_token",
        (
            "backend/app/services/domain/media/schedule/platforms.py",
            "backend/tests/*",
            "frontend/src/utils/mediaPlatforms.js",
        ),
    ),
    "企鹅影视": ("domain_match_token", ("backend/app/services/domain/resource/parser_rules.py",)),
    "爱奇艺": (
        "domain_match_token",
        (
            "backend/alembic/versions/*",
            "backend/app/services/integration/danmu/providers/iqiyi.py",
            "backend/app/services/domain/media/schedule/platforms.py",
            "backend/app/services/domain/resource/parser_rules.py",
            "backend/tests/*",
            "frontend/src/utils/mediaPlatforms.js",
        ),
    ),
    "爱奇艺国际版": ("domain_match_token", ("backend/app/services/domain/media/schedule/platforms.py",)),
    "奇艺": ("domain_match_token", ("backend/app/services/domain/resource/parser_rules.py",)),
    "优酷": (
        "domain_match_token",
        (
            "backend/alembic/versions/*",
            "backend/app/services/integration/danmu/providers/youku.py",
            "backend/app/services/domain/media/schedule/platforms.py",
            "backend/app/services/domain/resource/parser_rules.py",
            "backend/tests/*",
            "frontend/src/utils/mediaPlatforms.js",
        ),
    ),
    "优酷视频": (
        "domain_match_token",
        (
            "backend/app/services/domain/media/schedule/platforms.py",
            "backend/app/services/domain/resource/parser_rules.py",
            "frontend/src/utils/mediaPlatforms.js",
        ),
    ),
    "哔哩": ("domain_match_token", ("backend/app/services/domain/resource/parser_rules.py",)),
    "哔哩哔哩": (
        "domain_match_token",
        (
            "backend/alembic/versions/*",
            "backend/app/services/integration/danmu/providers/bilibili.py",
            "backend/app/services/domain/media/schedule/platforms.py",
            "backend/app/services/domain/resource/parser_rules.py",
            "backend/tests/*",
            "frontend/src/utils/mediaPlatforms.js",
        ),
    ),
    "B站": ("domain_match_token", ("backend/app/services/integration/danmu/providers/bilibili.py", "backend/app/services/domain/resource/parser_rules.py", "backend/tests/*")),
    "b站": ("domain_match_token", ("backend/app/services/integration/danmu/providers/bilibili.py",)),
    "芒果": ("domain_match_token", ("backend/app/services/domain/resource/parser_rules.py",)),
    "芒果tv": (
        "domain_match_token",
        (
            "backend/alembic/versions/*",
            "backend/app/services/domain/media/schedule/platforms.py",
            "frontend/src/utils/mediaPlatforms.js",
        ),
    ),
    "芒果TV": ("domain_match_token", ("backend/app/services/domain/media/schedule/platforms.py", "backend/app/services/domain/resource/parser_rules.py", "backend/tests/*")),
    "无限超越班": ("domain_match_token", ("backend/tests/*",)),
    "湖南卫视": ("domain_match_token", ("backend/app/services/domain/resource/parser_rules.py",)),
    "搜狐": ("domain_match_token", ("backend/app/services/domain/resource/parser_rules.py",)),
    "搜狐视频": ("domain_match_token", ("backend/app/services/domain/resource/parser_rules.py",)),
    "乐视": ("domain_match_token", ("backend/app/services/domain/resource/parser_rules.py",)),
    "乐视视频": ("domain_match_token", ("backend/app/services/domain/resource/parser_rules.py",)),
    "央视": ("domain_match_token", ("backend/app/services/domain/resource/parser_rules.py",)),
    "中央电视台": ("domain_match_token", ("backend/app/services/domain/resource/parser_rules.py",)),
    "咪咕": ("domain_match_token", ("backend/app/services/domain/resource/parser_rules.py",)),
    "百视通": ("domain_match_token", ("backend/app/services/domain/resource/parser_rules.py",)),
    "东方明珠": ("domain_match_token", ("backend/app/services/domain/resource/parser_rules.py",)),

    # Parser tokens that model resource titles, language tags, subtitles, and episode/disc labels.
    "第": ("parser_token", ("backend/app/services/integration/danmu/providers/qq.py", "backend/app/services/domain/media/provider/normalization.py", "backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*", "backend/app/services/domain/resource/parser_rules.py", "backend/app/utils/title_parser.py", "backend/tests/*", "frontend/src/composables/useMediaDetailPage.js")),
    "季": ("parser_token", ("backend/app/services/domain/media/provider/normalization.py", "backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*", "backend/app/services/domain/resource/parser_rules.py", "backend/app/utils/title_parser.py", "backend/tests/*", "frontend/src/composables/useMediaDetailPage.js")),
    "集": ("parser_token", ("backend/app/services/integration/danmu/providers/qq.py", "backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*", "backend/app/services/domain/resource/parser_rules.py", "backend/tests/*")),
    "话": ("parser_token", ("backend/app/services/integration/danmu/providers/qq.py", "backend/tests/*")),
    "碟": ("parser_token", ("backend/app/services/domain/resource/parser_rules.py", "backend/tests/*")),
    "盘": ("parser_token", ("backend/app/services/domain/resource/parser_rules.py",)),
    "一二三四五六七八九十": ("parser_token", ("backend/app/services/domain/media/provider/normalization.py", "backend/app/utils/title_parser.py")),
    "一": ("parser_token", ("backend/app/utils/title_parser.py", "frontend/src/composables/useMediaDetailPage.js")),
    "二": ("parser_token", ("backend/app/utils/title_parser.py", "frontend/src/composables/useMediaDetailPage.js")),
    "三": ("parser_token", ("backend/app/utils/title_parser.py", "backend/tests/*", "frontend/src/composables/useMediaDetailPage.js")),
    "四": ("parser_token", ("backend/app/utils/title_parser.py", "frontend/src/composables/useMediaDetailPage.js")),
    "五": ("parser_token", ("backend/app/utils/title_parser.py", "frontend/src/composables/useMediaDetailPage.js")),
    "六": ("parser_token", ("backend/app/utils/title_parser.py", "frontend/src/composables/useMediaDetailPage.js")),
    "七": ("parser_token", ("backend/app/utils/title_parser.py", "frontend/src/composables/useMediaDetailPage.js")),
    "八": ("parser_token", ("backend/app/utils/title_parser.py", "frontend/src/composables/useMediaDetailPage.js")),
    "九": ("parser_token", ("backend/app/utils/title_parser.py", "frontend/src/composables/useMediaDetailPage.js")),
    "十": ("parser_token", ("backend/app/utils/title_parser.py", "frontend/src/composables/useMediaDetailPage.js")),
    "预告": ("parser_token", ("backend/app/services/integration/danmu/providers/qq.py",)),
    "花絮": ("parser_token", ("backend/app/services/integration/danmu/providers/qq.py",)),
    "片花": ("parser_token", ("backend/app/services/integration/danmu/providers/qq.py",)),
    "彩蛋": ("parser_token", ("backend/app/services/integration/danmu/providers/qq.py",)),
    "电影": ("parser_token", ("backend/app/clients/jackett.py",)),
    "电视剧": ("parser_token", ("backend/app/clients/jackett.py",)),
    "剧集": ("parser_token", ("backend/app/clients/jackett.py", "backend/tests/*")),
    "动画": ("parser_token", ("backend/app/clients/jackett.py",)),
    "动漫": ("parser_token", ("backend/app/clients/jackett.py",)),
    "纪录": ("parser_token", ("backend/app/clients/jackett.py",)),
    "音乐": ("parser_token", ("backend/app/clients/jackett.py",)),
    "软件": ("parser_token", ("backend/app/clients/jackett.py",)),
    "游戏": ("parser_token", ("backend/app/clients/jackett.py",)),
    "第一季": ("parser_token", ("backend/tests/*",)),
    "第四季": ("parser_token", ("backend/tests/*",)),
    "中文": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*", "backend/tests/*", "frontend/src/i18n/locales/*")),
    "中字": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*", "backend/tests/*")),
    "中文字幕": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "官方中文字幕": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "简中": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "繁中": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "简繁": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "国语": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*", "backend/tests/*")),
    "国配": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "国英": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "国语配音": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*", "backend/tests/*")),
    "央视国语": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "中影国语": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "陆配": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "普通话": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "繁体": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "简体": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "英语": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*", "backend/tests/*")),
    "英文": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*", "backend/tests/*")),
    "英字": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*", "backend/tests/*")),
    "英文字幕": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "英语字幕": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "日语": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "日文": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "韩语": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "韩文": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "内嵌": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*", "backend/tests/*")),
    "内封": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*", "backend/tests/*")),
    "外挂": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*", "backend/tests/*")),
    "外挂字幕": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "封装字幕": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "双语": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*", "backend/tests/*")),
    "双语字幕": ("parser_token", ("backend/tests/*",)),
    "双字": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "简英双语": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "中英": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*", "backend/tests/*")),
    "中英特效字幕": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "国英双语": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "特效": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*", "backend/tests/*")),
    "特效字幕": ("parser_token", ("backend/tests/*",)),
    "特效双语字幕": ("parser_token", ("backend/tests/*",)),
    "内封特效字幕": ("parser_token", ("backend/tests/*",)),
    "中字外挂字幕": ("parser_token", ("backend/tests/*",)),
    "注释特效字幕": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "字幕": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "字母": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "粤语": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "粤配": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "港配": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "台配": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "台湾国语": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "多音轨": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*", "backend/tests/*")),
    "多语": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "多国语言": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "国英双音": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*", "backend/tests/*")),
    "国粤英": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "陆台粤英": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "IMAX版": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*", "backend/tests/*")),
    "DIY中字原盘": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "DIY字幕": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "DIY次世代": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "硬字幕": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "多字幕": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*", "backend/tests/*")),
    "多国字幕": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "多语言字幕": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "多语字幕": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "帧": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*", "backend/tests/*")),
    "帧率": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "高帧率": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "超高帧率": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "高码": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*", "backend/tests/*")),
    "率": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "高比特率": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "码率": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "开放遮幅": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "AI增强": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*", "backend/tests/*")),
    "增强": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "修复": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "补帧": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "插帧": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "杜比视界": ("parser_token", ("backend/app/services/domain/resource/parser_technical.py", "backend/tests/*", "frontend/src/i18n/locales/*")),
    "杜比全景声": ("parser_token", ("backend/app/services/domain/resource/parser_technical.py", "backend/tests/*")),
    "全景声": ("parser_token", ("backend/app/services/domain/resource/parser_technical.py",)),
    "临境音": ("parser_token", ("backend/app/services/domain/resource/parser_technical.py",)),
    "更新至": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "更新到": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "更至": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "全": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*", "backend/tests/*")),
    "全集": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/tests/*")),
    "全季": ("parser_token", ("backend/app/services/domain/resource/parser.py",)),
    "完整": ("parser_token", ("backend/app/services/domain/resource/parser.py",)),
    "完整版": ("parser_token", ("backend/app/services/domain/resource/parser.py",)),
    "至到": ("parser_token", ("backend/app/services/domain/resource/parser.py", "backend/app/services/domain/resource/tags.py", "backend/app/services/config/default_tags.py", "backend/alembic/versions/*",)),
    "无": ("parser_token", ("backend/app/services/domain/resource/parser.py",)),
    "音轨": ("parser_token", ("backend/app/services/domain/resource/parser.py",)),
    "配音": ("parser_token", ("backend/app/services/domain/resource/parser.py",)),
    "不含": ("parser_token", ("backend/app/services/domain/resource/parser.py",)),
    "不包括": ("parser_token", ("backend/app/services/domain/resource/parser.py",)),
    "未含": ("parser_token", ("backend/app/services/domain/resource/parser.py",)),
    "未包括": ("parser_token", ("backend/app/services/domain/resource/parser.py",)),
    "缺少": ("parser_token", ("backend/app/services/domain/resource/parser.py",)),
    "缺失": ("parser_token", ("backend/app/services/domain/resource/parser.py",)),
    "遗漏": ("parser_token", ("backend/app/services/domain/resource/parser.py",)),
    "漏": ("parser_token", ("backend/app/services/domain/resource/parser.py",)),
    "替代": ("parser_token", ("backend/app/services/domain/resource/parser.py",)),
    "代替": ("parser_token", ("backend/app/services/domain/resource/parser.py",)),
    "补档": ("parser_token", ("backend/app/services/domain/resource/parser.py",)),
    "类型": ("parser_token", ("backend/tests/*",)),
    "剧情": ("parser_token", ("backend/tests/*",)),
    "爱情": ("parser_token", ("backend/tests/*",)),
    "主演": ("parser_token", ("backend/tests/*",)),
    "视频参数": ("parser_token", ("backend/tests/*",)),
    "音频参数": ("parser_token", ("backend/tests/*",)),
    "格式": ("parser_token", ("backend/tests/*",)),
    "排除国语": ("parser_token", ("backend/tests/*",)),
    "低码": ("parser_token", ("backend/tests/*",)),
    "低码率版本": ("parser_token", ("backend/tests/*",)),

    # Test fixtures with realistic CJK media titles.
    "老友记": ("test_fixture", ("backend/tests/test_media_source_canonical.py",)),
    "庆余年": ("test_fixture", ("backend/tests/*",)),
    "流浪地球": ("test_fixture", ("backend/tests/*",)),
    "大江大河": ("test_fixture", ("backend/tests/test_resource_parser.py",)),
    "葬送的芙莉莲": ("test_fixture", ("backend/tests/test_resource_parser.py",)),
    "三体": ("test_fixture", ("backend/tests/test_resource_parser.py",)),
    "扫毒风暴": ("test_fixture", ("backend/tests/test_resource_parser.py",)),
    "爱情没有神话": ("test_fixture", ("backend/tests/*",)),
    "唐嫣": ("test_fixture", ("backend/tests/*",)),
    "赵又廷": ("test_fixture", ("backend/tests/*",)),
    "杨采钰": ("test_fixture", ("backend/tests/*",)),
    "冯绍峰": ("test_fixture", ("backend/tests/*",)),
    "晏紫东": ("test_fixture", ("backend/tests/*",)),
    "独身女人": ("test_fixture", ("backend/tests/*",)),
    "云视听极光": ("test_fixture", ("backend/tests/*",)),
    "真实描述": ("test_fixture", ("backend/tests/*",)),
    "任务描述": ("test_fixture", ("backend/tests/*",)),
    "第六季": ("test_fixture", ("backend/tests/test_media_source_canonical.py",)),
    "低智商犯罪": ("test_fixture", ("backend/tests/*",)),
    "我是刑警": ("test_fixture", ("backend/tests/*",)),
    "中国刑警": ("test_fixture", ("backend/tests/*",)),
    "于和伟": ("test_fixture", ("backend/tests/*",)),
    "富大龙": ("test_fixture", ("backend/tests/*",)),
    "丁勇岱": ("test_fixture", ("backend/tests/*",)),
    "其中第": ("test_fixture", ("backend/tests/*",)),
    "集无DV": ("test_fixture", ("backend/tests/*",)),
    "普码": ("test_fixture", ("backend/tests/*",)),
    "K替代": ("test_fixture", ("backend/tests/*",)),
    "无删减版": ("test_fixture", ("backend/tests/*",)),
    "无水印": ("test_fixture", ("backend/tests/*",)),
    "修复版": ("test_fixture", ("backend/tests/*",)),
    "中国大陆": ("test_fixture", ("backend/tests/*",)),
    "犯罪": ("test_fixture", ("backend/tests/*",)),
    "长沙夜生活": ("test_fixture", ("backend/tests/*",)),
    "咱们结婚吧": ("test_fixture", ("backend/tests/*",)),
    "这是私有": ("test_fixture", ("backend/tests/*",)),

    # Runtime labels that are persisted as command targets for operator context.
    "目录完整性扫描": ("runtime_label", ("backend/app/services/application/commands/handlers/directory_integrity.py", "backend/tests/*")),
    "目录完整性修复完成": ("runtime_label", ("backend/app/services/application/commands/handlers/directory_integrity.py",)),
    "目录完整性修复失败": ("runtime_label", ("backend/app/services/application/commands/handlers/directory_integrity.py",)),
    "目录完整性扫描完成": ("runtime_label", ("backend/app/services/application/commands/handlers/directory_integrity.py",)),
    "目录完整性扫描失败": ("runtime_label", ("backend/app/services/application/commands/handlers/directory_integrity.py",)),
    "正在扫描目录完整性": ("runtime_label", ("backend/app/services/application/commands/handlers/directory_integrity.py",)),
    "正在修复目录完整性": ("runtime_label", ("backend/app/services/application/commands/handlers/directory_integrity.py",)),
    "目录差异": ("runtime_label", ("backend/app/services/application/commands/handlers/directory_integrity.py",)),
    "未管理的库文件": ("runtime_label", ("backend/app/services/application/commands/handlers/directory_integrity.py",)),
    "库文件缺失": ("runtime_label", ("backend/app/services/application/commands/handlers/directory_integrity.py",)),
    "未管理的下载项": ("runtime_label", ("backend/app/services/application/commands/handlers/directory_integrity.py", "backend/tests/*")),
    "下载文件缺失": ("runtime_label", ("backend/app/services/application/commands/handlers/directory_integrity.py",)),
    "下载器种子缺失": ("runtime_label", ("backend/app/services/application/commands/handlers/directory_integrity.py",)),
    "下载器种子异常": ("runtime_label", ("backend/app/services/application/commands/handlers/directory_integrity.py",)),

    # External tracker/directory text used for normalization and filtering.
    "私有": ("external_protocol_token", ("backend/app/services/integration/torrent/directory_integrity.py", "frontend/src/components/media-management/directoryIntegritySupport.js")),
    "种子": ("external_protocol_token", ("backend/app/services/integration/torrent/directory_integrity.py", "frontend/src/components/media-management/directoryIntegritySupport.js")),
    "库": ("directory_display_token", ("frontend/src/components/media-management/directoryIntegritySupport.js",)),
}


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def path_allowed(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def should_skip(path: Path, text_extensions: set[str]) -> bool:
    relative = rel(path)
    relative_parts = path.relative_to(ROOT).parts
    if relative == "scripts/check_language_tokens.py":
        return True
    if relative_parts and relative_parts[0] == "config":
        return True
    if any(part in SKIP_DIRS for part in relative_parts):
        return True
    if any(fnmatch.fnmatch(relative, pattern) for pattern in SKIP_PATHS):
        return True
    return path.suffix not in text_extensions


def line_number(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def check_file(path: Path) -> list[str]:
    relative = rel(path)
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    findings: list[str] = []

    for match in UNICODE_ESCAPE_RE.finditer(text):
        findings.append(
            f"{relative}:{line_number(text, match.start())}: Unicode escape {match.group(0)!r} is not allowed outside locale files"
        )

    for match in HAN_TOKEN_RE.finditer(text):
        token = match.group(0)
        allowed = TOKEN_ALLOWLIST.get(token)
        if not allowed:
            findings.append(
                f"{relative}:{line_number(text, match.start())}: Chinese token {token!r} is not registered"
            )
            continue
        reason, patterns = allowed
        if not path_allowed(relative, patterns):
            findings.append(
                f"{relative}:{line_number(text, match.start())}: Chinese token {token!r} is registered as {reason}, but not allowed in this file"
            )
    return findings


def normalize_extensions(raw_extensions: str | None) -> set[str]:
    if not raw_extensions:
        return set(TEXT_EXTENSIONS)
    extensions = set()
    for item in raw_extensions.split(","):
        extension = item.strip()
        if not extension:
            continue
        if not extension.startswith("."):
            extension = f".{extension}"
        extensions.add(extension)
    return extensions


def iter_files(text_extensions: set[str]) -> list[Path]:
    result: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if should_skip(path, text_extensions):
            continue
        result.append(path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Check repository language token boundaries.")
    parser.add_argument(
        "--extensions",
        help="Comma-separated file extensions to scan. Defaults to all text extensions.",
    )
    args = parser.parse_args()
    text_extensions = normalize_extensions(args.extensions)

    findings: list[str] = []
    for path in iter_files(text_extensions):
        findings.extend(check_file(path))
    if findings:
        print("Repository language token check failed:", file=sys.stderr)
        for finding in findings:
            print(finding, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
