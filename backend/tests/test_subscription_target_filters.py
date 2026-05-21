from app.schemas.domain.subscription_filters import SubscriptionFilters, UpgradePolicy
from app.services.domain.resource.filtering import has_meaningful_filter_criteria


def test_empty_or_upgrade_only_filters_are_not_meaningful_targets():
    assert has_meaningful_filter_criteria(None) is False
    assert has_meaningful_filter_criteria(SubscriptionFilters()) is False
    assert has_meaningful_filter_criteria(SubscriptionFilters(resource_kind=["video_file"])) is False
    assert has_meaningful_filter_criteria(SubscriptionFilters(upgrade_policy=UpgradePolicy(enabled=True))) is False


def test_original_disc_resource_kind_is_meaningful_target():
    assert has_meaningful_filter_criteria(SubscriptionFilters(resource_kind=["original_disc"])) is True
    assert has_meaningful_filter_criteria(SubscriptionFilters(resource_kind=["video_file", "original_disc"])) is True


def test_quality_and_keyword_filters_are_meaningful_targets():
    assert has_meaningful_filter_criteria(SubscriptionFilters(resolution=["1080p"])) is True
    assert has_meaningful_filter_criteria(SubscriptionFilters(include_keywords=["PROPER"])) is True
    assert has_meaningful_filter_criteria(SubscriptionFilters(exclude_keywords=["CAM"])) is True
    assert has_meaningful_filter_criteria(SubscriptionFilters(tags=["tag-1"])) is True


def test_audio_and_color_depth_filters_are_meaningful_targets():
    filters = SubscriptionFilters(
        audio_codec=["DTS"],
        audio_channels=["5.1"],
        color_depth=["10bit"],
    )

    assert has_meaningful_filter_criteria(filters) is True
