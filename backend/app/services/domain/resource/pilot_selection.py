from __future__ import annotations

import logging
from itertools import combinations

from app.schemas.domain.quality_profile import QualityProfile
from app.schemas.domain.resource_search import Resource
from app.schemas.domain.torrent import TorrentPayload
from app.services.domain.resource.filtering import compute_preference_score
from app.services.domain.resource.quality import RESOURCE_FORM_BLURAY_DISC, RESOURCE_FORM_DVD_DISC
from app.services.domain.resource.selection import automatic_resource_sort_rank, has_valid_seeders
from app.services.domain.resource.torrent_metadata import fetch_torrent_payload

logger = logging.getLogger("app.services.resource.pilot_selection")


async def select_pilot_resources(
    results: list[Resource],
    *,
    quality_profile: QualityProfile | None = None,
    target_episodes: set[int],
) -> list[tuple[TorrentPayload, list[int], Resource]] | None:
    candidate_items: list[tuple[Resource, set[int], int, int, TorrentPayload | None]] = []
    for result in results:
        if not has_valid_seeders(result):
            logger.debug("Pilot candidate skipped: title=%s site=%s seeders=%s reason=no_seeders", result.resources.title, result.resources.site, int(result.resources.seeders or 0))
            continue
        if result.attrs.resource_form in {RESOURCE_FORM_BLURAY_DISC, RESOURCE_FORM_DVD_DISC}:
            logger.debug("Pilot candidate skipped: title=%s reason=disc_package", result.resources.title)
            continue
        preference_score = compute_preference_score(result, quality_profile)[0]
        seeders = int(result.resources.seeders or 0)
        available_episodes = set(result.attrs.episodes or [])
        if not available_episodes:
            logger.debug(
                "Pilot candidate requires payload inspection: title=%s site=%s seeders=%s preference=%s reason=no_parsed_episodes",
                result.resources.title,
                result.resources.site,
                seeders,
                preference_score,
            )
            available_episodes = set(target_episodes)
            payload = None
        else:
            payload = None

        covered = available_episodes & target_episodes
        if not covered:
            logger.debug(
                "Pilot candidate skipped: title=%s site=%s available=%s reason=no_target_episodes",
                result.resources.title,
                result.resources.site,
                sorted(available_episodes),
            )
            continue

        logger.debug(
            "Pilot candidate matched: title=%s site=%s available=%s covered=%s preference=%s seeders=%s",
            result.resources.title,
            result.resources.site,
            sorted(available_episodes),
            sorted(covered),
            preference_score,
            seeders,
        )
        candidate_items.append((result, covered, preference_score, seeders, payload))

    if not candidate_items:
        return None

    combo_candidates: list[tuple[int, tuple, tuple[tuple[Resource, set[int], int, int, TorrentPayload | None], ...]]] = []
    max_combo_size = min(len(candidate_items), len(target_episodes))
    for combo_size in range(1, max_combo_size + 1):
        for combo in combinations(candidate_items, combo_size):
            covered_union = set().union(*(item[1] for item in combo))
            if covered_union != target_episodes:
                continue
            overlap_count = sum(len(item[1]) for item in combo) - len(target_episodes)
            combo_resource_ranks = tuple(
                sorted(
                    [
                        (
                            item[2],
                            automatic_resource_sort_rank(item[0], quality_profile),
                            len(item[1]),
                        )
                        for item in combo
                    ],
                    reverse=True,
                )
            )
            rank = (combo_resource_ranks, -len(combo))
            combo_candidates.append((overlap_count, rank, combo))

    if not combo_candidates:
        return None

    min_overlap_count = min(item[0] for item in combo_candidates)
    filtered_candidates = [item for item in combo_candidates if item[0] == min_overlap_count]
    filtered_candidates.sort(key=lambda item: item[1], reverse=True)
    for overlap_count, rank, combo in filtered_candidates:
        logger.debug(
            "Pilot resource combination candidate: overlap=%s rank=%s resources=%s",
            overlap_count,
            rank,
            [
                {
                    "title": item[0].resources.title,
                    "covered": sorted(item[1]),
                    "preference": item[2],
                    "seeders": item[3],
                }
                for item in combo
            ],
        )
        finalized_items: list[tuple[TorrentPayload, list[int], Resource, set[int]]] = []
        combo_valid = True
        for result, covered, _preference_score, _seeders, payload in sorted(combo, key=lambda item: min(item[1]) if item[1] else 0):
            finalized = await finalize_pilot_resource(result, covered, payload)
            if not finalized:
                combo_valid = False
                break
            finalized_items.append((finalized[0], finalized[1], finalized[2], covered))
        if not combo_valid:
            continue

        logger.debug(
            "Pilot resource combination selected: covered=%s resources=%s",
            sorted(target_episodes),
            [
                {
                    "title": item[2].resources.title,
                    "covered": sorted(item[3]),
                    "selected_files": item[1],
                }
                for item in finalized_items
            ],
        )
        return [(payload, selected_files, resource) for payload, selected_files, resource, _covered in finalized_items]
    return None


async def finalize_pilot_resource(
    result: Resource | None,
    covered: set[int],
    payload: TorrentPayload | None = None,
) -> tuple[TorrentPayload, list[int], Resource] | None:
    if not result or not covered:
        return None
    try:
        payload = payload or await fetch_torrent_payload(result.resources)
    except ValueError as exc:
        logger.warning("Failed to finalize pilot torrent payload: title=%s error=%s", result.resources.title, exc)
        return None

    payload_episodes = set(payload.metadata.get_episodes())
    if payload.metadata.attrs and payload.metadata.attrs.resource_form in {RESOURCE_FORM_BLURAY_DISC, RESOURCE_FORM_DVD_DISC}:
        logger.debug("Pilot payload skipped: title=%s reason=disc_package", result.resources.title)
        return None
    if payload_episodes:
        if not covered.issubset(payload_episodes):
            logger.debug(
                "Pilot payload skipped: title=%s site=%s payload_episodes=%s covered=%s reason=incomplete_target_coverage",
                result.resources.title,
                result.resources.site,
                sorted(payload_episodes),
                sorted(covered),
            )
            return None
        logger.debug(
            "Pilot payload candidate matched: title=%s site=%s payload_episodes=%s covered=%s",
            result.resources.title,
            result.resources.site,
            sorted(payload_episodes),
            sorted(covered),
        )

    selected_files = [
        index
        for index, file in enumerate(payload.metadata.files)
        if file.get_episodes() and file.get_episodes() & covered
    ]
    if selected_files:
        selected_covered = set().union(*(payload.metadata.files[index].get_episodes() or set() for index in selected_files))
        if not covered.issubset(selected_covered):
            logger.debug(
                "Pilot payload skipped: title=%s site=%s selected_covered=%s covered=%s reason=incomplete_file_coverage",
                result.resources.title,
                result.resources.site,
                sorted(selected_covered),
                sorted(covered),
            )
            return None
    if payload.metadata.files and not selected_files:
        logger.warning(
            "No files selected for pilot resource: title=%s site=%s covered=%s",
            result.resources.title,
            result.resources.site,
            sorted(covered),
        )
        return None
    logger.debug(
        "Pilot files selected: title=%s site=%s covered=%s selected_files=%s file_count=%d",
        result.resources.title,
        result.resources.site,
        sorted(covered),
        selected_files,
        len(payload.metadata.files),
    )
    return payload, selected_files, result
