"""
text

text，text：
- text
- text (HDR, 4K, text)
- text (BluRay, WEB-DLtext)
- text (text)
- text
- text
- text
"""

import logging
import re
from collections.abc import Mapping

from app.schemas.domain.resource_attributes import ResourceAttributes
from app.services.domain.resource.parser_rules import (
    BLURAY_DISC_CODEC_PATTERN,
    BLURAY_DISC_PATTERN,
    BLURAY_LOSSLESS_AUDIO_PATTERN,
    DISC_PATTERNS,
    DVD_DISC_PATTERN,
    EPISODE_PATTERNS,
    GROUP_PATTERNS,
    ISO_IMAGE_PATTERN,
    NON_DISC_RELEASE_PATTERN,
    PLATFORM_PATTERNS,
    SEASON_PATTERNS,
    SOURCE_PATTERNS,
    UHD_BLURAY_DISC_PATTERN,
    VERSION_PATTERNS,
)
from app.services.domain.resource.parser_technical import (
    extract_audio_channels,
    extract_audio_codec,
    extract_color_depth,
    extract_hdr_type,
    extract_resolution,
    extract_video_codec,
)
from app.services.domain.resource.quality import (
    AUDIO_CODEC_RANK,
    RESOURCE_FORM_BLURAY_DISC,
    RESOURCE_FORM_DVD_DISC,
    RESOURCE_FORM_VIDEO_FILE,
    HDR_TYPE_RANK,
    SOURCE_BLURAY,
    SOURCE_DVD,
    SOURCE_UHD_BLURAY,
    VIDEO_CODEC_RANK,
)

logger = logging.getLogger("app.resource_parser")


