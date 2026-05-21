from __future__ import annotations

import re

from app.schemas.domain.resource_attributes import NamingContext

TOKEN_PATTERN = re.compile(r"\{([^{}:]+?)(?::(0+))?\}")
CAMEL_BOUNDARY_PATTERN = re.compile(r"([a-z0-9])([A-Z])")
YEAR_PATTERN = re.compile(r"(19|20)\d{2}")
SPECIAL_KEYWORD_PATTERN = re.compile(
    r"\b(SP|SPECIAL|SPECIALS|OVA|OAD|NCOP|NCED|BONUS|EXTRA|EXTRAS|OMAKE)\b",
    re.IGNORECASE,
)
MOVIE_MEDIA_TYPE = "movie"
TV_MEDIA_TYPE = "tv"
MOVIE_CATEGORY = "movie"
NORMAL_EPISODE_CATEGORY = "normal_episode"
EXTRA_EPISODE_CATEGORY = "extra_episode"
GLOBAL_STRONG_TOKENS = {"title"}
TV_STRONG_TOKENS = {"season", "season_folder"}
TV_NORMAL_EPISODE_STRONG_TOKENS = {"episode"}
EMPTY_WHEN_MISSING_TOKENS = {
    "disc",
    "disc_total",
    "disc_folder",
    "disc_package_name",
    "disc_suffix",
    "resource_form",
    "package_layout",
}

TOKEN_ALIASES = {
    "Movie Title": "title",
    "Series Title": "title",
    "Title": "title",
    "Year": "year",
    "ReleaseYear": "year",
    "tmdbId": "tmdb_id",
    "imdbId": "imdb_id",
    "imdb_id": "imdb_id",
    "Quality": "quality",
    "QualityFull": "quality",
    "resolution": "resolution",
    "Source": "source",
    "SourceShort": "source_short",
    "Release Group": "group",
    "ReleaseGroup": "group",
    "Group": "group",
    "language": "language",
    "audio": "audio",
    "videoCodec": "video_codec",
    "container": "container",
    "size": "size",
    "runtime": "runtime",
    "season": "season",
    "episode": "episode",
    "seasonFolder": "season_folder",
    "Episode Title": "episode_title",
    "episodeTitle": "episode_title",
    "disc": "disc",
    "disc_number": "disc",
    "discNumber": "disc",
    "discTotal": "disc_total",
    "disc_total": "disc_total",
    "discFolder": "disc_folder",
    "disc_folder": "disc_folder",
    "discPackageName": "disc_package_name",
    "disc_package_name": "disc_package_name",
    "discSuffix": "disc_suffix",
    "disc_suffix": "disc_suffix",
    "resourceForm": "resource_form",
    "resource_form": "resource_form",
    "packageLayout": "package_layout",
    "package_layout": "package_layout",
}
CANONICAL_TOKENS = tuple(sorted(set(TOKEN_ALIASES.values())))


def normalize_token_name(token: str) -> str:
    token_text = str(token or "").strip()
    if not token_text:
        return ""
    if token_text in TOKEN_ALIASES:
        return TOKEN_ALIASES[token_text]
    normalized = CAMEL_BOUNDARY_PATTERN.sub(r"\1_\2", token_text)
    normalized = normalized.replace("-", " ").replace("/", " ")
    normalized = re.sub(r"\s+", "_", normalized.strip())
    return normalized.lower()


def _migrate_template_match(match: re.Match[str]) -> str:
    token = normalize_token_name(match.group(1))
    pad = match.group(2)
    return f"{{{token}:{pad}}}" if pad else f"{{{token}}}"


def migrate_template_tokens(template: str) -> str:
    if not template:
        return ""
    return TOKEN_PATTERN.sub(_migrate_template_match, template)


def split_legacy_template(template: str) -> tuple[str, str]:
    if not template:
        return "", ""
    if "/" in template:
        return template.rsplit("/", 1)
    return "", template


def combine_templates(dir_template: str, file_template: str) -> str:
    directory = (dir_template or "").strip()
    file_name = (file_template or "").strip()
    if directory and file_name:
        return f"{directory}/{file_name}"
    return directory or file_name


