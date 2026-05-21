"""
Resource filtering and scoring logic for resource matching.

Pure domain functions — no database access, no side effects.
Used by resource selection flows to filter/score candidate resources.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Mapping

from app.schemas.domain.quality_profile import QualityProfile
from app.schemas.domain.resource_attributes import ResourceAttributes
from app.schemas.domain.resource_search import Resource
from app.schemas.domain.resource_filters import ResourceFilters, ResourceUnmatchedRule
from app.services.domain.resource.quality import RESOURCE_FORM_BLURAY_DISC, RESOURCE_FORM_DVD_DISC, normalize_hdr_type
from app.services.domain.resource.quality import quality_sort_key
from app.services.domain.resource.tags import (
    PreferenceScoreBreakdown,
    build_tag_map,
    compute_tag_score,
    matches_tag,
    resource_match_text,
)

logger = logging.getLogger("app.services.domain.resource.filtering")

RESOURCE_KIND_VIDEO_FILE = "video_file"
RESOURCE_KIND_ORIGINAL_DISC = "original_disc"
ORIGINAL_DISC_FORMS = {RESOURCE_FORM_BLURAY_DISC, RESOURCE_FORM_DVD_DISC}
QUALITY_SCORE_RANK_BASE = 100
QUALITY_SCORE_TAG_RANGE = 1_000_000
QUALITY_SCORE_TAG_SCALE = QUALITY_SCORE_TAG_RANGE * 2 + 1


def has_meaningful_filter_criteria(filters: ResourceFilters | None) -> bool:
    if not filters:
        return False
    resource_kind = {str(value) for value in (filters.resource_kind or [])}
    return any((
        resource_kind and resource_kind != {RESOURCE_KIND_VIDEO_FILE},
        filters.resolution,
        filters.source,
        filters.resource_form,
        filters.codec,
        filters.hdr_type,
        filters.audio_codec,
        filters.audio_channels,
        filters.color_depth,
        filters.include_keywords,
        filters.exclude_keywords,
        filters.tags,
    ))


def matches_unmatched_rules(resource: Resource, rules: list[ResourceUnmatchedRule] | None) -> bool:
    if resource.resources.matched_by_id:
        return True
    text = f"{resource.resources.title or ''}\n{resource.resources.description or ''}".strip()
    site = resource.resources.site
    for rule in rules or []:
        if rule.sites and site not in rule.sites:
            continue
        try:
            matched = re.search(rule.pattern, text, re.IGNORECASE) is not None if rule.pattern else False
        except re.error:
            matched = rule.pattern.lower() in text.lower()
        if matched:
            return True
    return False


def _resource_match_text(attrs: ResourceAttributes) -> tuple[str, str]:
    return resource_match_text(attrs)


def compute_preference_score_from_attrs(
    attrs: ResourceAttributes,
    quality_profile: QualityProfile | None,
) -> tuple[int, PreferenceScoreBreakdown]:
    """Compute a preference score for resource attributes according to tag_scores in quality profile."""
    if not quality_profile:
        return 0, PreferenceScoreBreakdown()
    return compute_tag_score(attrs, quality_profile.tag_scores)


def compute_preference_score(
    r: Resource,
    quality_profile: QualityProfile | None,
) -> tuple[int, PreferenceScoreBreakdown]:
    """Compute preference score for a Resource."""
    return compute_preference_score_from_attrs(r.attrs, quality_profile)


def compute_quality_upgrade_score_from_attrs(
    attrs: ResourceAttributes,
    quality_profile: QualityProfile | None,
) -> int:
    if not quality_profile:
        return 0
    ranks = quality_sort_key(attrs, quality_profile.ranking)
    score = 0
    for rank in ranks:
        score = score * QUALITY_SCORE_RANK_BASE + int(rank or 0)
    tag_score, _ = compute_preference_score_from_attrs(attrs, quality_profile)
    tag_bucket = max(-QUALITY_SCORE_TAG_RANGE, min(QUALITY_SCORE_TAG_RANGE, int(tag_score or 0)))
    return score * QUALITY_SCORE_TAG_SCALE + tag_bucket


def compute_quality_upgrade_score(
    r: Resource,
    quality_profile: QualityProfile | None,
) -> int:
    return compute_quality_upgrade_score_from_attrs(r.attrs, quality_profile)


def normalized_resource_kinds(filters: ResourceFilters | None) -> set[str]:
    if not filters or not filters.resource_kind:
        return {RESOURCE_KIND_VIDEO_FILE}
    return {str(value) for value in filters.resource_kind} or {RESOURCE_KIND_VIDEO_FILE}


def is_original_disc_attrs(attrs: ResourceAttributes) -> bool:
    return bool(attrs.package_layout or attrs.resource_form in ORIGINAL_DISC_FORMS)


def match_resource_kind(attrs: ResourceAttributes, filters: ResourceFilters | None) -> bool:
    categories = normalized_resource_kinds(filters)
    if is_original_disc_attrs(attrs):
        return RESOURCE_KIND_ORIGINAL_DISC in categories
    return RESOURCE_KIND_VIDEO_FILE in categories


def _collect_filter_reasons(
    attrs: ResourceAttributes,
    filters: ResourceFilters | None,
    quality_profile: QualityProfile | None = None,
) -> list[str]:
    title_raw, title = _resource_match_text(attrs)
    filter_reasons: list[str] = []

    if filters is not None or is_original_disc_attrs(attrs):
        if not match_resource_kind(attrs, filters):
            filter_reasons.append(f"resource_kind mismatch (want={sorted(normalized_resource_kinds(filters))}, have={'original_disc' if is_original_disc_attrs(attrs) else 'video_file'})")

    if filters and filters.resolution:
        res_have = attrs.resolution
        if not res_have or res_have.lower() not in [w.lower() for w in filters.resolution]:
            filter_reasons.append(f"resolution mismatch (want={filters.resolution}, have={attrs.resolution})")

    if filters and filters.source:
        src_have = [s.lower() for s in attrs.sources]
        if not src_have or not any(w.lower() in src_have for w in filters.source):
            filter_reasons.append(f"source mismatch (want={filters.source}, have={attrs.sources})")

    if filters and filters.resource_form:
        form_have = attrs.resource_form
        if not form_have or form_have.lower() not in [w.lower() for w in filters.resource_form]:
            filter_reasons.append(f"resource_form mismatch (want={filters.resource_form}, have={attrs.resource_form})")

    if filters and filters.codec:
        codec_have = attrs.video_codec
        if not codec_have or codec_have.lower() not in [w.lower() for w in filters.codec]:
            filter_reasons.append(f"codec mismatch (want={filters.codec}, have={attrs.video_codec})")

    if filters and filters.hdr_type:
        hdr_have = normalize_hdr_type(attrs.hdr_type)
        hdr_wanted = [value for value in (normalize_hdr_type(hdr) for hdr in filters.hdr_type) if value]
        if not hdr_have or hdr_have.lower() not in [h.lower() for h in hdr_wanted]:
            filter_reasons.append(f"hdr_type mismatch (want={filters.hdr_type}, have={attrs.hdr_type})")

    if filters and filters.audio_codec:
        ac_have = attrs.audio_codec
        if not ac_have or ac_have.lower() not in [ac.lower() for ac in filters.audio_codec]:
            filter_reasons.append(f"audio_codec mismatch (want={filters.audio_codec}, have={attrs.audio_codec})")

    if filters and filters.audio_channels:
        ach_have = attrs.audio_channels
        if not ach_have or ach_have.lower() not in [ach.lower() for ach in filters.audio_channels]:
            filter_reasons.append(f"audio_channels mismatch (want={filters.audio_channels}, have={attrs.audio_channels})")

    if filters and filters.color_depth:
        cd_have = attrs.color_depth
        if not cd_have or cd_have.lower() not in [cd.lower() for cd in filters.color_depth]:
            filter_reasons.append(f"color_depth mismatch (want={filters.color_depth}, have={attrs.color_depth})")

    if filters and filters.include_keywords:
        missing = [k for k in filters.include_keywords if k.lower() not in title]
        if missing:
            filter_reasons.append(f"missing include_keywords={missing}")

    if filters and filters.exclude_keywords:
        found = [k for k in filters.exclude_keywords if k.lower() in title]
        if found:
            filter_reasons.append(f"matched exclude_keywords={found}")

    if filters and filters.tags:
        tag_map = build_tag_map(list(filters.tags))
        for tag_id in filters.tags:
            if tag_id not in tag_map:
                continue
            tag = tag_map[tag_id]
            if not matches_tag(tag, title_raw, title):
                filter_reasons.append(f"tag '{tag.name}' not matched")

    if quality_profile and quality_profile.min_score is not None:
        score, _ = compute_preference_score_from_attrs(attrs, quality_profile)
        if score < int(quality_profile.min_score):
            filter_reasons.append(f"min_score not met (want>={quality_profile.min_score}, have={score})")

    return filter_reasons


def match_filters_against_attrs(
    attrs: ResourceAttributes,
    filters: ResourceFilters | None,
    quality_profile: QualityProfile | None = None,
) -> bool:
    return len(_collect_filter_reasons(attrs, filters, quality_profile)) == 0


def match_filters(
    r: Resource,
    filters: ResourceFilters | None,
    quality_profile: QualityProfile | None = None,
) -> bool:
    """Evaluate `filters` against a resource `r`.

    Season-based filtering is no longer handled here; this method only
    applies the configured `filters` (resolution/source/codec/seeders/keywords).
    """
    return len(_collect_filter_reasons(r.attrs, filters, quality_profile)) == 0


def match_episodes(
    r: Resource,
    episodes: set[int],
    required_scores: Mapping[int, int] | None = None,
    quality_profile: QualityProfile | None = None,
) -> bool:
    """Check if resource matches requested episodes and meets score requirements."""
    if not r.attrs.episodes:
        return True
    resource_eps = set(r.attrs.episodes)
    wanted = resource_eps & set(episodes)
    if not wanted:
        return False
    if not required_scores:
        return True
    score = compute_quality_upgrade_score(r, quality_profile) if quality_profile else 0
    for ep in wanted:
        ep_key = int(ep)
        req = required_scores[ep_key] if ep_key in required_scores else None
        if req is None or score >= int(req):
            return True
    return False


def match_season(r: Resource, season_number: int) -> bool:
    """Return True if resource `r` matches the provided season_number."""
    # If seasons is empty, assume it's season 1
    if not r.attrs or not r.attrs.seasons:
        return 1 == season_number

    return season_number in r.attrs.seasons
