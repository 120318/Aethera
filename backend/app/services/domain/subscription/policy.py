from __future__ import annotations

from app.schemas.domain.quality_profile import QualityProfile
from app.schemas.domain.subscription import Subscription
from app.schemas.domain.subscription_filters import SubscriptionFilters
from app.services.config.settings_service import settings_service
from app.services.domain.resource.filtering import has_meaningful_filter_criteria, normalized_resource_kinds


def upgrade_policy_enabled(filters: SubscriptionFilters | None) -> bool:
    upgrade_policy = filters.upgrade_policy if filters and filters.upgrade_policy else None
    return bool(upgrade_policy and upgrade_policy.enabled)


def subscription_upgrade_enabled(subscription: Subscription) -> bool:
    return upgrade_policy_enabled(subscription.filters)


def has_meaningful_target_filters(filters: SubscriptionFilters | None) -> bool:
    return has_meaningful_filter_criteria(filters)


def allows_disc_package(filters: SubscriptionFilters | None) -> bool:
    return "original_disc" in normalized_resource_kinds(filters)


def allows_video_file(filters: SubscriptionFilters | None) -> bool:
    return "video_file" in normalized_resource_kinds(filters)


def resolve_quality_profile(subscription: Subscription) -> QualityProfile:
    quality_profile = settings_service.get_quality_profile(subscription.quality_profile_id) if subscription.quality_profile_id else None
    if subscription.filter_config_id:
        filter_config = settings_service.get_filter(subscription.filter_config_id)
        if not quality_profile and filter_config and filter_config.quality_profile_id:
            quality_profile = settings_service.get_quality_profile(filter_config.quality_profile_id)
    return quality_profile or settings_service.get_default_quality_profile()


def resolve_runtime_filters(subscription: Subscription) -> SubscriptionFilters | None:
    filters = subscription.filters
    if not subscription.filter_config_id:
        return filters
    filter_config = settings_service.get_filter(subscription.filter_config_id)
    preset_filters = filter_config.filters if filter_config else None
    if not preset_filters:
        return filters
    if has_meaningful_filter_criteria(filters):
        return filters
    if filters and filters.upgrade_policy:
        return preset_filters.model_copy(update={"upgrade_policy": filters.upgrade_policy})
    return preset_filters
