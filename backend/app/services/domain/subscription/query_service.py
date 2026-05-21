from __future__ import annotations

from app.schemas.domain.media import MediaTarget
from app.schemas.domain.media_download_config import MediaDownloadConfig
from app.schemas.domain.media_download_config import EffectiveMediaDownloadConfig
from app.schemas.domain.media_subscription_state import MediaSubscriptionStateView
from app.schemas.domain.media_subscription_state import MediaSubscriptionState
from app.schemas.domain.subscription import Subscription
from app.schemas.domain.subscription_filters import SubscriptionFilters
from app.schemas.exception import DownloadException
from app.schemas.media_id import MediaID
from app.schemas.runtime.media_management import MediaMonitorState
from app.services.config.settings_service import settings_service
from app.services.domain.subscription.download_config_service import subscription_download_config_service
from app.services.domain.resource.filtering import has_meaningful_filter_criteria
from app.services.domain.subscription.store import SubscriptionStore, subscription_store


class SubscriptionQueryService:
    def __init__(self, store: SubscriptionStore | None = None) -> None:
        self.store = store or subscription_store

    @staticmethod
    def _target_filter_override_payload(filters: SubscriptionFilters | None):
        if not has_meaningful_filter_criteria(filters):
            return {}
        payload = {}
        if filters.resolution:
            payload["resolution"] = filters.resolution
        if filters.source:
            payload["source"] = filters.source
        if filters.codec:
            payload["codec"] = filters.codec
        if filters.hdr_type:
            payload["hdr_type"] = filters.hdr_type
        if filters.audio_codec:
            payload["audio_codec"] = filters.audio_codec
        if filters.audio_channels:
            payload["audio_channels"] = filters.audio_channels
        if filters.color_depth:
            payload["color_depth"] = filters.color_depth
        if filters.include_keywords:
            payload["include_keywords"] = filters.include_keywords
        if filters.exclude_keywords:
            payload["exclude_keywords"] = filters.exclude_keywords
        if filters.tags:
            payload["tags"] = filters.tags
        return payload

    @classmethod
    def _resolve_runtime_target_filters(cls, state) -> SubscriptionFilters | None:
        preset_filters = None
        if state.target_filter_config_id:
            target_filter_config = settings_service.get_filter(state.target_filter_config_id)
            if target_filter_config and target_filter_config.filters:
                preset_filters = target_filter_config.filters.model_copy()

        override_payload = cls._target_filter_override_payload(state.target_filters)
        if preset_filters and override_payload:
            return preset_filters.model_copy(update=override_payload)
        if preset_filters:
            return preset_filters
        if override_payload:
            return state.target_filters.model_copy()
        return None

    @classmethod
    def compose_runtime_subscription(cls, state, config: EffectiveMediaDownloadConfig) -> Subscription:
        if state.media is None:
            raise DownloadException("backendErrors.mediaExecutionSnapshotRequired")
        filters = config.filters.model_copy() if config.filters else None
        target_filters = cls._resolve_runtime_target_filters(state)
        if state.upgrade_policy:
            filters = filters.model_copy(update={"upgrade_policy": state.upgrade_policy}) if filters else SubscriptionFilters(
                upgrade_policy=state.upgrade_policy,
            )
        return Subscription(
            sub_id=state.sub_id,
            media_id=state.media_id,
            media=state.media,
            season_number=state.season_number,
            sites=config.sites,
            filters=filters,
            target_filters=target_filters,
            target_filter_config_id=state.target_filter_config_id,
            filter_config_id=config.filter_config_id,
            quality_profile_id=config.quality_profile_id,
            directory_id=config.directory_id,
            followed=state.followed,
            active=state.active,
            created_at=state.created_at,
            last_run_at=state.last_run_at,
            follow_reminded_air_date=state.follow_reminded_air_date,
            follow_reminded_digital_release_date=state.follow_reminded_digital_release_date,
            follow_reminded_physical_release_date=state.follow_reminded_physical_release_date,
            follow_reminded_at=state.follow_reminded_at,
            follow_reminded_digital_release_at=state.follow_reminded_digital_release_at,
            follow_reminded_physical_release_at=state.follow_reminded_physical_release_at,
            unmatched_rules=list(config.unmatched_rules),
            warnings=list(state.warnings),
        )

    async def get_current(self, target: MediaTarget) -> MediaSubscriptionStateView:
        aggregate = await self.store.load_current(target)
        return aggregate.view

    async def get_current_state_and_view(
        self,
        target: MediaTarget,
    ) -> tuple[MediaSubscriptionState | None, MediaSubscriptionStateView]:
        aggregate = await self.store.load_current(target)
        return aggregate.state, aggregate.view

    async def get_current_state_view_and_config(
        self,
        target: MediaTarget,
    ) -> tuple[MediaSubscriptionState | None, MediaSubscriptionStateView, MediaDownloadConfig | None]:
        aggregate = await self.store.load_current(target)
        settings = aggregate.settings
        config = (
            MediaDownloadConfig(
                sub_id=settings.sub_id,
                media_id=target.media_id,
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
            if settings
            else None
        )
        return aggregate.state, aggregate.view, config

    async def get_state(self, target: MediaTarget) -> MediaSubscriptionState | None:
        aggregate = await self.store.load_current(target)
        return aggregate.state

    async def get_state_by_sub_id(self, sub_id: str) -> MediaSubscriptionState | None:
        aggregate = await self.store.load_by_sub_id(sub_id)
        if not aggregate:
            return None
        return aggregate.state

    async def get_by_target(self, target: MediaTarget) -> Subscription | None:
        aggregate = await self.store.load_current(target)
        if not aggregate.state or not aggregate.state.active:
            return None
        config = await subscription_download_config_service.resolve_effective_config(
            target.media_id,
            target.media_id.media_type,
            season_number=target.season_number,
        )
        return self.compose_runtime_subscription(aggregate.state, config)

    async def get_by_sub_id(self, sub_id: str) -> Subscription | None:
        aggregate = await self.store.load_by_sub_id(sub_id)
        if not aggregate or not aggregate.state or not aggregate.state.active:
            return None
        config = await subscription_download_config_service.resolve_effective_config(
            aggregate.target.media_id,
            aggregate.target.media_id.media_type,
            season_number=aggregate.target.season_number,
        )
        return self.compose_runtime_subscription(aggregate.state, config)

    async def list_all(self) -> list[MediaSubscriptionStateView]:
        return [aggregate.view for aggregate in await self.store.list_all()]

    async def list_states(self) -> list[MediaSubscriptionState]:
        return [aggregate.state for aggregate in await self.store.list_all() if aggregate.state is not None]

    async def list_active(self) -> list[Subscription]:
        subscriptions: list[Subscription] = []
        for aggregate in await self.store.list_active():
            if not aggregate.state or not aggregate.state.active:
                continue
            config = await subscription_download_config_service.resolve_effective_config(
                aggregate.target.media_id,
                aggregate.target.media_id.media_type,
                season_number=aggregate.target.season_number,
            )
            subscriptions.append(self.compose_runtime_subscription(aggregate.state, config))
        return subscriptions

    async def find_current_monitors_by_media_ids(self, media_ids: list[MediaID]) -> dict[str, MediaMonitorState]:
        return await self.store.find_current_monitors_by_media_ids(media_ids)


subscription_query_service = SubscriptionQueryService()
