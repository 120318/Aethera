from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.schemas.config import DirectoryConfig
from app.schemas.domain.command import CommandRecord, CommandType
from app.schemas.domain.filter_config import FilterConfig
from app.schemas.domain.media_download_config import EffectiveMediaDownloadConfig, MediaDownloadConfig
from app.schemas.domain.media import MediaFullInfo, MediaTarget
from app.schemas.domain.schedule import MediaScheduleSummary
from app.schemas.domain.media_subscription_state import (
    MediaSubscriptionState,
    SubscriptionMode,
    resolve_subscription_mode,
)
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.quality_profile import QualityProfile
from app.schemas.domain.resource_search import Resource
from app.schemas.domain.subscription_filters import SubscriptionFilters
from app.schemas.exception import InvalidRequestException, MediaNotFoundException
from app.schemas.media_id import MediaID
from app.schemas.runtime.media_detail_overview import (
    MediaDetailActionReadinessItem,
    MediaDetailActionReadinessSummary,
    MediaDetailConfigValueSummary,
    MediaDetailCurrentConfigSummary,
    MediaDetailCustomRulesSummary,
    MediaDetailOverviewCatalogs,
    MediaDetailOverviewResponse,
    MediaDetailOverviewSummary,
    MediaDetailResourceDiscoverySummary,
    MediaDetailSubscriptionSummary,
)
from app.schemas.runtime.library_overview import LibraryOverviewSnapshot
from app.services.application.commands.service import command_service
from app.services.application.views.library import library_overview_service
from app.services.config.settings_service import settings_service
from app.services.domain.library.service import MediaLibrarySnapshot
from app.services.domain.subscription.download_config_service import subscription_download_config_service
from app.services.domain.media import media_service
from app.services.domain.subscription.query_service import subscription_query_service
from app.services.application.workflows.resource_search import resource_search_service
from app.services.domain.resource.parser import resource_parser
from app.services.domain.resource.filtering import matches_unmatched_rules
from app.services.application.views.media_detail_overview.schedule import MediaDetailOverviewScheduleMixin


@dataclass(frozen=True)
class _DetailOverviewSettingsSnapshot:
    filters: list[FilterConfig]
    quality_profiles: list[QualityProfile]
    directories: list[DirectoryConfig]
    indexers_enabled: bool
    enabled_downloaders: set[str]
    default_downloader_id: str | None
    has_default_template: bool
    enabled_directories: list[DirectoryConfig]
    default_directory: DirectoryConfig | None
    default_filter: FilterConfig | None


