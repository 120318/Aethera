from __future__ import annotations

import logging
import re
from collections.abc import Mapping

from app.schemas.domain.quality_profile import QualityProfile
from app.schemas.domain.resource_attributes import ResourceAttributes
from app.schemas.domain.resource_search import Resource, ResourceSearchResult
from app.schemas.domain.resource_filters import ResourceFilters, ResourceUnmatchedRule
from app.schemas.domain.torrent import TorrentCoverageKind, TorrentPayload
from pydantic import BaseModel, Field

from app.schemas.media_id import MediaID
from app.services.domain.resource.filtering import (
    compute_preference_score,
    compute_quality_upgrade_score,
    match_episodes,
    match_filters,
    matches_unmatched_rules,
    match_season,
    normalized_resource_kinds,
)
from app.services.domain.resource.parser import resource_parser
from app.services.domain.resource.quality import quality_sort_key
from app.services.domain.resource.torrent_metadata import fetch_torrent_payload

logger = logging.getLogger("app.services.resource.selection")


class ResourceSelectionPlan(BaseModel):
    media_id: MediaID
    season_number: int | None = None
    episode_mode: bool = True
    filters: ResourceFilters | None = None
    quality_profile: QualityProfile | None = None
    target_episodes: set[int] = Field(default_factory=set)
    required_scores: dict[int, int] = Field(default_factory=dict)


def resource_sort_rank(
    result: Resource,
    quality_profile: QualityProfile | None,
) -> tuple[int, ...]:
    return quality_sort_key(result.attrs, quality_profile.ranking if quality_profile else None)


def automatic_resource_sort_rank(
    result: Resource,
    quality_profile: QualityProfile | None,
) -> tuple[int, tuple[int, ...], int, int, tuple[int, ...], int, int]:
    attrs = result.attrs
    core_attrs = attrs.model_copy(update={"audio_channels": None})
    ranking = quality_profile.ranking if quality_profile else None
    size_health_rank = _size_health_rank(result, attrs)
    seeders_health_rank = _seeders_health_rank(result)
    return (
        1 if size_health_rank > 0 and seeders_health_rank > 0 else 0,
        quality_sort_key(core_attrs, ranking),
        size_health_rank,
        seeders_health_rank,
        quality_sort_key(attrs, ranking),
        int(result.resources.seeders or 0),
        _resource_size_bytes(result),
    )


def has_valid_seeders(result: Resource) -> bool:
    return int(result.resources.seeders or 0) > 0


def _seeders_health_rank(result: Resource) -> int:
    seeders = int(result.resources.seeders or 0)
    if seeders >= 30:
        return 3
    if seeders >= 10:
        return 2
    if seeders >= 3:
        return 1
    return 0


def _size_health_rank(result: Resource, attrs: ResourceAttributes) -> int:
    size_bytes = _resource_size_bytes(result)
    gib = 1024**3
    if attrs.resolution == "2160p":
        if size_bytes >= 12 * gib:
            return 3
        if size_bytes >= 6 * gib:
            return 2
        if size_bytes >= 3 * gib:
            return 1
        return 0
    if attrs.resolution == "1080p":
        if size_bytes >= 6 * gib:
            return 3
        if size_bytes >= 3 * gib:
            return 2
        if size_bytes >= 1 * gib:
            return 1
        return 0
    if size_bytes > 0:
        return 1
    return 0


def _resource_size_bytes(result: Resource) -> int:
    value = str(result.resources.size or "").strip()
    if not value:
        return 0
    match = re.match(r"(?i)^\s*([0-9]+(?:\.[0-9]+)?)\s*([kmgt]?i?b|bytes?)?\s*$", value)
    if not match:
        return 0
    number = float(match.group(1))
    unit = (match.group(2) or "b").lower()
    multiplier = {
        "b": 1,
        "byte": 1,
        "bytes": 1,
        "kb": 1024,
        "kib": 1024,
        "mb": 1024**2,
        "mib": 1024**2,
        "gb": 1024**3,
        "gib": 1024**3,
        "tb": 1024**4,
        "tib": 1024**4,
    }.get(unit, 1)
    return int(number * multiplier)


def allows_disc_package_subscription(filters: ResourceFilters | None) -> bool:
    return "original_disc" in normalized_resource_kinds(filters)


def allows_video_file_subscription(filters: ResourceFilters | None) -> bool:
    return "video_file" in normalized_resource_kinds(filters)


