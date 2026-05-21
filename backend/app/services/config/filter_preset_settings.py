from __future__ import annotations

import uuid

from app.db.repositories.settings_sqlite_repository import SettingsSqliteRepository
from app.schemas.domain.filter_config import FilterConfig
from app.schemas.domain.quality_values import HdrTypeValue, ResolutionValue
from app.schemas.domain.subscription_filters import SubscriptionFilters
from app.services.config.quality_profile_settings import QualityProfileSettings


DEFAULT_FILTER_DOLBY_VISION_ID = "builtin-filter-dolby-vision"
DEFAULT_FILTER_HDR_ID = "builtin-filter-hdr"
DEFAULT_FILTER_4K_ID = "builtin-filter-4k"
DEFAULT_FILTER_1080P_ID = "builtin-filter-1080p"


class FilterPresetSettings:
    def __init__(self, repo: SettingsSqliteRepository, quality_profiles: QualityProfileSettings) -> None:
        self._repo = repo
        self._quality_profiles = quality_profiles

    def list(self) -> list[FilterConfig]:
        return self._repo.filter_presets.list()

    def replace_all(self, filters: list[FilterConfig]) -> None:
        self._repo.filter_presets.replace(filters)

    def find(self, filter_id: str) -> FilterConfig | None:
        return next((filter_config for filter_config in self.list() if filter_config.id == filter_id), None)

    def create(
        self,
        name: str,
        filters: SubscriptionFilters,
        quality_profile_id: str | None = None,
        active_default: bool = False,
    ) -> FilterConfig:
        filter_presets = self.list()
        filter_config = FilterConfig(
            id=str(uuid.uuid4()),
            name=name,
            is_default=False,
            active_default=active_default,
            quality_profile_id=quality_profile_id or self._quality_profiles.get_default_id(),
            filters=filters,
        )
        filter_presets.append(filter_config)
        self.replace_all(filter_presets)
        return filter_config

    def update(
        self,
        filter_id: str,
        name: str | None = None,
        filters: SubscriptionFilters | None = None,
        quality_profile_id: str | None = None,
        active_default: bool | None = None,
    ) -> FilterConfig | None:
        filter_presets = self.list()
        for index, filter_config in enumerate(filter_presets):
            if filter_config.id != filter_id:
                continue
            updated = filter_config.model_copy(
                update={
                    "name": name if name is not None else filter_config.name,
                    "filters": filters if filters is not None else filter_config.filters,
                    "quality_profile_id": quality_profile_id if quality_profile_id is not None else filter_config.quality_profile_id,
                    "active_default": active_default if active_default is not None else filter_config.active_default,
                }
            )
            filter_presets[index] = updated
            self.replace_all(filter_presets)
            return updated
        return None

    def delete(self, filter_id: str) -> bool:
        filter_presets = self.list()
        next_filters = [item for item in filter_presets if item.id != filter_id]
        if len(next_filters) == len(filter_presets):
            return False
        self.replace_all(next_filters)
        return True

    def ensure_defaults(self) -> None:
        if self.list():
            return
        default_quality_profile_id = self._quality_profiles.get_default_id()
        self.replace_all(
            [
                FilterConfig(
                    id=DEFAULT_FILTER_DOLBY_VISION_ID,
                    name="Dolby Vision",
                    is_default=False,
                    active_default=False,
                    quality_profile_id=default_quality_profile_id,
                    filters=SubscriptionFilters(hdr_type=[HdrTypeValue.DOLBY_VISION]),
                ),
                FilterConfig(
                    id=DEFAULT_FILTER_HDR_ID,
                    name="HDR",
                    is_default=False,
                    active_default=False,
                    quality_profile_id=default_quality_profile_id,
                    filters=SubscriptionFilters(hdr_type=[HdrTypeValue.HDR10, HdrTypeValue.HDR10_PLUS]),
                ),
                FilterConfig(
                    id=DEFAULT_FILTER_4K_ID,
                    name="4K",
                    is_default=False,
                    active_default=True,
                    quality_profile_id=default_quality_profile_id,
                    filters=SubscriptionFilters(resolution=[ResolutionValue.UHD_2160P]),
                ),
                FilterConfig(
                    id=DEFAULT_FILTER_1080P_ID,
                    name="1080p",
                    is_default=False,
                    active_default=False,
                    quality_profile_id=default_quality_profile_id,
                    filters=SubscriptionFilters(resolution=[ResolutionValue.FHD_1080P]),
                ),
            ]
        )