class ResourceParser:
    """Internal helper."""

    def parse(self, title: str, desc: str = "") -> ResourceAttributes:
        """
        text，text

        Args:
            title: text
            desc: text（text）

        Returns:
            ResourceAttributes: text
        """
        desc = str(desc or "").strip()

        # Internal note.
        title_upper = title.upper()
        text_for_context = self._join_context_text(title, desc)

        # Internal note.
        groups = self._extract_groups(title)
        sources = self._extract_sources(title_upper)
        resource_form = self._extract_resource_form(title)
        platforms = self._extract_platforms(title_upper)
        versions = self._extract_versions(title_upper)
        seasons = self._extract_seasons(title)
        episodes = self._extract_episodes(title)
        if not episodes and desc:
            episodes = self._extract_episodes_from_desc(desc)
        disc_number, disc_total = self._extract_disc_info(title)

        # Internal note.
        desc_upper = desc.upper()
        resolution = extract_resolution(title_upper) or extract_resolution(desc_upper)
        video_codec = self._best_ranked_value(
            extract_video_codec(title_upper),
            extract_video_codec(desc_upper),
            VIDEO_CODEC_RANK,
        )
        audio_codec = self._best_ranked_value(
            extract_audio_codec(title_upper),
            extract_audio_codec(desc_upper),
            AUDIO_CODEC_RANK,
        )
        hdr_type = self._best_ranked_value(
            extract_hdr_type(title_upper),
            extract_hdr_type(desc_upper),
            HDR_TYPE_RANK,
        )
        audio_channels = extract_audio_channels(title_upper) or extract_audio_channels(desc_upper)
        color_depth = extract_color_depth(title_upper) or extract_color_depth(desc_upper)

        # Internal note.
        content_type = self._detect_content_type(title)
        language = self._extract_language(text_for_context)
        subtitle = self._extract_subtitle(text_for_context)

        return ResourceAttributes(
            title=title,
            desc=desc or None,
            groups=groups,
            sources=sources,
            resource_form=resource_form,
            versions=versions,
            seasons=seasons,
            episodes=list(episodes),
            disc_number=disc_number,
            disc_total=disc_total,
            platforms=platforms,
            resolution=resolution,
            video_codec=video_codec,
            audio_codec=audio_codec,
            hdr_type=hdr_type,
            audio_channels=audio_channels,
            color_depth=color_depth,
            content_type=content_type,
            language=language,
            subtitle=subtitle,
        )

    def _is_valid_group(self, g: str, used_tokens: set) -> bool:
        return bool(g and 2 <= len(g) <= 30 and not re.match(r"^\d+$", g) and g.upper() not in used_tokens)

    def _extract_groups(self, title: str) -> list[str]:
        """Internal helper."""
        title_upper = title.upper()

        # Internal note.
        used_tokens = set()
        if re.search(r"\b(4K|2160P|1080P?|720P?|480P?|UHD)\b", title_upper):
            used_tokens.update(["4K", "2160P", "1080P", "720P", "480P", "UHD"])
        if re.search(r"\b(HEVC|H\.?265|X\.?265|AVC|H\.?264|X\.?264|AV1)\b", title_upper):
            used_tokens.update(["HEVC", "H265", "X265", "AVC", "H264", "X264", "AV1"])
        if re.search(r"\b(AAC|AC3|DTS|FLAC|TRUEHD|ATMOS|DDP|EAC3)\b", title_upper):
            used_tokens.update(["AAC", "AC3", "DTS", "FLAC", "TRUEHD", "ATMOS", "DDP", "EAC3", "DOLBY ATMOS"])
        if re.search(r"\b(HDR10\+|HDR10|HDR|DV|DOLBY.?VISION)\b", title_upper):
            used_tokens.update(["HDR10+", "HDR10", "HDR", "DV"])
        if re.search(r"\b(WEB.?DL|WEBDL|WEB.?RIP|WEBRIP|BLU.?RAY|BLURAY|BDRIP|BD|HDTV|DVDRIP|DVD|REMUX)\b", title_upper):
            used_tokens.update(["WEBDL", "WEB-DL", "WEBRIP", "WEB-RIP", "BLURAY", "BLU-RAY", "BDRIP", "BD", "HDTV", "DVDRIP", "DVD", "REMUX"])

        # 1) [Group] / 【Group】
        m_leading = re.search(r"^\s*[\[【]([^\[\]【】]+?)[\]】]", title, re.IGNORECASE)
        if m_leading:
            grp = m_leading.group(1).strip()
            if self._is_valid_group(grp, used_tokens):
                return [grp]

        # 2) text，text
        last_valid = None
        for pattern in GROUP_PATTERNS:
            for match in re.finditer(pattern, title, re.IGNORECASE):
                grp = match.group(1).strip()
                if self._is_valid_group(grp, used_tokens):
                    last_valid = grp
        if last_valid:
            return [last_valid]

        return []

    def _extract_sources(self, title: str) -> list[str]:
        """Internal helper."""
        sources_set = set()
        for source, pattern in SOURCE_PATTERNS.items():
            if re.search(pattern, title, re.IGNORECASE):
                sources_set.add(source)

        if re.search(DVD_DISC_PATTERN, title, re.IGNORECASE):
            sources_set.add(SOURCE_DVD)
        if re.search(BLURAY_DISC_PATTERN, title, re.IGNORECASE):
            if re.search(UHD_BLURAY_DISC_PATTERN, title, re.IGNORECASE):
                sources_set.add(SOURCE_UHD_BLURAY)
            else:
                sources_set.add(SOURCE_BLURAY)

        # Internal note.
        if SOURCE_UHD_BLURAY in sources_set and SOURCE_BLURAY in sources_set:
            sources_set.discard(SOURCE_BLURAY)

        return list(sources_set)

    def _extract_resource_form(self, title: str) -> str | None:
        """Internal helper."""
        title_upper = title.upper()
        if re.search(ISO_IMAGE_PATTERN, title, re.IGNORECASE):
            if re.search(DVD_DISC_PATTERN, title, re.IGNORECASE) or re.search(r"\bDVD\b", title, re.IGNORECASE):
                return RESOURCE_FORM_DVD_DISC
            if re.search(UHD_BLURAY_DISC_PATTERN, title_upper, re.IGNORECASE):
                return RESOURCE_FORM_BLURAY_DISC
            if re.search(BLURAY_DISC_PATTERN, title, re.IGNORECASE) or re.search(r"\b(?:BLURAY|BLU[ ._-]*RAY|BD)\b", title, re.IGNORECASE):
                return RESOURCE_FORM_BLURAY_DISC
            return None
        if re.search(DVD_DISC_PATTERN, title, re.IGNORECASE):
            return RESOURCE_FORM_DVD_DISC
        if re.search(BLURAY_DISC_PATTERN, title, re.IGNORECASE):
            return RESOURCE_FORM_BLURAY_DISC
        if self._looks_like_bluray_disc_by_codec(title):
            return RESOURCE_FORM_BLURAY_DISC
        return RESOURCE_FORM_VIDEO_FILE

    def _looks_like_bluray_disc_by_codec(self, title: str) -> bool:
        if not re.search(r"\b(?:BLURAY|BLU[ ._-]*RAY|BD)\b", title, re.IGNORECASE):
            return False
        if not re.search(BLURAY_DISC_CODEC_PATTERN, title, re.IGNORECASE):
            return False
        if not re.search(BLURAY_LOSSLESS_AUDIO_PATTERN, title, re.IGNORECASE):
            return False
        return re.search(NON_DISC_RELEASE_PATTERN, title, re.IGNORECASE) is None

    def _extract_disc_info(self, title: str) -> tuple[int | None, int | None]:
        for pattern in DISC_PATTERNS:
            match = re.search(pattern, title, re.IGNORECASE)
            if not match:
                continue
            disc_number = int(match.group(1))
            disc_total = int(match.group(2)) if match.lastindex and match.lastindex >= 2 else None
            if disc_number <= 0:
                continue
            if disc_total is not None and disc_total < disc_number:
                disc_total = None
            return disc_number, disc_total
        return None, None

    def _extract_platforms(self, title: str) -> list[str]:
        """Internal helper."""
        platforms: list[str] = []
        for platform, pattern in PLATFORM_PATTERNS.items():
            if re.search(pattern, title, re.IGNORECASE):
                platforms.append(platform)
        return list(set(platforms))

    def _extract_versions(self, title: str) -> list[str]:
        """Internal helper."""
        versions = []

        for version, pattern in VERSION_PATTERNS.items():
            if re.search(pattern, title, re.IGNORECASE):
                versions.append(version)

        return versions

    def _extract_seasons(self, title: str) -> list[int]:
        """Internal helper."""
        seasons_set = set()

        # 1) S01-S03 / S1-3 / Season 1-3 / Season.1-4 / 第1-3季
        range_patterns = [
            r"\bS(\d{1,2})\s*[-–—~]\s*(?:S)?(\d{1,2})\b",
            r"\bSeason[\s.]+(\d{1,2})\s*[-–—~]\s*(\d{1,2})\b",
            r"第(\d{1,2})\s*[-–—~]\s*(\d{1,2})\s*季",
        ]

        for pattern in range_patterns:
            for m in re.finditer(pattern, title, re.IGNORECASE):
                try:
                    start = int(m.group(1))
                    end = int(m.group(2))
                except (ValueError, TypeError):
                    continue
                if start > end:
                    # Internal note.
                    start, end = end, start
                # Internal note.
                start = max(1, start)
                end = min(50, end)
                for s in range(start, end + 1):
                    seasons_set.add(s)

        # 2) "Season 1,2,3" / "Season.1,2,3" / "第1,2季"
        list_patterns = [
            r"\bSeason[\s.]+((?:\d{1,2}[,，\s]+)*\d{1,2})\b",
            r"第((?:\d{1,2}[,，、\s]+)*\d{1,2})季",
        ]

        for pattern in list_patterns:
            for m in re.finditer(pattern, title, re.IGNORECASE):
                nums = re.split(r"[,，、\s]+", m.group(1))
                for n in nums:
                    try:
                        v = int(n)
                    except (ValueError, TypeError):
                        continue
                    if 1 <= v <= 50:
                        seasons_set.add(v)

        # 3) text（S01, Season 1, text1text text）
        for pattern in SEASON_PATTERNS:
            for match in re.finditer(pattern, title, re.IGNORECASE):
                try:
                    season_num = int(match.group(1))
                except (ValueError, TypeError):
                    continue
                if 1 <= season_num <= 50:
                    seasons_set.add(season_num)

        # Internal note.
        seasons = sorted(list(seasons_set))
        return seasons

    def _extract_episodes(self, title: str) -> list[int]:
        """Internal helper."""
        episodes: list[int] = []

        for pattern in EPISODE_PATTERNS:
            matches = list(re.finditer(pattern, title, re.IGNORECASE))
            # Internal note.
            for match in matches:
                groups = match.groups()
                # Internal note.
                if len(groups) >= 2 and groups[1]:
                    try:
                        start = int(groups[0])
                        end = int(groups[1])
                    except (ValueError, TypeError):
                        continue
                    is_concatenated_multi_episode = re.search(r"E\d{1,3}E\d{1,3}", match.group(0), re.IGNORECASE) is not None
                    if is_concatenated_multi_episode and 1 <= start <= 999 and 1 <= end <= 999:
                        episodes.extend([start, end])
                    elif 1 <= start < end <= 999:
                        # Internal note.
                        episodes.extend([i for i in range(start, end + 1)])
                else:
                    # Internal note.
                    ep_num = None
                    for g in groups:
                        if g:
                            try:
                                ep_num = int(g)
                                break
                            except (ValueError, TypeError):
                                continue
                    if ep_num and 1 <= ep_num <= 999:
                        episodes.append(ep_num)

        # Internal note.
        return list(set(episodes))

    def _extract_episodes_from_desc(self, desc: str) -> list[int]:
        complete_episodes = self._extract_complete_episode_coverage_from_desc(desc)
        if complete_episodes is not None:
            return complete_episodes

        episodes: list[int] = []
        patterns = [
            r"(?:更新至|更新到|更至|全|第)?\s*(\d{1,3})\s*[-–—~至到]\s*(\d{1,3})\s*集",
            r"(?:更新至|更新到|更至)?\s*第\s*(\d{1,3})\s*集",
            r"(?:更新至|更新到|更至)\s*(\d{1,3})\s*集",
            r"第\s*(\d{1,3})\s*集",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, desc, re.IGNORECASE):
                if self._is_excluded_desc_episode_match(desc, match.start(), match.end()):
                    continue
                if match.lastindex and match.lastindex >= 2 and match.group(2):
                    try:
                        start = int(match.group(1))
                        end = int(match.group(2))
                    except (ValueError, TypeError):
                        continue
                    if 1 <= start < end <= 999:
                        episodes.extend(range(start, end + 1))
                    continue
                try:
                    episode = int(match.group(1))
                except (ValueError, TypeError):
                    continue
                if 1 <= episode <= 999:
                    episodes.append(episode)
        return sorted(set(episodes))

    def _extract_complete_episode_coverage_from_desc(self, desc: str) -> list[int] | None:
        numeric_patterns = (
            r"(?:^|[|。；;\s])(?:全|全集|全季|完整|完整版|Complete)\s*(\d{1,3})\s*集",
            r"(?:^|[|。；;\s])(\d{1,3})\s*集\s*(?:全|全集|全季|完整|完整版|Complete)",
        )
        for pattern in numeric_patterns:
            match = re.search(pattern, desc, re.IGNORECASE)
            if not match:
                continue
            episode_count = int(match.group(1))
            if 1 <= episode_count <= 999:
                return list(range(1, episode_count + 1))

        complete_patterns = (
            r"(?:^|[|。；;\s])(?:全集|全季|完整版|Complete)(?:$|[|。；;\s])",
            r"(?:^|[|。；;\s])全(?:$|[|。；;\s])",
        )
        if any(re.search(pattern, desc, re.IGNORECASE) for pattern in complete_patterns):
            return []
        return None

    def _is_excluded_desc_episode_match(self, desc: str, start: int, end: int) -> bool:
        segment_start = max(
            desc.rfind(separator, 0, start)
            for separator in ("|", "。", "；", ";", "\n")
        ) + 1
        segment_end_candidates = [
            index
            for index in (desc.find(separator, end) for separator in ("|", "。", "；", ";", "\n"))
            if index >= 0
        ]
        segment_end = min(segment_end_candidates) if segment_end_candidates else len(desc)
        segment = desc[segment_start:segment_end]
        relative_start = start - segment_start
        relative_end = end - segment_start
        before = segment[:relative_start]
        after = segment[relative_end:]
        before_tail = before[-12:]
        after_head = after[:24]
        explicit_missing_patterns = (
            r"(?:不含|不包括|未含|未包括|缺少|缺失|遗漏|漏)\s*$",
            r"^\s*(?:不含|不包括|未含|未包括|缺少|缺失|遗漏|漏)",
            r"^\s*无\s*(?:DV|HDR|字幕|音轨|配音|国语|中字)\b",
            r"^\s*[^，,。；;|]{0,12}(?:替代|代替)\b",
            r"(?:替代|代替)\s*$",
        )
        return any(re.search(pattern, before_tail, re.IGNORECASE) for pattern in explicit_missing_patterns) or any(
            re.search(pattern, after_head, re.IGNORECASE) for pattern in explicit_missing_patterns
        )

    def _detect_content_type(self, title: str) -> str | None:
        """Internal helper."""
        # Internal note.
        # Internal note.
        return None

    def _extract_language(self, title: str) -> str | None:
        """Internal helper."""
        language_patterns = {
            "中文": r"(中文|国语|普通话|CHT|CHS|繁体|简体)",
            "英语": r"(英语|英文|ENG|ENGLISH)",
            "日语": r"(日语|日文|JPN|JAPANESE)",
            "韩语": r"(韩语|韩文|KOR|KOREAN)",
        }

        for language, pattern in language_patterns.items():
            if re.search(pattern, title, re.IGNORECASE):
                return language

        return None

    def _extract_subtitle(self, title: str) -> str | None:
        """Internal helper."""
        subtitle_patterns = {
            "特效": r"特效(?:字幕|中字|双语|字母)?",
            "双语": r"(双语(?:字幕|字母)?|BILINGUAL)",
            "中英": r"(中英|CHI.?ENG)",
            "中字": r"(中字|中文字幕|中文(?:特效)?字幕|简中|繁中|简繁(?:字幕)?|官方中文字幕)",
            "英字": r"(英字|英文字幕|英语字幕)",
            "外挂": r"(外挂|EXTERNAL)",
            "PGS": r"\bPGS\b",
            "内嵌": r"(内嵌|内封|EMBEDDED)",
        }

        for subtitle_type, pattern in subtitle_patterns.items():
            if re.search(pattern, title, re.IGNORECASE):
                return subtitle_type

        return None

    def _join_context_text(self, title: str, desc: str) -> str:
        return "\n".join(part for part in [title or "", desc or ""] if part)

    def _best_ranked_value(self, primary: str | None, fallback: str | None, ranking: Mapping[str, int]) -> str | None:
        if not primary:
            return fallback
        if not fallback:
            return primary
        fallback_rank = ranking[fallback] if fallback in ranking else 0
        primary_rank = ranking[primary] if primary in ranking else 0
        return fallback if fallback_rank > primary_rank else primary


# Internal note.
resource_parser = ResourceParser()
