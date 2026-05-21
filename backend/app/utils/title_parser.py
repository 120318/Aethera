import re
import logging

logger = logging.getLogger(__name__)


def _has_cjk(value: str) -> bool:
    return any(0x4E00 <= ord(char) <= 0x9FFF for char in value)


def _parse_season_number(value: str, char_map: dict[str, int]) -> int | None:
    if char_map and value in char_map:
        return char_map[value]
    try:
        return int(value)
    except ValueError:
        return None


def _parse_trailing_small_cjk_number(value: str) -> tuple[str, int | None]:
    if re.search(r'(?:19|20)\d{2}\s*$', value):
        return value, None
    match = re.search(r'(.+?)([1-9]\d?)$', value)
    if not match:
        return value, None
    base_title = match.group(1).strip()
    if len(base_title) < 2 or not _has_cjk(base_title):
        return value, None
    number = int(match.group(2))
    if number > 20:
        return value, None
    return base_title, number


def _strip_trailing_year_with_separator(title: str) -> str:
    cleaned = re.sub(r'\s*[（(]\s*(?:19|20)\d{2}\s*[）)]\s*$', '', title).strip()
    cleaned = re.sub(r'\s+(?:19|20)\d{2}\s*$', '', cleaned).strip()
    return cleaned


def build_loose_tmdb_search_title(title: str) -> str:
    if not title:
        return title
    cleaned = re.sub(r'(?:19|20)\d{2}\s*$', '', title.strip()).strip()
    if cleaned != title.strip() and len(cleaned) >= 2:
        return cleaned
    match = re.search(r'(.+?)([1-9]\d?)$', title.strip())
    if match:
        base_title = match.group(1).strip()
        if len(base_title) >= 2 and _has_cjk(base_title):
            return base_title
    return title.strip()


def build_tmdb_search_title(title: str, *, is_tv: bool) -> tuple[str, int | None]:
    cleaned_title = title.strip() if title else title
    season_number = None
    if is_tv:
        cleaned_title, season_number = parse_tv_title(cleaned_title)
    return _strip_trailing_year_with_separator(cleaned_title), season_number


def parse_tv_title(title: str) -> tuple[str, int | None]:
    if not title:
        return title, None
    
    season_patterns = [
        (r'第\s*([一二三四五六七八九十\d]+)\s*季', {
            '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
            '六': 6, '七': 7, '八': 8, '九': 9, '十': 10
        }),
        (r'Season\s+(\d+)', {}),
        (r'S(\d+)', {}),
    ]
    
    cleaned_title = title.strip()
    season_number = None
    
    for pattern, char_map in season_patterns:
        match = re.search(pattern, cleaned_title, re.IGNORECASE)
        if match:
            season_str = match.group(1)
            parsed = _parse_season_number(season_str, char_map)
            if parsed:
                season_number = parsed
                cleaned_title = re.sub(pattern, '', cleaned_title, flags=re.IGNORECASE).strip()
                break

    if season_number is None:
        cleaned_title, season_number = _parse_trailing_small_cjk_number(cleaned_title)
    
    return cleaned_title, season_number
