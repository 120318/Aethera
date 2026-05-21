from __future__ import annotations
import logging
from collections.abc import Mapping
from datetime import date
from uuid import uuid4
from app.schemas.domain.media import MediaExecutionSnapshot
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.quality_profile import QualityProfile
from app.schemas.domain.resource_attributes import ResourceAttributes
from app.schemas.domain.subscription import Subscription
from app.schemas.domain.subscription_filters import SubscriptionFilters
from app.schemas.domain.torrent import TorrentCoverageKind
from app.schemas.exception import DownloadException
from app.schemas.runtime.subscription_runtime import SubscriptionPlanningStatus, SubscriptionRunPlan, SubscriptionRunPlanningResult
from app.services.domain.download import download_service
from app.services.domain.library.service import library_service
from app.services.domain.resource.filtering import (
    compute_quality_upgrade_score_from_attrs,
    is_original_disc_attrs,
    match_filters_against_attrs,
)
from app.services.domain.resource.selection import allows_disc_package_subscription
from app.services.domain.subscription.policy import (
    has_meaningful_target_filters as _has_meaningful_target_filters,
    resolve_quality_profile as _resolve_subscription_quality_profile,
    resolve_runtime_filters as _resolve_runtime_filters,
)

logger = logging.getLogger("app.services.subscription.resource_run_plan")
compute_preference_score_from_attrs = compute_quality_upgrade_score_from_attrs


def _upgrade_score(attrs, quality_profile) -> int:
    score = compute_preference_score_from_attrs(attrs, quality_profile)
    try:
        return int(score[0])
    except TypeError:
        return int(score)


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    text = str(value)
    if len(text) < 10:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _is_future_date(value: str | None) -> bool:
    parsed = _parse_iso_date(value)
    return bool(parsed and parsed > date.today())


def _validate_runtime_subscription(subscription: Subscription) -> None:
    if subscription.active and not subscription.directory_id:
        raise DownloadException("backendErrors.subscriptionDirectoryRequired")
    if subscription.active and subscription.media_id.media_type.value == "tv" and subscription.season_number is None:
        raise DownloadException("backendErrors.subscriptionSeasonRequired")
    if subscription.active and subscription.media.media_id != subscription.media_id:
        raise DownloadException("backendErrors.subscriptionMediaSnapshotMismatch")
    if subscription.active and subscription.media.season_number != subscription.season_number:
        raise DownloadException("backendErrors.subscriptionMediaSnapshotSeasonMismatch")


async def _build_run_plan(sub: Subscription) -> SubscriptionRunPlanningResult:
    _validate_runtime_subscription(sub)
    correlation_id = str(uuid4())
    filters = _resolve_runtime_filters(sub)
    quality_profile = _resolve_subscription_quality_profile(sub)
    media = sub.media
    episode_mode = media.media_type == MediaType.tv
    total_episodes = set(range(1, media.episodes_count + 1)) if episode_mode and media.episodes_count else {1}
    invalid_reason: tuple[str, str] | None = None
    if episode_mode and not media.episodes_count:
        invalid_reason = ("backendErrors.subscriptionRunEpisodeCountMissing", "Subscription '%s(%s)': media has no episodes_count, skipping")
    elif episode_mode and media.season_number is None:
        invalid_reason = ("backendErrors.subscriptionRunSeasonMissing", "Subscription '%s(%s)': season_number is missing, skipping")
    if invalid_reason:
        logger.error(invalid_reason[1], sub.media_id, media.title)
        return SubscriptionRunPlanningResult(status=SubscriptionPlanningStatus.INVALID, message_key=invalid_reason[0], correlation_id=correlation_id)
    target_episodes, required_scores = await _compute_target_episodes(
        sub,
        media=media,
        filters=filters,
        quality_profile=quality_profile,
        total_episodes=total_episodes,
    )
    existing_disc_numbers, has_season_package = await _resolve_existing_disc_packages(
        sub,
        media,
        filters,
        quality_profile=quality_profile,
    )
    if has_season_package:
        logger.debug("Subscription disc package already downloading: media=%s sub=%s", sub.media_id, sub.sub_id)
        return SubscriptionRunPlanningResult(status=SubscriptionPlanningStatus.SATISFIED, message_key="subscriptionRunMessages.seasonPackageExists", correlation_id=correlation_id)
    if _should_skip_until_future_availability(media, target_episodes, filters):
        message_key = (
            "subscriptionRunMessages.awaitingDigitalRelease"
            if media.media_type == MediaType.movie
            else "subscriptionRunMessages.awaitingNextEpisode"
        )
        logger.debug("Subscription targets unavailable until future schedule: media=%s sub=%s", sub.media_id, sub.sub_id)
        return SubscriptionRunPlanningResult(status=SubscriptionPlanningStatus.SATISFIED, message_key=message_key, correlation_id=correlation_id)
    if not target_episodes and not allows_disc_package_subscription(filters):
        logger.debug("Subscription targets already satisfied: media=%s sub=%s", sub.media_id, sub.sub_id)
        return SubscriptionRunPlanningResult(status=SubscriptionPlanningStatus.SATISFIED, message_key="subscriptionRunMessages.targetSatisfied", correlation_id=correlation_id)
    plan = SubscriptionRunPlan(
        sub_id=sub.sub_id,
        media=media,
        season_number=media.season_number if episode_mode else None,
        correlation_id=correlation_id,
        episode_mode=episode_mode,
        sites=sub.sites,
        filters=filters,
        quality_profile=quality_profile,
        target_episodes=target_episodes,
        required_scores=required_scores,
        existing_disc_numbers=existing_disc_numbers,
    )
    return SubscriptionRunPlanningResult(status=SubscriptionPlanningStatus.READY, plan=plan, correlation_id=correlation_id)