def partition_search_results(
    plan: ResourceSelectionPlan,
    search_results: list[ResourceSearchResult],
    *,
    unmatched_rules: list[ResourceUnmatchedRule] | None,
) -> tuple[list[Resource], list[Resource], bool]:
    parsed_results = [
        Resource(resources=result, attrs=attrs)
        for result in search_results
        if (
            attrs := resource_parser.parse(result.title, desc=result.description)
        ) is not None and int(result.seeders or 0) > 0
    ]
    if not parsed_results:
        return [], [], False
    season_filtered = (
        [result for result in parsed_results if match_season(result, plan.season_number)]
        if plan.episode_mode else parsed_results
    )
    attribute_filtered = [result for result in season_filtered if match_filters(result, plan.filters, plan.quality_profile)]
    disc_attribute_filtered = season_filtered if allows_disc_package_subscription(plan.filters) else []
    video_attribute_filtered = attribute_filtered if allows_video_file_subscription(plan.filters) else []
    episode_filtered = [
        result
        for result in video_attribute_filtered
        if match_episodes(result, plan.target_episodes, plan.required_scores, plan.quality_profile)
    ]
    episode_filtered.extend(result for result in disc_attribute_filtered if result not in episode_filtered)
    logger.debug(
        "Resource selection filter summary: media=%s parsed=%d season=%d attribute=%d episode=%d targets=%s",
        plan.media_id,
        len(parsed_results),
        len(season_filtered),
        len(attribute_filtered),
        len(episode_filtered),
        sorted(plan.target_episodes),
    )
    if not episode_filtered:
        return [], [], False
    upgrade_policy = plan.filters.upgrade_policy if plan.filters and plan.filters.upgrade_policy else None
    locked_score = max(plan.required_scores.values()) if plan.required_scores else None
    if upgrade_policy and upgrade_policy.enabled and upgrade_policy.strategy == "consistent_skip_low" and locked_score is not None:
        episode_filtered = [
            result for result in episode_filtered if compute_quality_upgrade_score(result, plan.quality_profile) >= locked_score
        ]
    if not episode_filtered:
        return [], [], False
    standard_results: list[Resource] = []
    unmatched_results: list[Resource] = []
    has_any_id_match = any(result.resources.matched_by_id for result in episode_filtered)
    for result in episode_filtered:
        if matches_unmatched_rules(result, unmatched_rules):
            standard_results.append(result)
        else:
            unmatched_results.append(result)
    logger.debug(
        "Resource selection candidate partition: media=%s standard=%d unmatched=%d id_matched=%s",
        plan.media_id,
        len(standard_results),
        len(unmatched_results),
        has_any_id_match,
    )
    return standard_results, unmatched_results, has_any_id_match


async def select_resources(
    results: list[Resource],
    *,
    episodes: set[int] | None = None,
    filters: ResourceFilters | None = None,
    quality_profile: QualityProfile | None = None,
    required_scores: Mapping[int, int] | None = None,
    episode_mode: bool = True,
    existing_disc_numbers: set[int] | None = None,
) -> list[tuple[TorrentPayload, list[int], Resource]]:
    if episode_mode and allows_disc_package_subscription(filters):
        selected: list[tuple[TorrentPayload, list[int], Resource]] = []
        if allows_video_file_subscription(filters):
            selected.extend(await _select_video_file_resources(
                results,
                episodes=episodes,
                filters=filters,
                quality_profile=quality_profile,
                required_scores=required_scores,
                episode_mode=episode_mode,
            ))
        selected.extend(await _select_disc_package_resources(
            results,
            filters=filters,
            quality_profile=quality_profile,
            existing_disc_numbers=existing_disc_numbers or set(),
        ))
        return selected
    return await _select_video_file_resources(
        results,
        episodes=episodes,
        filters=filters,
        quality_profile=quality_profile,
        required_scores=required_scores,
        episode_mode=episode_mode,
    )