def _fmt_number(value: str | None, pad: int | None = None) -> str:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return str(value) if value is not None else ""
    if pad:
        return str(number).zfill(int(pad))
    return str(number)


def _fmt_episode_numbers(values: list[int], pad: int | None = None) -> str:
    formatted = [_fmt_number(str(value), pad=pad) for value in values if int(value) > 0]
    if not formatted:
        return ""
    return formatted[0] + "".join(f"E{value}" for value in formatted[1:])


def _infer_media_type(record: NamingContext) -> str:
    media_type = (record.media_type or record.attributes.content_type or "").strip().lower()
    if media_type in {MOVIE_MEDIA_TYPE, TV_MEDIA_TYPE}:
        return media_type
    if record.season_number is not None:
        return TV_MEDIA_TYPE
    return MOVIE_MEDIA_TYPE


def _infer_naming_category(record: NamingContext) -> str:
    media_type = _infer_media_type(record)
    if media_type != TV_MEDIA_TYPE:
        return MOVIE_CATEGORY

    if record.naming_category in {NORMAL_EPISODE_CATEGORY, EXTRA_EPISODE_CATEGORY}:
        return record.naming_category

    attrs = record.attributes
    versions = {str(item).strip().lower() for item in (attrs.versions or []) if item}
    explicit_special = bool(
        {"special", "special edition", "ova", "oad"} & versions
        or SPECIAL_KEYWORD_PATTERN.search(" ".join(filter(None, [record.resource_title, record.torrent_name, attrs.episode_title])))
        or str(attrs.content_type or "").strip().lower() in {"special", "extra", "ova", "oad"}
    )
    episodes = [episode for episode in (attrs.episodes or []) if int(episode) > 0]
    if explicit_special or not episodes:
        return EXTRA_EPISODE_CATEGORY
    return NORMAL_EPISODE_CATEGORY


def _resolve_year(record: NamingContext) -> str:
    attrs = record.attributes
    if attrs.year:
        return str(attrs.year)
    if attrs.release_year:
        return str(attrs.release_year)
    date_text = attrs.release_date or attrs.first_air_date or ""
    match = YEAR_PATTERN.search(str(date_text))
    return match.group(0) if match else ""


def _build_values(record: NamingContext) -> dict[str, str]:
    attrs = record.attributes
    title = (record.resource_title or attrs.title or "").strip()
    resolution = (attrs.resolution or "").strip()
    sources = attrs.sources or []
    source = str(sources[0]).strip() if sources else ""
    groups = attrs.groups or []
    group = str(groups[0]).strip() if groups else ""
    language = (attrs.language or "").strip()
    audio = (attrs.audio_codec or "").strip()
    video_codec = (attrs.video_codec or "").strip()
    container = (attrs.subtitle or "").strip()
    runtime = (attrs.runtime or "").strip()
    season = str(record.season_number) if record.season_number is not None else ""
    episodes = [episode for episode in (attrs.episodes or []) if int(episode) > 0]
    episode = str(episodes[0]) if episodes else ""
    quality = resolution or source
    disc_number = str(attrs.disc_number) if attrs.disc_number else ""
    disc_total = str(attrs.disc_total) if attrs.disc_total else ""
    resource_form = str(attrs.resource_form or "").strip()
    package_layout = str(attrs.package_layout or "").strip()
    disc_package_name = str(record.disc_package_name or "").strip()
    disc_folder = f"Disc {_fmt_number(disc_number, pad=2)}" if disc_number else ""
    if not disc_folder and resource_form and _infer_media_type(record) == TV_MEDIA_TYPE:
        disc_folder = resource_form
    disc_suffix = f" - Disc {_fmt_number(disc_number, pad=2)}" if disc_number else ""
    return {
        "title": title,
        "year": _resolve_year(record),
        "tmdb_id": str(attrs.tmdb_id or "").strip(),
        "imdb_id": str(attrs.imdb_id or "").strip(),
        "quality": quality,
        "resolution": resolution,
        "source": source,
        "source_short": source,
        "group": group,
        "language": language,
        "audio": audio,
        "video_codec": video_codec,
        "container": container,
        "size": str(record.size or ""),
        "runtime": runtime,
        "season": season,
        "episode": episode,
        "episode_title": str(attrs.episode_title or "").strip(),
        "disc": disc_number,
        "disc_total": disc_total,
        "disc_folder": disc_folder,
        "disc_package_name": disc_package_name,
        "disc_suffix": disc_suffix,
        "resource_form": resource_form,
        "package_layout": package_layout,
    }