def _should_skip_until_future_availability(
    media: MediaExecutionSnapshot,
    target_episodes: set[int],
    filters: SubscriptionFilters | None,
) -> bool:
    if media.media_type != MediaType.movie and allows_disc_package_subscription(filters):
        return False
    upgrade_policy = filters.upgrade_policy if filters and filters.upgrade_policy else None
    if media.media_type == MediaType.movie:
        if upgrade_policy and upgrade_policy.enabled:
            return False
        release_date = media.physical_release_date if allows_disc_package_subscription(filters) else media.digital_release_date
        return bool(target_episodes and _is_future_date(release_date))
    if media.media_type != MediaType.tv or not target_episodes:
        return False
    next_episode = media.next_episode_to_air
    if not next_episode or not _is_future_date(next_episode.air_date):
        return False
    aired_upper_bound = int(media.aired_episode_count or 0)
    if aired_upper_bound < 0:
        return False
    return all(int(episode) > aired_upper_bound for episode in target_episodes)


async def _resolve_existing_disc_packages(
    sub: Subscription,
    media: MediaExecutionSnapshot,
    filters: SubscriptionFilters | None,
    *,
    quality_profile: QualityProfile | None = None,
) -> tuple[set[int], bool]:
    if media.media_type != MediaType.tv or media.season_number is None or not allows_disc_package_subscription(filters):
        return set(), False
    tasks = await download_service.get_tasks(
        status=download_service.list_episode_coverage_statuses(),
        media_id=sub.media_id,
    )
    discs: set[int] = set()
    disc_total: int | None = None
    for task in tasks:
        metadata = task.metadata
        attrs = metadata.attrs if metadata else None
        if (
            not metadata
            or not attrs
            or not _attrs_match_season(attrs, media.season_number)
            or not match_filters_against_attrs(attrs, filters, quality_profile)
        ):
            continue
        if metadata.coverage_kind == TorrentCoverageKind.SEASON_PACKAGE:
            return discs, True
        if metadata.coverage_kind == TorrentCoverageKind.DISC_PACKAGE and attrs.disc_number:
            discs.add(int(attrs.disc_number))
            if attrs.disc_total:
                disc_total = max(disc_total or 0, int(attrs.disc_total))
    library_files = await library_service.get_files_by_media(sub.media_id, season=media.season_number)
    for file in library_files:
        attrs = file.resource_attributes
        if (
            not attrs
            or not _attrs_match_season(attrs, media.season_number)
            or not is_original_disc_attrs(attrs)
            or not match_filters_against_attrs(attrs, filters, quality_profile)
        ):
            continue
        if not attrs.disc_number:
            return discs, True
        discs.add(int(attrs.disc_number))
        if attrs.disc_total:
            disc_total = max(disc_total or 0, int(attrs.disc_total))
    if disc_total and len(discs) >= disc_total:
        return discs, True
    return discs, False


