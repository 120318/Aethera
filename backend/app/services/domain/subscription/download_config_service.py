from __future__ import annotations

from app.schemas.config import DirectoryConfig
from app.schemas.domain.filter_config import FilterConfig
from app.schemas.domain.media import MediaTarget
from app.schemas.domain.media_download_config import (
    EffectiveMediaDownloadConfig,
    MediaDownloadConfig,
    MediaDownloadConfigPatch,
)
from app.schemas.domain.media_subscription_state import default_subscription_mode_for_media
from app.schemas.domain.media_types import MediaType
from app.schemas.media_id import MediaID
from app.schemas.runtime.subscription_lifecycle import SubscriptionMutation
from app.services.config.settings_service import settings_service
from app.services.domain.subscription.store import SubscriptionStore, subscription_store


class SubscriptionDownloadConfigService:
    def __init__(self, store: SubscriptionStore | None = None) -> None:
        self.store = store or subscription_store

    async def find_by_media_id(self, media_id: MediaID, season_number: int | None = None) -> MediaDownloadConfig | None:
        settings = (await self.store.load_current(MediaTarget(media_id=media_id, season_number=season_number))).settings
        if not settings:
            return None
        return MediaDownloadConfig(
            sub_id=settings.sub_id,
            media_id=media_id,
            season_number=settings.season_number,
            directory_id=settings.directory_id,
            filter_config_id=settings.filter_config_id,
            quality_profile_id=settings.quality_profile_id,
            filters=settings.filters,
            sites=settings.sites,
            unmatched_rules=list(settings.unmatched_rules),
            created_at=settings.created_at,
            updated_at=settings.updated_at,
        )

    async def get_by_sub_id(self, sub_id: str) -> MediaDownloadConfig | None:
        aggregate = await self.store.load_by_sub_id(sub_id)
        settings = aggregate.settings if aggregate else None
        if not settings:
            return None
        return MediaDownloadConfig(
            sub_id=settings.sub_id,
            media_id=settings.media_id,
            season_number=settings.season_number,
            directory_id=settings.directory_id,
            filter_config_id=settings.filter_config_id,
            quality_profile_id=settings.quality_profile_id,
            filters=settings.filters,
            sites=settings.sites,
            unmatched_rules=list(settings.unmatched_rules),
            created_at=settings.created_at,
            updated_at=settings.updated_at,
        )

    async def upsert(
        self,
        *,
        media_id: MediaID,
        season_number: int | None = None,
        sub_id: str | None = None,
        directory_id=None,
        filter_config_id=None,
        quality_profile_id=None,
        filters=None,
        sites=None,
        unmatched_rules=None,
    ) -> MediaDownloadConfig:
        aggregate = await self.store.load_current(MediaTarget(media_id=media_id, season_number=season_number))
        state = aggregate.state
        settings = aggregate.settings
        next_aggregate = await self.store.save_subscription(
            SubscriptionMutation(
                target=aggregate.target,
                sub_id=sub_id or (state.sub_id if state else None),
                media=state.media if state else None,
                active=bool(state.active) if state else False,
                followed=bool(state.followed) if state else False,
                subscription_mode=state.subscription_mode if state else default_subscription_mode_for_media(media_id),
                upgrade_policy=state.upgrade_policy if state else None,
                target_filters=state.target_filters if state else None,
                target_filter_config_id=state.target_filter_config_id if state else None,
                directory_id=directory_id,
                filter_config_id=filter_config_id,
                quality_profile_id=quality_profile_id,
                filters=filters,
                sites=sites,
                unmatched_rules=list(unmatched_rules or []),
                follow_reminded_air_date=settings.follow_reminded_air_date if settings else None,
                follow_reminded_digital_release_date=settings.follow_reminded_digital_release_date if settings else None,
                follow_reminded_physical_release_date=settings.follow_reminded_physical_release_date if settings else None,
                follow_reminded_at=settings.follow_reminded_at if settings else None,
                follow_reminded_digital_release_at=settings.follow_reminded_digital_release_at if settings else None,
                follow_reminded_physical_release_at=settings.follow_reminded_physical_release_at if settings else None,
            )
        )
        settings = next_aggregate.settings
        if settings is None:
            raise RuntimeError("download config mutation did not produce settings")
        return MediaDownloadConfig(
            sub_id=settings.sub_id,
            media_id=settings.media_id,
            season_number=settings.season_number,
            directory_id=settings.directory_id,
            filter_config_id=settings.filter_config_id,
            quality_profile_id=settings.quality_profile_id,
            filters=settings.filters,
            sites=settings.sites,
            unmatched_rules=list(settings.unmatched_rules),
            created_at=settings.created_at,
            updated_at=settings.updated_at,
        )

    async def patch(
        self,
        media_id: MediaID,
        patch: MediaDownloadConfigPatch,
        *,
        sub_id: str | None = None,
        season_number: int | None = None,
    ) -> MediaDownloadConfig:
        existing = await self.find_by_media_id(media_id, season_number)
        return await self.upsert(
            media_id=media_id,
            season_number=season_number,
            sub_id=sub_id or (existing.sub_id if existing else None),
            directory_id=patch.directory_id if "directory_id" in patch.model_fields_set else (existing.directory_id if existing else None),
            filter_config_id=patch.filter_config_id if "filter_config_id" in patch.model_fields_set else (existing.filter_config_id if existing else None),
            quality_profile_id=patch.quality_profile_id if "quality_profile_id" in patch.model_fields_set else (existing.quality_profile_id if existing else None),
            filters=patch.filters if "filters" in patch.model_fields_set else (existing.filters if existing else None),
            sites=patch.sites if "sites" in patch.model_fields_set else (existing.sites if existing else None),
            unmatched_rules=patch.unmatched_rules if "unmatched_rules" in patch.model_fields_set else (existing.unmatched_rules if existing else []),
        )

    async def delete(self, media_id: MediaID, season_number: int | None = None) -> bool:
        existing = await self.find_by_media_id(media_id, season_number)
        if not existing:
            return False
        await self.upsert(
            media_id=media_id,
            season_number=season_number,
            directory_id=None,
            filter_config_id=None,
            quality_profile_id=None,
            filters=None,
            sites=None,
            unmatched_rules=[],
        )
        return True

    async def resolve_effective_config(
        self,
        media_id: MediaID,
        media_type: MediaType,
        *,
        season_number: int | None = None,
    ) -> EffectiveMediaDownloadConfig:
        existing = await self.find_by_media_id(media_id, season_number)
        default_directory = self.get_default_directory(media_type)
        default_filter = self.get_default_filter_preset()
        default_quality_profile = self.get_default_quality_profile()
        use_default_filter = not bool(existing and (existing.filter_config_id or existing.filters))

        directory_id = existing.directory_id if existing and existing.directory_id else (default_directory.id if default_directory else None)
        filter_config_id = existing.filter_config_id if existing and existing.filter_config_id else (
            default_filter.id if use_default_filter and default_filter else None
        )
        filter_config = settings_service.get_filter(filter_config_id) if filter_config_id else None
        filters = existing.filters if existing and existing.filters else (filter_config.filters if filter_config else None)
        quality_profile_id = existing.quality_profile_id if existing and existing.quality_profile_id else (
            filter_config.quality_profile_id if filter_config and filter_config.quality_profile_id else (
                default_quality_profile.id if default_quality_profile else None
            )
        )
        quality_profile = settings_service.get_quality_profile(quality_profile_id) if quality_profile_id else default_quality_profile

        return EffectiveMediaDownloadConfig(
            media_id=media_id,
            season_number=existing.season_number if existing else (season_number if media_type == MediaType.tv else None),
            sub_id=existing.sub_id if existing else None,
            directory_id=directory_id,
            filter_config_id=filter_config_id,
            quality_profile_id=quality_profile.id if quality_profile else quality_profile_id,
            filters=filters,
            has_custom_filter_override=bool(existing and existing.filters),
            sites=existing.sites if existing else None,
            quality_profile=quality_profile,
            unmatched_rules=list(existing.unmatched_rules) if existing else [],
            is_default_directory=not bool(existing and existing.directory_id) and bool(default_directory),
            is_default_filter=not bool(existing and (existing.filter_config_id or existing.filters)) and bool(default_filter),
            is_default_quality_profile=not bool(existing and existing.quality_profile_id) and bool(quality_profile),
        )

    @staticmethod
    def get_default_filter_preset() -> FilterConfig | None:
        return next((item for item in settings_service.list_filter_presets() if item.active_default), None)

    @staticmethod
    def get_default_quality_profile():
        return settings_service.get_default_quality_profile()

    @staticmethod
    def get_default_directory(media_type: MediaType) -> DirectoryConfig | None:
        return settings_service.get_default_directory(media_type)

    @staticmethod
    def get_typed_directories(media_type: MediaType) -> list[DirectoryConfig]:
        return [
            item for item in settings_service.list_directories()
            if item.enabled and item.media_type == media_type
        ]


subscription_download_config_service = SubscriptionDownloadConfigService()
