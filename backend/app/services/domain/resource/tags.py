from __future__ import annotations

import logging
import re
from collections.abc import Mapping, Sequence

from app.schemas.config import Tag
from app.schemas.domain.resource_attributes import ResourceAttributes
from app.services.config.settings_service import settings_service

logger = logging.getLogger("app.services.domain.resource.tags")


class TagScoreBreakdown:
    def __init__(self, tag_id: str, name: str, score: int) -> None:
        self.id = tag_id
        self.name = name
        self.score = score


class PreferenceScoreBreakdown:
    def __init__(self, tag_scores: list[TagScoreBreakdown] | None = None, total: int = 0) -> None:
        self.tag_scores = tag_scores or []
        self.total = total


def resource_match_text(attrs: ResourceAttributes) -> tuple[str, str]:
    raw = "\n".join(part for part in [attrs.title or "", attrs.desc or ""] if part)
    return raw, raw.lower()


def tag_has_criteria(tag: Tag) -> bool:
    return bool(tag.include_keywords or tag.exclude_keywords or tag.regex)


def matches_tag(tag: Tag, title_raw: str, title: str) -> bool:
    if tag.include_keywords and any(keyword.lower() not in title for keyword in tag.include_keywords):
        return False
    if tag.exclude_keywords and any(keyword.lower() in title for keyword in tag.exclude_keywords):
        return False
    if not tag.regex:
        return True
    try:
        return re.search(tag.regex, title_raw, re.IGNORECASE) is not None
    except re.error:
        logger.warning("Invalid regex in tag '%s': %s", tag.name, tag.regex)
        return False


def build_tag_map(tag_ids: Sequence[str]) -> Mapping[str, Tag]:
    if not tag_ids:
        return {}
    wanted = set(tag_ids)
    return {
        tag.id: tag
        for tag in settings_service.list_tags()
        if tag.id in wanted
    }


def resolve_tag_names(attrs: ResourceAttributes, tags: Sequence[Tag] | None = None) -> list[str]:
    title_raw, title = resource_match_text(attrs)
    names: list[str] = []
    seen: set[str] = set()
    for tag in tags if tags is not None else settings_service.list_tags():
        tag_name = tag.name.strip()
        if not tag_name or tag_name in seen or not tag_has_criteria(tag):
            continue
        if matches_tag(tag, title_raw, title):
            names.append(tag_name)
            seen.add(tag_name)
    return names


def resolve_display_tags(
    attrs: ResourceAttributes,
    *,
    tags: Sequence[Tag] | None = None,
) -> list[str]:
    return resolve_tag_names(attrs, tags=tags)


def matches_tag_ids(attrs: ResourceAttributes, tag_ids: Sequence[str] | None) -> bool:
    if not tag_ids:
        return True
    title_raw, title = resource_match_text(attrs)
    tag_map = build_tag_map(list(tag_ids))
    for tag_id in tag_ids:
        if tag_id not in tag_map:
            continue
        if not matches_tag(tag_map[tag_id], title_raw, title):
            return False
    return True


def compute_tag_score(
    attrs: ResourceAttributes,
    tag_scores: Mapping[str, int] | None,
) -> tuple[int, PreferenceScoreBreakdown]:
    total = 0
    breakdown = PreferenceScoreBreakdown()
    if not tag_scores:
        return 0, breakdown
    title_raw, title = resource_match_text(attrs)
    tag_map = build_tag_map(list(tag_scores.keys()))
    matched_scores: list[TagScoreBreakdown] = []
    for tag_id, score in tag_scores.items():
        if tag_id not in tag_map:
            continue
        tag = tag_map[tag_id]
        if matches_tag(tag, title_raw, title):
            total += int(score)
            matched_scores.append(TagScoreBreakdown(tag_id=tag_id, name=tag.name, score=int(score)))
    breakdown.tag_scores = matched_scores
    breakdown.total = total
    return total, breakdown