def _attrs_match_season(attrs: ResourceAttributes, season_number: int) -> bool:
    if not attrs.seasons:
        return False
    return season_number in attrs.seasons


async def _compute_target_episodes(
    sub: Subscription,
    *,
    media: MediaExecutionSnapshot,
    filters: SubscriptionFilters | None,
    quality_profile: QualityProfile | None = None,
    total_episodes: set[int],
) -> tuple[set[int], Mapping[int, int]]:
    active_season = media.season_number if media.media_type == MediaType.tv else None
    present_episodes = await library_service.get_present_episodes(sub.media_id, season=active_season)
    downloading_episodes = await download_service.list_active_episodes_by_media(sub.media_id, season=active_season)
    if downloading_episodes:
        logger.debug("Subscription '%s': Excluding downloading episodes: %s", sub.media_id, sorted(downloading_episodes))
    missing_episodes = total_episodes - present_episodes - downloading_episodes
    target_episodes = set(missing_episodes)
    required_scores: dict[int, int] = {}
    upgrade_policy = filters.upgrade_policy if filters and filters.upgrade_policy else None
    if not upgrade_policy or not upgrade_policy.enabled:
        return target_episodes, required_scores
    if _has_meaningful_target_filters(sub.target_filters):
        target_episodes.update(
            await _compute_target_filter_gap_episodes(
                sub,
                media=media,
                quality_profile=quality_profile,
                total_episodes=total_episodes,
                downloading_episodes=downloading_episodes,
            )
        )
        return target_episodes, required_scores
    active_season = media.season_number if media.media_type == MediaType.tv else None
    episode_attributes = await library_service.get_episode_attributes(sub.media_id, season=active_season)
    current_scores: dict[int, int] = {}
    for episode, attrs_list in episode_attributes.items():
        best_score: int | None = None
        for attrs in attrs_list:
            score = _upgrade_score(attrs, quality_profile)
            best_score = score if best_score is None else max(best_score, score)
        if best_score is not None:
            current_scores[int(episode)] = int(best_score)
    locked_score: int | None = None
    if current_scores and upgrade_policy.lock_mode != "off":
        if upgrade_policy.lock_mode == "best_existing":
            locked_score = max(current_scores.values())
        elif upgrade_policy.lock_mode == "first_download":
            locked_score = current_scores[min(current_scores)]
    if locked_score is None:
        return target_episodes, required_scores
    min_upgrade_delta = int(upgrade_policy.min_upgrade_score_delta or 0)
    for episode, current_score in current_scores.items():
        if current_score >= locked_score:
            continue
        target_episodes.add(int(episode))
        required_scores[int(episode)] = max(int(locked_score), int(current_score) + min_upgrade_delta)
    if upgrade_policy.strategy == "consistent_skip_low" and locked_score is not None:
        for episode in missing_episodes:
            required_scores[int(episode)] = int(locked_score)
    return target_episodes, required_scores
async def _compute_target_filter_gap_episodes(
    sub: Subscription,
    *,
    media: MediaExecutionSnapshot,
    quality_profile: QualityProfile | None,
    total_episodes: set[int],
    downloading_episodes: set[int],
) -> set[int]:
    if media.media_type == MediaType.movie:
        if 1 in downloading_episodes:
            return set()
        library_files = await library_service.get_files_by_media(sub.media_id)
        if any(match_filters_against_attrs(library_file.resource_attributes, sub.target_filters, quality_profile) for library_file in library_files):
            return set()
        return {1}
    if media.season_number is None:
        return set()
    episode_attributes = await library_service.get_episode_attributes(sub.media_id, season=media.season_number)
    target_filter_gaps: set[int] = set()
    for episode in total_episodes - downloading_episodes:
        attrs_list = episode_attributes[episode] if episode in episode_attributes else []
        if not attrs_list:
            continue
        if not any(match_filters_against_attrs(attrs, sub.target_filters, quality_profile) for attrs in attrs_list):
            target_filter_gaps.add(int(episode))
    return target_filter_gaps
class ResourceRunPlanService:
    def validate_runtime_subscription(self, subscription: Subscription) -> None:
        _validate_runtime_subscription(subscription)

    async def build_subscription_plan(self, subscription: Subscription) -> SubscriptionRunPlanningResult:
        return await _build_run_plan(subscription)

resource_run_plan_service = ResourceRunPlanService()
