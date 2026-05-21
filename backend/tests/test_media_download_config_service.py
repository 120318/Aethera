from types import SimpleNamespace

import pytest

from app.schemas.domain.media_types import MediaType
from app.schemas.domain.quality_profile import QualityProfile
from app.schemas.domain.subscription_filters import SubscriptionFilters
from app.schemas.media_id import MediaID
from app.services.domain.subscription.download_config_service import SubscriptionDownloadConfigService


@pytest.mark.asyncio
async def test_effective_config_uses_selected_filter_profile_when_subscription_does_not_override(monkeypatch):
    service = SubscriptionDownloadConfigService()
    media_id = MediaID.parse("tmdb:tv:123")
    selected_filters = SubscriptionFilters()
    selected_filter = SimpleNamespace(
        id="filter-selected",
        filters=selected_filters,
        quality_profile_id="qp-selected",
        active_default=False,
    )
    default_filter = SimpleNamespace(
        id="filter-default",
        filters=SubscriptionFilters(),
        quality_profile_id="qp-default",
        active_default=True,
    )
    selected_quality_profile = QualityProfile(id="qp-selected", name="Selected")
    default_quality_profile = QualityProfile(id="qp-default", name="Default")

    async def fake_get(_media_id, _season_number=None):
        return SimpleNamespace(
                media_id=media_id,
                season_number=None,
                sub_id="sub-1",
            directory_id=None,
            filter_config_id="filter-selected",
            quality_profile_id=None,
            filters=None,
            sites=[],
            unmatched_rules=[],
        )

    monkeypatch.setattr(service, "find_by_media_id", fake_get)
    monkeypatch.setattr(
        "app.services.domain.subscription.download_config_service.settings_service.get_default_directory",
        lambda _media_type: None,
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.download_config_service.settings_service.list_filter_presets",
        lambda: [default_filter, selected_filter],
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.download_config_service.settings_service.get_filter",
        lambda filter_id: selected_filter if filter_id == "filter-selected" else (
            default_filter if filter_id == "filter-default" else None
        ),
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.download_config_service.settings_service.get_default_quality_profile",
        lambda: default_quality_profile,
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.download_config_service.settings_service.get_quality_profile",
        lambda profile_id: selected_quality_profile if profile_id == "qp-selected" else (
            default_quality_profile if profile_id == "qp-default" else None
        ),
    )

    effective = await service.resolve_effective_config(media_id, MediaType.tv)

    assert effective.filter_config_id == "filter-selected"
    assert effective.filters is selected_filters
    assert effective.quality_profile_id == "qp-selected"
    assert effective.quality_profile is selected_quality_profile


@pytest.mark.asyncio
async def test_effective_config_with_custom_filters_and_no_preset_uses_global_default_profile(monkeypatch):
    service = SubscriptionDownloadConfigService()
    media_id = MediaID.parse("tmdb:tv:456")
    custom_filters = SubscriptionFilters()
    default_filter = SimpleNamespace(
        id="filter-default",
        filters=SubscriptionFilters(),
        quality_profile_id="qp-from-default-filter",
        active_default=True,
    )
    global_default_profile = QualityProfile(id="qp-global-default", name="Global Default", active_default=True)

    async def fake_get(_media_id, _season_number=None):
        return SimpleNamespace(
                media_id=media_id,
                season_number=None,
                sub_id="sub-2",
            directory_id=None,
            filter_config_id=None,
            quality_profile_id=None,
            filters=custom_filters,
            sites=[],
            unmatched_rules=[],
        )

    monkeypatch.setattr(service, "find_by_media_id", fake_get)
    monkeypatch.setattr(
        "app.services.domain.subscription.download_config_service.settings_service.get_default_directory",
        lambda _media_type: None,
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.download_config_service.settings_service.list_filter_presets",
        lambda: [default_filter],
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.download_config_service.settings_service.get_filter",
        lambda _filter_id: None,
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.download_config_service.settings_service.get_default_quality_profile",
        lambda: global_default_profile,
    )
    monkeypatch.setattr(
        "app.services.domain.subscription.download_config_service.settings_service.get_quality_profile",
        lambda profile_id: global_default_profile if profile_id == "qp-global-default" else None,
    )

    effective = await service.resolve_effective_config(media_id, MediaType.tv)

    assert effective.filter_config_id is None
    assert effective.filters is custom_filters
    assert effective.quality_profile_id == "qp-global-default"
    assert effective.quality_profile is global_default_profile
