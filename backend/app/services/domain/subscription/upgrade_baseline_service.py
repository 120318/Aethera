from __future__ import annotations

import json

from app.schemas.domain.media import MediaExecutionSnapshot, MediaTarget
from app.schemas.domain.media_subscription_state import UpgradeCompletionSnapshot
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.subscription import Subscription
from app.services.domain.library.service import library_service
from app.services.domain.resource.filtering import compute_quality_upgrade_score_from_attrs
from app.services.domain.subscription.policy import (
    has_meaningful_target_filters,
    resolve_quality_profile as _resolve_quality_profile,
    subscription_upgrade_enabled as _is_upgrade_enabled,
)
from app.services.domain.subscription.query_service import subscription_query_service

compute_preference_score_from_attrs = compute_quality_upgrade_score_from_attrs


def _compute_config_fingerprint(subscription: Subscription) -> str:
    upgrade_policy = subscription.filters.upgrade_policy if subscription.filters and subscription.filters.upgrade_policy else None
    payload = {
        "filter_config_id": subscription.filter_config_id,
        "quality_profile_id": subscription.quality_profile_id,
        "directory_id": subscription.directory_id,
        "sites": subscription.sites or [],
        "filters": subscription.filters.model_dump(mode="json") if subscription.filters else None,
        "target_filters": subscription.target_filters.model_dump(mode="json") if subscription.target_filters else None,
        "upgrade_policy": upgrade_policy.model_dump(mode="json") if upgrade_policy else None,
        "unmatched_rules": [rule.model_dump(mode="json") for rule in subscription.unmatched_rules],
    }
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _resolve_baseline_score(subscription: Subscription, episode_scores: dict[int, int]) -> int | None:
    if not episode_scores:
        return None
    upgrade_policy = subscription.filters.upgrade_policy if subscription.filters and subscription.filters.upgrade_policy else None
    lock_mode = upgrade_policy.lock_mode if upgrade_policy else "best_existing"
    if lock_mode == "off":
        return 0
    if lock_mode == "first_download":
        return int(episode_scores[min(episode_scores)])
    return max(int(score) for score in episode_scores.values())


def _upgrade_score(attrs, quality_profile) -> int:
    score = compute_preference_score_from_attrs(attrs, quality_profile)
    try:
        return int(score[0])
    except TypeError:
        return int(score)


async def _resolve_snapshot(
    subscription: Subscription,
    media: MediaExecutionSnapshot,
    aired_upper_bound: int,
) -> UpgradeCompletionSnapshot | None:
    target = MediaTarget(media_id=subscription.media_id, season_number=media.season_number)
    state = await subscription_query_service.get_state(target)
    if not state or media.season_number is None:
        return None

    existing_snapshot = state.upgrade_completion_snapshot
    current_fingerprint = _compute_config_fingerprint(subscription)
    if (
        existing_snapshot
        and existing_snapshot.season_number == media.season_number
        and (
            existing_snapshot.config_fingerprint is None
            or existing_snapshot.config_fingerprint == current_fingerprint
        )
    ):
        return existing_snapshot

    quality_profile = _resolve_quality_profile(subscription)
    episode_attributes = await library_service.get_episode_attributes(subscription.media_id, season=media.season_number)
    current_scores: dict[int, int] = {}
    for episode in range(1, aired_upper_bound + 1):
        attrs_list = episode_attributes[episode] if episode in episode_attributes else []
        if not attrs_list:
            continue
        best_score = max(
            _upgrade_score(attrs, quality_profile)
            for attrs in attrs_list
        )
        current_scores[int(episode)] = int(best_score)

    baseline_score = _resolve_baseline_score(subscription, current_scores)
    if baseline_score is None:
        return None
    return UpgradeCompletionSnapshot(
        season_number=media.season_number,
        baseline_score=baseline_score,
        baseline_episode_upper_bound=aired_upper_bound,
        config_fingerprint=current_fingerprint,
    )


class SubscriptionUpgradeBaselineService:
    def compute_config_fingerprint(self, subscription: Subscription) -> str:
        return _compute_config_fingerprint(subscription)

    async def resolve_snapshot(
        self,
        subscription: Subscription,
        media: MediaExecutionSnapshot,
        aired_upper_bound: int,
    ) -> UpgradeCompletionSnapshot | None:
        return await _resolve_snapshot(subscription, media, aired_upper_bound)

    async def resolve_for_subscription(self, subscription: Subscription) -> UpgradeCompletionSnapshot | None:
        media = subscription.media
        aired_upper_bound = int(media.aired_episode_count or 0)
        if (
            not subscription.active
            or media.media_type != MediaType.tv
            or media.season_number is None
            or aired_upper_bound <= 0
            or not _is_upgrade_enabled(subscription)
            or has_meaningful_target_filters(subscription.target_filters)
        ):
            return None
        return await self.resolve_snapshot(subscription, media, aired_upper_bound)


subscription_upgrade_baseline_service = SubscriptionUpgradeBaselineService()