def _is_strong_token(token: str, record: NamingContext) -> bool:
    category = _infer_naming_category(record)
    media_type = _infer_media_type(record)
    if token in GLOBAL_STRONG_TOKENS:
        return True
    if media_type == TV_MEDIA_TYPE and token in TV_STRONG_TOKENS:
        return True
    if media_type == TV_MEDIA_TYPE and category == NORMAL_EPISODE_CATEGORY and token in TV_NORMAL_EPISODE_STRONG_TOKENS:
        return True
    return False


def _resolve_token(token: str, record: NamingContext, values: dict[str, str]) -> str:
    if token == "season_folder":
        season_value = values["season"] if "season" in values else ""
        return f"Season {_fmt_number(season_value)}" if season_value else ""
    return values[token] if token in values else ""


def _render_naming_token(match: re.Match[str], record: NamingContext, values: dict[str, str]) -> str:
    raw_token = match.group(1)
    canonical_token = normalize_token_name(raw_token)
    pad = len(match.group(2)) if match.group(2) else None
    value = _resolve_token(canonical_token, record, values)
    if value:
        if canonical_token == "episode":
            episodes = [episode for episode in (record.attributes.episodes or []) if int(episode) > 0]
            if len(episodes) > 1:
                return _fmt_episode_numbers(episodes, pad=pad)
        if pad and canonical_token in {"season", "episode", "disc", "disc_total"}:
            return _fmt_number(value, pad=pad)
        return value
    if canonical_token in EMPTY_WHEN_MISSING_TOKENS:
        return ""
    if _is_strong_token(canonical_token, record):
        raise ValueError(f"missing naming field: {canonical_token}")
    return f"unknown_{canonical_token}" if canonical_token else "unknown_field"


def _cleanup_empty_wrappers(text: str) -> str:
    cleaned = text
    wrapper_patterns = (
        re.compile(r"\(\s*\)"),
        re.compile(r"\[\s*\]"),
    )
    while True:
        next_cleaned = cleaned
        for pattern in wrapper_patterns:
            next_cleaned = pattern.sub("", next_cleaned)
        if next_cleaned == cleaned:
            return cleaned
        cleaned = next_cleaned


def _cleanup_dangling_episode_suffix(text: str) -> str:
    return re.sub(r"\b(S\d+)(?:E(?:unknown_episode)?)(?=$|[ ._\-()[\]])", r"\1", text)


def _cleanup_segment(text: str) -> str:
    cleaned = _cleanup_empty_wrappers(text)
    cleaned = _cleanup_dangling_episode_suffix(cleaned)
    cleaned = re.sub(r"\.{2,}", ".", cleaned)
    cleaned = re.sub(r"_{2,}", "_", cleaned)
    cleaned = re.sub(r"-{2,}", "-", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = cleaned.strip(" ._-")
    return cleaned


def _cleanup_rendered_name(text: str) -> str:
    segments = [_cleanup_segment(segment) for segment in text.split("/")]
    return "/".join(segment for segment in segments if segment)


def format_name(template: str, record: NamingContext) -> str:
    if not template:
        return ""
    values = _build_values(record)
    rendered_parts: list[str] = []
    last_index = 0
    for match in TOKEN_PATTERN.finditer(template):
        start, end = match.span()
        rendered_parts.append(template[last_index:start])
        rendered_parts.append(_render_naming_token(match, record, values))
        last_index = end
    rendered_parts.append(template[last_index:])
    rendered = "".join(rendered_parts)
    sanitized = "".join(character for character in rendered if character.isalnum() or character in (" ", ".", "-", "_", "/", ":", "(", ")", "[", "]"))
    return _cleanup_rendered_name(sanitized)
