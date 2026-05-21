from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from app.schemas.domain.media import MediaFullInfo


def is_movie_nfo_complete(path: Path | None, media: MediaFullInfo) -> bool:
    return _has_required_text(path, _common_required_fields(media))


def is_tvshow_nfo_complete(path: Path | None, media: MediaFullInfo) -> bool:
    return _has_required_text(path, _common_required_fields(media))


def is_season_nfo_complete(path: Path | None) -> bool:
    return _has_required_text(path, ["title"])


def is_episode_nfo_complete(
    path: Path | None,
    *,
    require_title: bool = True,
    require_plot: bool = True,
) -> bool:
    required_fields: list[str] = []
    if require_title:
        required_fields.append("title")
    if require_plot:
        required_fields.append("plot")
    return _has_required_text(path, required_fields)


def _common_required_fields(media: MediaFullInfo) -> list[str]:
    fields = ["title"]
    if (media.overview or "").strip():
        fields.append("plot")
    return fields


def _has_required_text(path: Path | None, field_names: list[str]) -> bool:
    if path is None or not path.exists():
        return False
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return False
    for field_name in field_names:
        if not _element_text(root, field_name):
            return False
    return True


def _element_text(root: ET.Element, field_name: str) -> str:
    value = root.findtext(field_name)
    return value.strip() if value else ""
