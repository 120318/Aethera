from __future__ import annotations

from app.schemas.domain.download import TaskData
from app.schemas.domain.media import MediaExecutionSnapshot, MediaTarget
from app.schemas.domain.media_subscription_state import SubscriptionEndReason, UpgradeCompletionSnapshot
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.subscription import Subscription
from app.schemas.domain.subscription_filters import SubscriptionFilters
from app.schemas.domain.torrent import TorrentCoverageKind
from app.services.domain.download import download_service
from app.services.domain.library.service import library_service
from app.services.domain.subscription.policy import (
    allows_disc_package as _allows_disc_package_subscription,
    allows_video_file as _allows_video_file_subscription,
    has_meaningful_target_filters as _has_meaningful_target_filters,
    resolve_quality_profile as _resolve_quality_profile,
    upgrade_policy_enabled as _is_upgrade_enabled,
)
from app.services.domain.subscription.upgrade_baseline_service import subscription_upgrade_baseline_service
from app.schemas.runtime.subscription_lifecycle import SubscriptionCompletion
from app.services.domain.resource.filtering import (
    compute_quality_upgrade_score_from_attrs,
    is_original_disc_attrs,
    match_filters_against_attrs,
)

compute_preference_score_from_attrs = compute_quality_upgrade_score_from_attrs


async def _resolve_movie_completion_state(
    sub: Subscription,
    media: MediaExecutionSnapshot,
) -> SubscriptionEndReason | None:
    if media.media_type != MediaType.movie:
        return None

    if _is_upgrade_enabled(sub.filters):
        if not _has_meaningful_target_filters(sub.target_filters):
            return None
        quality_profile = _resolve_quality_profile(sub)
        library_files = await library_service.get_files_by_media(sub.media_id)
        for library_file in library_files:
            if match_filters_against_attrs(library_file.resource_attributes, sub.target_filters, quality_profile):
                return SubscriptionEndReason.MOVIE_TARGET_COMPLETED
        return None

    library_files = await library_service.get_files_by_media(sub.media_id)
    if sub.filters is None and library_files:
        return SubscriptionEndReason.MOVIE_LIBRARY_COMPLETED
    if any(match_filters_against_attrs(library_file.resource_attributes, sub.filters) for library_file in library_files):
        return SubscriptionEndReason.MOVIE_LIBRARY_COMPLETED

    active_tasks = await download_service.get_tasks(
        status=download_service.list_episode_coverage_statuses(),
        media_id=sub.media_id,
    )
    if any(_task_matches_subscription_filters(task, sub.filters) for task in active_tasks):
        return SubscriptionEndReason.MOVIE_DOWNLOADING_COMPLETED
    return None


async def _resolve_tv_completion_state(
    sub: Subscription,
    media: MediaExecutionSnapshot,
) -> SubscriptionEndReason | None:
    if media.media_type != MediaType.tv or media.season_number is None:
        return None

    total_upper_bound = int(media.episodes_count or 0)
    if total_upper_bound <= 0:
        return None

    aired_upper_bound = int(media.aired_episode_count or 0)
    target_episodes = set(range(1, total_upper_bound + 1))
    requires_disc = _allows_disc_package_subscription(sub.filters)
    requires_video = _allows_video_file_subscription(sub.filters)
    if requires_disc and not requires_video:
        if await _is_tv_disc_package_cycle_complete(sub, media):
            return SubscriptionEndReason.TV_COMPLETED
        return None

    if _is_upgrade_enabled(sub.filters):
        if _has_meaningful_target_filters(sub.target_filters):
            if await _is_tv_target_cycle_complete(sub, media, target_episodes):
                return SubscriptionEndReason.TV_TARGET_COMPLETED
            return None
        if aired_upper_bound <= 0:
            return None
        snapshot = await subscription_upgrade_baseline_service.resolve_snapshot(sub, media, aired_upper_bound)
        if snapshot is None:
            return None
        if await _is_tv_upgrade_cycle_complete(sub, media, snapshot):
            return SubscriptionEndReason.TV_UPGRADE_COMPLETED
        return None

    present_episodes = await library_service.get_present_episodes(sub.media_id, season=media.season_number)
    downloading_episodes = await download_service.list_active_episodes_by_media(sub.media_id, season=media.season_number)
    video_complete = target_episodes.issubset(present_episodes | downloading_episodes)
    if video_complete and (not requires_disc or await _is_tv_disc_package_cycle_complete(sub, media)):
        return SubscriptionEndReason.TV_COMPLETED
    return None


def _task_matches_subscription_filters(task: TaskData, filters: SubscriptionFilters | None) -> bool:
    if filters is None:
        return True
    metadata = task.metadata
    attrs = metadata.attrs if metadata else None
    if attrs and match_filters_against_attrs(attrs, filters):
        return True
    context_attrs = task.context.parsed_attributes if task.context else None
    return bool(context_attrs and match_filters_against_attrs(context_attrs, filters))