async def _select_video_file_resources(
    results: list[Resource],
    *,
    episodes: set[int] | None = None,
    filters: ResourceFilters | None = None,
    quality_profile: QualityProfile | None = None,
    required_scores: Mapping[int, int] | None = None,
    episode_mode: bool = True,
) -> list[tuple[TorrentPayload, list[int], Resource]]:
    needed_episodes = set(episodes) if episodes else set()
    candidates = [result for result in results if has_valid_seeders(result) and match_filters(result, filters, quality_profile)]
    selected_items: list[tuple[Resource, set[int], TorrentPayload | None]] = []
    while needed_episodes and candidates:
        best_resource = None
        best_rank: tuple | None = None
        best_known_covered: set[int] = set()
        for result in candidates:
            preference_score = compute_preference_score(result, quality_profile)[0]
            upgrade_score = compute_quality_upgrade_score(result, quality_profile)
            available = set(result.attrs.episodes) & needed_episodes if result.attrs.episodes else set(needed_episodes)
            covered = {
                ep
                for ep in available
                if not required_scores or upgrade_score >= (required_scores[ep] if ep in required_scores else -10**9)
            }
            if not covered:
                continue
            rank = (
                automatic_resource_sort_rank(result, quality_profile),
                preference_score,
                len(covered),
            )
            if best_rank is None or rank > best_rank:
                best_resource = result
                best_known_covered = covered
                best_rank = rank
        if not best_resource or not best_known_covered or best_rank is None:
            break
        if best_resource.attrs.episodes:
            selected_items.append((best_resource, best_known_covered, None))
            needed_episodes -= best_known_covered
            candidates.remove(best_resource)
            logger.debug("Selected known resource: title=%s episodes=%s", best_resource.resources.title, sorted(best_known_covered))
            continue
        logger.debug(
            "Lazy fetching resource candidate: title=%s seeders=%s",
            best_resource.resources.title,
            int(best_resource.resources.seeders or 0),
        )
        try:
            payload = await fetch_torrent_payload(best_resource.resources)
        except ValueError as exc:
            logger.warning("Failed to fetch resource torrent payload: title=%s error=%s", best_resource.resources.title, exc)
            candidates.remove(best_resource)
            continue
        original_best_resource = best_resource
        best_resource = _resource_with_metadata_attrs(original_best_resource, payload)
        if not match_filters(best_resource, filters, quality_profile):
            candidates.remove(original_best_resource)
            continue
        real_episodes = payload.metadata.get_episodes() or (set(needed_episodes) if not episode_mode else set())
        best_upgrade_score = compute_quality_upgrade_score(best_resource, quality_profile)
        real_covered = {
            ep
            for ep in real_episodes & needed_episodes
            if not required_scores or best_upgrade_score >= (required_scores[ep] if ep in required_scores else -10**9)
        }
        if real_covered:
            selected_items.append((best_resource, real_covered, payload))
            needed_episodes -= real_covered
            logger.debug("Selected fetched resource: title=%s episodes=%s", best_resource.resources.title, sorted(real_covered))
        else:
            logger.debug(
                "Discarded fetched resource: title=%s contained=%s needed=%s",
                best_resource.resources.title,
                sorted(real_episodes),
                sorted(needed_episodes),
            )
        candidates.remove(original_best_resource)
    selected_items.sort(key=lambda item: min(item[1]) if item[1] else 0)
    final_results: list[tuple[TorrentPayload, list[int], Resource]] = []
    for result, covered, payload in selected_items:
        try:
            payload = payload or await fetch_torrent_payload(result.resources)
            if not payload.metadata.files or not covered:
                selected_files = []
            elif not episode_mode:
                selected_files = []
            else:
                selected_files = []
                for index, file in enumerate(payload.metadata.files):
                    file_episodes = file.get_episodes()
                    if file_episodes and file_episodes & covered:
                        selected_files.append(index)
            if selected_files or not episode_mode:
                final_results.append((payload, selected_files, result))
            else:
                logger.warning("No files selected for resource: title=%s covered=%s", result.resources.title, sorted(covered))
        except ValueError as exc:
            logger.warning("Failed to finalize resource: title=%s error=%s", result.resources.title, exc)
            continue
    return final_results


async def _select_disc_package_resources(
    results: list[Resource],
    *,
    filters: ResourceFilters | None,
    quality_profile: QualityProfile | None = None,
    existing_disc_numbers: set[int] | None = None,
) -> list[tuple[TorrentPayload, list[int], Resource]]:
    candidates = sorted(
        [result for result in results if has_valid_seeders(result)],
        key=lambda result: (automatic_resource_sort_rank(result, quality_profile), compute_preference_score(result, quality_profile)[0]),
        reverse=True,
    )
    selected: list[tuple[TorrentPayload, list[int], Resource]] = []
    selected_discs: set[int] = set(existing_disc_numbers or set())
    expected_total: int | None = None
    for result in candidates:
        try:
            payload = await fetch_torrent_payload(result.resources)
        except ValueError as exc:
            logger.warning("Failed to fetch resource torrent payload: title=%s error=%s", result.resources.title, exc)
            continue
        enriched = _resource_with_metadata_attrs(result, payload)
        attrs = enriched.attrs
        if not attrs.resource_form or not match_filters(enriched, filters, quality_profile):
            continue
        if payload.metadata.coverage_kind == TorrentCoverageKind.SEASON_PACKAGE:
            return [(payload, [], enriched)]
        if payload.metadata.coverage_kind != TorrentCoverageKind.DISC_PACKAGE or attrs.disc_number is None:
            continue
        if attrs.disc_number in selected_discs:
            continue
        selected.append((payload, [], enriched))
        selected_discs.add(attrs.disc_number)
        if attrs.disc_total:
            expected_total = max(expected_total or 0, int(attrs.disc_total))
        if expected_total and len(selected_discs) >= expected_total:
            break
    return selected


def _resource_with_metadata_attrs(resource: Resource, payload: TorrentPayload) -> Resource:
    if not payload.metadata.attrs:
        return resource
    return resource.model_copy(update={"attrs": payload.metadata.attrs})