class MediaDetailOverviewService(MediaDetailOverviewScheduleMixin):
    async def get_overview(self, media_id: MediaID, *, season_number: int | None = None) -> MediaDetailOverviewResponse:
        if media_id.media_type == MediaType.tv and (season_number is None or season_number <= 0):
            raise InvalidRequestException("backendErrors.seasonRequired")
        media = await media_service.info(media_id, season_number=season_number)
        if not media:
            raise MediaNotFoundException()
        media = media_service.apply_season_context(media, season_number)
        return await self.get_overview_for_media(media, season_number=season_number)

    async def get_overview_for_media(
        self,
        media: MediaFullInfo,
        *,
        season_number: int | None = None,
        subscription_state: MediaSubscriptionState | None = None,
        subscription_state_loaded: bool = False,
        download_config: MediaDownloadConfig | None = None,
        download_config_loaded: bool = False,
        active_commands: list[CommandRecord] | None = None,
        active_commands_loaded: bool = False,
        library_snapshot: MediaLibrarySnapshot | None = None,
    ) -> MediaDetailOverviewResponse:
        media_id = media.media_id
        media = media_service.apply_season_context(media, season_number)
        settings_snapshot = self._build_settings_snapshot(media.media_type)

        schedule_task = asyncio.create_task(self._resolve_schedule_summary(media))

        state_result, config_result, commands_result, _schedule, local_resources = await asyncio.gather(
            self._resolve_subscription_state(
                media_id,
                media.season_number,
                loaded=subscription_state_loaded,
                value=subscription_state,
            ),
            self._resolve_download_config(
                media_id,
                media.season_number,
                loaded=download_config_loaded,
                value=download_config,
            ),
            self._resolve_active_commands(
                media_id,
                media.season_number,
                loaded=active_commands_loaded,
                value=active_commands,
            ),
            schedule_task,
            self._build_local_resources(media_id, media, schedule_task, library_snapshot=library_snapshot),
        )
        state = state_result
        raw_config = config_result
        active_commands = commands_result or []
        effective_config = self._resolve_effective_config(media_id, raw_config, settings_snapshot, media.season_number)
        search_running = any(
            command.type == CommandType.RESOURCE_SEARCH and command.status.value in {"queued", "running"}
            for command in active_commands
        )

        summary = MediaDetailOverviewSummary(
            subscription=MediaDetailSubscriptionSummary(
                subscribed=bool(state.active) if state else False,
                followed=bool(state.followed) if state else False,
                subscription_mode=self._resolve_subscription_mode_label(state, media.media_type),
            ),
            resource_discovery=self._resolve_resource_discovery_summary(
                media_id,
                effective_config,
                search_running,
                media.season_number,
            ),
            download_config=MediaDetailCurrentConfigSummary(
                directory=self._resolve_directory_summary(effective_config, settings_snapshot),
                filter=self._resolve_filter_summary(effective_config, settings_snapshot),
                quality_profile=self._resolve_quality_profile_summary(effective_config, settings_snapshot),
                custom_rules=self._resolve_custom_rules_summary(effective_config),
            ),
            local_resources=local_resources,
            action_readiness=self._resolve_action_readiness(media.media_type, settings_snapshot),
        )

        return MediaDetailOverviewResponse(
            media_id=media_id,
            summary=summary,
            catalogs=MediaDetailOverviewCatalogs(
                filters=settings_snapshot.filters,
                quality_profiles=settings_snapshot.quality_profiles,
                directories=settings_snapshot.directories,
            ),
        )

    async def _resolve_subscription_state(
        self,
        media_id: MediaID,
        season_number: int | None,
        *,
        loaded: bool,
        value: MediaSubscriptionState | None,
    ) -> MediaSubscriptionState | None:
        if loaded:
            return value
        return await subscription_query_service.get_state(MediaTarget(media_id=media_id, season_number=season_number))

    async def _resolve_download_config(
        self,
        media_id: MediaID,
        season_number: int | None,
        *,
        loaded: bool,
        value: MediaDownloadConfig | None,
    ) -> MediaDownloadConfig | None:
        if loaded:
            return value
        return await subscription_download_config_service.find_by_media_id(media_id, season_number)

    async def _resolve_active_commands(
        self,
        media_id: MediaID,
        season_number: int | None,
        *,
        loaded: bool,
        value: list[CommandRecord] | None,
    ) -> list[CommandRecord]:
        if loaded:
            return value or []
        return await command_service.list_media_active_commands(media_id, season_number=season_number)

    async def _build_local_resources(
        self,
        media_id: MediaID,
        media: MediaFullInfo,
        schedule_task: asyncio.Task[MediaScheduleSummary],
        *,
        library_snapshot: MediaLibrarySnapshot | None = None,
    ) -> LibraryOverviewSnapshot:
        schedule = await schedule_task
        return await library_overview_service.build_snapshot(
            media_id,
            media,
            schedule=schedule,
            library_snapshot=library_snapshot,
        )

    def _has_meaningful_filters(self, filters: SubscriptionFilters | None) -> bool:
        if not filters:
            return False
        list_fields = [
            filters.resolution,
            filters.source,
            filters.resource_form,
            filters.codec,
            filters.hdr_type,
            filters.audio_codec,
            filters.audio_channels,
            filters.color_depth,
            filters.include_keywords,
            filters.exclude_keywords,
            filters.tags,
        ]
        if any(items for items in list_fields):
            return True
        return bool(filters.upgrade_policy and filters.upgrade_policy.enabled)

    def _resolve_subscription_mode_label(
        self,
        state: MediaSubscriptionState | None,
        media_type: MediaType,
    ) -> SubscriptionMode:
        if state:
            return resolve_subscription_mode(state.media_id, state.upgrade_policy)
        if media_type == MediaType.movie:
            return SubscriptionMode.FIRST_RELEASE
        return SubscriptionMode.CURRENT_AIRED_COMPLETE

    def _resolve_directory_summary(
        self,
        config: EffectiveMediaDownloadConfig,
        snapshot: _DetailOverviewSettingsSnapshot,
    ) -> MediaDetailConfigValueSummary:
        current = next((item for item in snapshot.directories if item.id == config.directory_id), None)
        if current:
            return MediaDetailConfigValueSummary(
                id=current.id,
                name=current.name or current.path or "Unnamed directory",
                is_default=bool(current.is_default),
            )

        if snapshot.default_directory:
            return MediaDetailConfigValueSummary(
                id=snapshot.default_directory.id,
                name=snapshot.default_directory.name or snapshot.default_directory.path or "Unnamed directory",
                is_default=True,
            )

        return MediaDetailConfigValueSummary(name_key="common.notSet")

    def _resolve_filter_summary(
        self,
        config: EffectiveMediaDownloadConfig,
        snapshot: _DetailOverviewSettingsSnapshot,
    ) -> MediaDetailConfigValueSummary:
        if config.has_custom_filter_override and self._has_meaningful_filters(config.filters):
            return MediaDetailConfigValueSummary(
                name_key="mediaDetail.customValue",
                is_default=False,
            )
        if config.filter_config_id:
            preset = next((item for item in snapshot.filters if item.id == config.filter_config_id), None)
            if preset:
                return MediaDetailConfigValueSummary(
                    id=preset.id,
                    name=preset.name,
                    is_default=bool(preset.active_default and config.is_default_filter),
                )
        if snapshot.default_filter:
            return MediaDetailConfigValueSummary(
                id=snapshot.default_filter.id,
                name=snapshot.default_filter.name,
                is_default=True,
            )
        return MediaDetailConfigValueSummary(name_key="mediaDetail.emptyValue")

    def _resolve_custom_rules_summary(
        self,
        config: EffectiveMediaDownloadConfig,
    ) -> MediaDetailCustomRulesSummary:
        unmatched_rules = config.unmatched_rules or []
        if not unmatched_rules:
            return MediaDetailCustomRulesSummary()
        return MediaDetailCustomRulesSummary(
            enabled=True,
            count=len(unmatched_rules),
            summary_key="mediaDetail.customRulesCount",
            summary_params={"count": str(len(unmatched_rules))},
        )

    def _resolve_quality_profile_summary(
        self,
        config: EffectiveMediaDownloadConfig,
        snapshot: _DetailOverviewSettingsSnapshot,
    ) -> MediaDetailConfigValueSummary:
        profile = config.quality_profile
        if profile:
            return MediaDetailConfigValueSummary(
                id=profile.id,
                name=profile.name,
                is_default=bool(profile.active_default and config.is_default_quality_profile),
            )
        return MediaDetailConfigValueSummary(name_key="common.notSet")

    def _create_ready_state(self) -> MediaDetailActionReadinessItem:
        return MediaDetailActionReadinessItem()

    def _create_blocked_state(self, reason_key: str, target: str) -> MediaDetailActionReadinessItem:
        return MediaDetailActionReadinessItem(available=False, reason_key=reason_key, target=target)

    def _has_valid_default_downloader_id(self, snapshot: _DetailOverviewSettingsSnapshot) -> bool:
        if not snapshot.enabled_downloaders:
            return False
        return bool(
            snapshot.default_downloader_id
            and snapshot.default_downloader_id in snapshot.enabled_downloaders
        )

    def _has_valid_default_directory(self, snapshot: _DetailOverviewSettingsSnapshot) -> bool:
        return any(item.is_default for item in snapshot.enabled_directories)

    def _has_usable_directory_bindings(
        self,
        media_type: MediaType,
        snapshot: _DetailOverviewSettingsSnapshot,
    ) -> bool:
        for directory in snapshot.enabled_directories:
            if not directory.is_default:
                continue
            if not directory.downloader_id:
                continue
            if media_type == MediaType.movie and directory.movie_template_id:
                return True
            if media_type == MediaType.tv and directory.tv_template_id:
                return True
        return False

    def _resolve_action_readiness(
        self,
        media_type: MediaType,
        snapshot: _DetailOverviewSettingsSnapshot,
    ) -> MediaDetailActionReadinessSummary:
        if not snapshot.indexers_enabled:
            blocked = self._create_blocked_state("actionPrerequisites.indexerRequired", "indexer")
            return MediaDetailActionReadinessSummary(search=blocked, download=blocked, subscription=blocked)

        if not self._has_valid_default_downloader_id(snapshot):
            blocked = self._create_blocked_state("actionPrerequisites.defaultDownloaderRequired", "downloader")
            return MediaDetailActionReadinessSummary(
                search=self._create_ready_state(),
                download=blocked,
                subscription=blocked,
            )

        if not snapshot.has_default_template:
            blocked = self._create_blocked_state(
                "actionPrerequisites.defaultMovieTemplateRequired" if media_type == MediaType.movie else "actionPrerequisites.defaultTvTemplateRequired",
                "naming",
            )
            return MediaDetailActionReadinessSummary(
                search=self._create_ready_state(),
                download=blocked,
                subscription=blocked,
            )

        if not snapshot.enabled_directories:
            blocked = self._create_blocked_state(
                "actionPrerequisites.defaultMovieDirectoryRequired" if media_type == MediaType.movie else "actionPrerequisites.defaultTvDirectoryRequired",
                "directory",
            )
            return MediaDetailActionReadinessSummary(
                search=self._create_ready_state(),
                download=blocked,
                subscription=blocked,
            )

        if not self._has_valid_default_directory(snapshot):
            blocked = self._create_blocked_state(
                "actionPrerequisites.defaultMovieDirectoryRequired" if media_type == MediaType.movie else "actionPrerequisites.defaultTvDirectoryRequired",
                "directory",
            )
            return MediaDetailActionReadinessSummary(
                search=self._create_ready_state(),
                download=blocked,
                subscription=blocked,
            )

        if not self._has_usable_directory_bindings(media_type, snapshot):
            blocked = self._create_blocked_state("actionPrerequisites.directoryBindingRequired", "directory")
            return MediaDetailActionReadinessSummary(
                search=self._create_ready_state(),
                download=blocked,
                subscription=blocked,
            )

        ready = self._create_ready_state()
        return MediaDetailActionReadinessSummary(
            search=ready,
            download=ready,
            subscription=ready,
            follow=ready,
        )

    def _resolve_resource_discovery_summary(
        self,
        media_id: MediaID,
        config: EffectiveMediaDownloadConfig,
        search_running: bool,
        season_number: int | None = None,
    ) -> MediaDetailResourceDiscoverySummary:
        cached_results = resource_search_service.get_latest_media_cached_results(media_id, season_number=season_number)
        searched = cached_results is not None
        results = cached_results or []
        searched_at, _search_duration_seconds = resource_search_service.get_latest_media_search_metadata(
            media_id,
            season_number=season_number,
        )

        matched_by_custom_rule_count = 0
        if config.unmatched_rules:
            for result in results:
                if result.matched_by_id:
                    continue
                attrs = resource_parser.parse(result.title, desc=result.description)
                if matches_unmatched_rules(
                    Resource(resources=result, attrs=attrs),
                    config.unmatched_rules,
                ):
                    matched_by_custom_rule_count += 1

        if search_running:
            search_state: str = "searching"
        elif searched:
            search_state = "ready"
        else:
            search_state = "idle"

        return MediaDetailResourceDiscoverySummary(
            searched=searched,
            search_state=search_state,
            available_count=len(results),
            matched_by_id_count=sum(1 for result in results if result.matched_by_id),
            matched_by_custom_rule_count=matched_by_custom_rule_count,
            searched_at=searched_at,
        )

    def _build_settings_snapshot(self, media_type: MediaType) -> _DetailOverviewSettingsSnapshot:
        filters = settings_service.list_filter_presets()
        quality_profiles = settings_service.list_quality_profiles()
        directories = settings_service.list_directories()
        indexers = settings_service.list_indexers()
        downloaders = settings_service.list_downloaders()
        templates = settings_service.list_naming_templates()
        default_downloader_id = settings_service.get_default_downloader_id()

        enabled_directories = [
            item for item in directories
            if item.enabled and item.media_type == media_type
        ]
        default_directory = next((item for item in enabled_directories if item.is_default), None)
        default_filter = next((item for item in filters if item.active_default), None)

        return _DetailOverviewSettingsSnapshot(
            filters=filters,
            quality_profiles=quality_profiles,
            directories=directories,
            indexers_enabled=any(item.enabled for item in indexers),
            enabled_downloaders={item.id for item in downloaders if item.enabled and item.id},
            default_downloader_id=default_downloader_id,
            has_default_template=any(
                item.enabled and item.type == media_type and item.is_default
                for item in templates
            ),
            enabled_directories=enabled_directories,
            default_directory=default_directory,
            default_filter=default_filter,
        )

    def _resolve_effective_config(
        self,
        media_id: MediaID,
        config: MediaDownloadConfig | None,
        snapshot: _DetailOverviewSettingsSnapshot,
        season_number: int | None = None,
    ) -> EffectiveMediaDownloadConfig:
        use_default_filter = not bool(config and (config.filter_config_id or config.filters))
        directory_id = config.directory_id if config and config.directory_id else (
            snapshot.default_directory.id if snapshot.default_directory else None
        )
        filter_config_id = config.filter_config_id if config and config.filter_config_id else (
            snapshot.default_filter.id if use_default_filter and snapshot.default_filter else None
        )
        filter_config = next((item for item in snapshot.filters if item.id == filter_config_id), None)
        default_quality_profile = next((item for item in snapshot.quality_profiles if item.active_default), None) or (
            snapshot.quality_profiles[0] if snapshot.quality_profiles else None
        )
        quality_profile_id = config.quality_profile_id if config and config.quality_profile_id else (
            filter_config.quality_profile_id if filter_config and filter_config.quality_profile_id else (
                default_quality_profile.id if default_quality_profile else None
            )
        )
        filters = config.filters if config and config.filters else (
            filter_config.filters if filter_config else None
        )
        quality_profile = next((item for item in snapshot.quality_profiles if item.id == quality_profile_id), None)

        return EffectiveMediaDownloadConfig(
            media_id=media_id,
            season_number=config.season_number if config else (season_number if media_id.media_type == MediaType.tv else None),
            sub_id=config.sub_id if config else None,
            directory_id=directory_id,
            filter_config_id=filter_config_id,
            quality_profile_id=quality_profile_id,
            filters=filters,
            has_custom_filter_override=bool(config and config.filters),
            sites=config.sites if config else None,
            quality_profile=quality_profile,
            unmatched_rules=list(config.unmatched_rules) if config else [],
            is_default_directory=not bool(config and config.directory_id) and bool(snapshot.default_directory),
            is_default_filter=not bool(config and (config.filter_config_id or config.filters)) and bool(snapshot.default_filter),
            is_default_quality_profile=not bool(config and config.quality_profile_id) and bool(quality_profile and quality_profile.active_default),
        )


media_detail_overview_service = MediaDetailOverviewService()