async def _is_tv_disc_package_cycle_complete(sub: Subscription, media: MediaExecutionSnapshot) -> bool:
    if media.season_number is None:
        return False
    quality_profile = _resolve_quality_profile(sub)
    active_tasks = await download_service.get_tasks(
        status=download_service.list_episode_coverage_statuses(),
        media_id=sub.media_id,
    )
    discs: set[int] = set()
    disc_total: int | None = None
    for task in active_tasks:
        metadata = task.metadata
        attrs = metadata.attrs if metadata else None
        if (
            not metadata
            or not attrs
            or not _attrs_match_season(attrs.seasons, media.season_number)
            or not match_filters_against_attrs(attrs, sub.filters, quality_profile)
        ):
            continue
        if metadata.coverage_kind == TorrentCoverageKind.SEASON_PACKAGE:
            return True
        if metadata.coverage_kind == TorrentCoverageKind.DISC_PACKAGE and attrs.disc_number:
            discs.add(int(attrs.disc_number))
            if attrs.disc_total:
                disc_total = max(disc_total or 0, int(attrs.disc_total))
    library_files = await library_service.get_files_by_media(sub.media_id, season=media.season_number)
    for file in library_files:
        attrs = file.resource_attributes
        if (
            not attrs
            or not _attrs_match_season(attrs.seasons, media.season_number)
            or not is_original_disc_attrs(attrs)
            or not match_filters_against_attrs(attrs, sub.filters, quality_profile)
        ):
            continue
        if not attrs.disc_number:
            return True
        discs.add(int(attrs.disc_number))
        if attrs.disc_total:
            disc_total = max(disc_total or 0, int(attrs.disc_total))
    return bool(disc_total and len(discs) >= disc_total)


def _attrs_match_season(seasons: list[int], season_number: int) -> bool:
    if not seasons:
        return False
    return season_number in seasons


def _upgrade_score(attrs, quality_profile) -> int:
    score = compute_preference_score_from_attrs(attrs, quality_profile)
    try:
        return int(score[0])
    except TypeError:
        return int(score)


async def _is_tv_upgrade_cycle_complete(
    sub: Subscription,
    media: MediaExecutionSnapshot,
    snapshot: UpgradeCompletionSnapshot,
) -> bool:
    if media.season_number is None or snapshot.season_number != media.season_number:
        return False

    if int(snapshot.baseline_episode_upper_bound or 0) <= 0:
        return False
    total_upper_bound = int(media.episodes_count or 0)
    if total_upper_bound <= 0:
        return False

    present_episodes = await library_service.get_present_episodes(sub.media_id, season=media.season_number)
    target_episodes = set(range(1, total_upper_bound + 1))
    if not target_episodes.issubset(present_episodes):
        return False

    quality_profile = _resolve_quality_profile(sub)
    episode_attributes = await library_service.get_episode_attributes(sub.media_id, season=media.season_number)
    for episode in target_episodes:
        attrs_list = episode_attributes[episode] if episode in episode_attributes else []
        if not attrs_list:
            return False
        best_score = max(
            _upgrade_score(attrs, quality_profile)
            for attrs in attrs_list
        )
        if int(best_score) < int(snapshot.baseline_score):
            return False
    return True


async def _is_tv_target_cycle_complete(
    sub: Subscription,
    media: MediaExecutionSnapshot,
    target_episodes: set[int],
) -> bool:
    if media.season_number is None or not target_episodes or not _has_meaningful_target_filters(sub.target_filters):
        return False

    present_episodes = await library_service.get_present_episodes(sub.media_id, season=media.season_number)
    if not target_episodes.issubset(present_episodes):
        return False

    quality_profile = _resolve_quality_profile(sub)
    episode_attributes = await library_service.get_episode_attributes(sub.media_id, season=media.season_number)
    for episode in target_episodes:
        attrs_list = episode_attributes[episode] if episode in episode_attributes else []
        if not attrs_list:
            return False
        if not any(match_filters_against_attrs(attrs, sub.target_filters, quality_profile) for attrs in attrs_list):
            return False
    return True


class SubscriptionCompletionChecker:
    async def resolve_movie_completion_state(self, sub: Subscription, media: MediaExecutionSnapshot):
        return await _resolve_movie_completion_state(sub, media)

    async def resolve_tv_completion_state(self, sub: Subscription, media: MediaExecutionSnapshot):
        return await _resolve_tv_completion_state(sub, media)

    async def check(self, subscription: Subscription) -> SubscriptionCompletion | None:
        if not subscription.active:
            return None
        media = subscription.media
        if media.media_type == MediaType.movie:
            reason = await self.resolve_movie_completion_state(subscription, media)
        else:
            reason = await self.resolve_tv_completion_state(subscription, media)
        if reason is None:
            return None
        return SubscriptionCompletion(
            sub_id=subscription.sub_id,
            target=MediaTarget(media_id=subscription.media_id, season_number=subscription.season_number),
            reason=reason,
            upgrade_snapshot=await subscription_upgrade_baseline_service.resolve_for_subscription(subscription),
        )


subscription_completion_checker = SubscriptionCompletionChecker()
