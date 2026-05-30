import logging

from app.core.request_perf_context import db_perf_source
from app.db.repositories.media_management_repository import media_management_repository
from app.db.repositories.media_external_mapping_repository import MediaExternalMappingRepository
from app.schemas.config import BrowseSource
from app.schemas.media_id import MediaID
from app.schemas.domain.managed_media_profile import ManagedMediaProfile
from app.schemas.domain.media import EpisodeInfo, MediaExecutionSnapshot, MediaFullInfo, MediaIdentity, MediaSimpleInfo, SeasonDetails
from app.schemas.domain.media_context import ResolvedMediaContext
from app.schemas.domain.media_source import MediaSourceLookup
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.schedule import MediaScheduleSummary, ScheduleAiring
from app.schemas.integration.media.provider import ProviderSearchItem
from app.schemas.domain.search_models import MediaSearchResult
from app.schemas.runtime.media_management import MediaManagementRowsPage, MediaManagementSummary
from app.services.domain.media.profile.context import media_profile_context_service
from app.services.domain.media.profile.season import apply_media_season_context
from app.services.domain.media.execution_snapshot import MediaExecutionSnapshotService
from app.services.domain.media.profile.service import MediaProfileService
from app.services.domain.media.provider_cache import MediaProviderCacheService
from app.services.domain.media.provider.service import MediaProviderService
from app.services.domain.media.schedule.service import MediaScheduleService

logger = logging.getLogger("app.services.media")


class MediaService:
    def __init__(self) -> None:
        self.provider_service = MediaProviderService()
        self.schedule_service = MediaScheduleService()
        self.profile_service = MediaProfileService(self.provider_service, self.schedule_service)
        self.execution_snapshot_service = MediaExecutionSnapshotService(self.profile_service)
        self.provider_cache_service = MediaProviderCacheService(self.provider_service)
        self.mapping_repo = MediaExternalMappingRepository()
        self.management_repo = media_management_repository

    # ── Managed Media Profiles ──

    async def info(
        self,
        media_id: MediaID,
        *,
        season_number: int | None = None,
        include_default_season_details: bool = False,
        default_season_year: int | None = None,
    ) -> MediaFullInfo | None:
        return await self.profile_service.info(
            media_id,
            season_number=season_number,
            include_default_season_details=include_default_season_details,
            default_season_year=default_season_year,
        )

    async def info_with_cache_status(
        self,
        media_id: MediaID,
        *,
        season_number: int | None = None,
        include_default_season_details: bool = False,
        default_season_year: int | None = None,
    ) -> tuple[MediaFullInfo | None, str]:
        return await self.profile_service.info_with_cache_status(
            media_id,
            season_number=season_number,
            include_default_season_details=include_default_season_details,
            default_season_year=default_season_year,
        )

    async def info_from_source(self, lookup: MediaSourceLookup) -> MediaFullInfo | None:
        return await self.profile_service.info_from_source(lookup)

    async def cached_info(self, media_id: MediaID) -> MediaFullInfo | None:
        return await self.profile_service.cached_info(media_id)

    async def season_detail_for_library_view(self, media_id: MediaID, *, season_number: int) -> MediaFullInfo | None:
        return await self.profile_service.info(media_id, season_number=season_number)

    async def simple_info(self, media_id: MediaID) -> MediaSimpleInfo | None:
        return await self.profile_service.simple_info(media_id)

    def apply_season_context[T: MediaFullInfo | MediaSimpleInfo](self, media: T, season_number: int | None) -> T:
        return apply_media_season_context(media, season_number)

    def resolve_media_context(self, media: MediaFullInfo) -> ResolvedMediaContext:
        return media_profile_context_service.resolve_context_from_media(media)

    def tmdb_id_from_media_context(self, context: ResolvedMediaContext) -> int | None:
        return media_profile_context_service.tmdb_id_from_context(context)

    async def build_schedule_summary_for_media(self, media: MediaFullInfo) -> MediaScheduleSummary:
        return await self.schedule_service.build_schedule_summary_for_media(media)

    async def build_schedule_bundle(self, media: MediaFullInfo) -> tuple[MediaScheduleSummary, list[ScheduleAiring]]:
        return await self.schedule_service.build_schedule_bundle(media)

    async def resolve_execution_snapshot(
        self,
        media_id: MediaID,
        *,
        season_number: int | None = None,
        require_tv_season: bool = False,
        require_episode_count: bool = False,
        include_schedule_snapshot: bool = False,
    ) -> MediaExecutionSnapshot:
        return await self.execution_snapshot_service.resolve_execution_snapshot(
            media_id,
            season_number=season_number,
            require_tv_season=require_tv_season,
            require_episode_count=require_episode_count,
            include_schedule_snapshot=include_schedule_snapshot,
        )

    async def attach_source_tmdb_mapping(
        self,
        lookup: MediaSourceLookup,
        *,
        tmdb_id: int,
        season_number: int | None = None,
        episode_count_override: int | None = None,
    ) -> MediaID:
        media_id = await self.provider_service.attach_source_tmdb_mapping(
            lookup,
            tmdb_id=tmdb_id,
            season_number=season_number,
            episode_count_override=episode_count_override,
        )
        mapping = self.provider_service.mapping.mapping_repo.find_by_douban_id(lookup.source_id, lookup.media_type.value)
        await self.apply_source_mapping_snapshot(
            media_id,
            season_number=mapping.season_number if mapping else season_number,
            douban_id=(mapping.douban_id if mapping else lookup.source_id) if lookup.source.value == "douban" else None,
            episode_count_override=mapping.episode_count_override if mapping else episode_count_override,
        )
        return media_id

    async def apply_source_mapping_snapshot(
        self,
        media_id: MediaID,
        *,
        season_number: int | None,
        douban_id: str | None = None,
        episode_count_override: int | None = None,
    ) -> None:
        await self.profile_service.apply_source_mapping_snapshot(
            media_id,
            season_number=season_number,
            douban_id=douban_id,
            episode_count_override=episode_count_override,
        )

    def discover_available(self, source: BrowseSource) -> bool:
        if source == BrowseSource.tmdb:
            return self.provider_service.tmdb_discover_available()
        return self.provider_service.discover_available()

    def supports_discover_key(self, source: BrowseSource, key: str) -> bool:
        if source == BrowseSource.tmdb:
            return self.provider_service.supports_tmdb_discover_key(key)
        return self.provider_service.supports_discover_key(key)

    async def discover_items(
        self,
        source: BrowseSource,
        key: str,
        *,
        start: int,
        count: int,
    ) -> list[ProviderSearchItem]:
        if source == BrowseSource.tmdb:
            return await self.provider_service.tmdb_discover_items(key, start=start, count=count)
        return await self.provider_service.discover_items(key, start=start, count=count)

    async def upsert_active_profile_from_identity(self, media: MediaIdentity):
        return await self.profile_service.upsert_active_profile_from_identity(media)

    async def activate_existing_profile(self, media_id: MediaID) -> None:
        await self.profile_service.activate_existing_profile(media_id)

    async def refresh_profile(self, media_id: MediaID, existing=None, *, season_number: int | None = None):
        return await self.profile_service.refresh_profile(media_id, existing=existing, season_number=season_number)

    async def refresh_profile_safely(self, media_id: MediaID, season_number: int | None = None) -> None:
        await self.profile_service.refresh_profile_safely(media_id, season_number)

    async def refresh_active_profiles(self) -> int:
        return await self.profile_service.refresh_active_profiles()

    async def list_profiles_by_media_ids(self, media_ids: list[MediaID]) -> list[ManagedMediaProfile]:
        return await self.profile_service.list_profiles_by_media_ids(media_ids)

    async def list_profiles_by_media_targets(self, targets: list[tuple[MediaID, int | None]]) -> dict[str, ManagedMediaProfile]:
        return await self.profile_service.list_profiles_by_media_targets(targets)

    async def get_management_summary(self) -> MediaManagementSummary:
        return self.management_repo.get_summary()

    async def list_management_rows(
        self,
        *,
        statuses: list[str] | None = None,
        query: str | None = None,
        media_type: MediaType | None = None,
        sort: str = "activity",
        direction: str = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> MediaManagementRowsPage:
        return self.management_repo.list_page(
            statuses=statuses,
            query=query,
            media_type=media_type,
            sort=sort,
            direction=direction,
            limit=limit,
            offset=offset,
        )

    async def refresh_schedule_snapshot(
        self,
        media_id: MediaID,
        *,
        season_number: int | None = None,
    ) -> ManagedMediaProfile | None:
        return await self.profile_service.refresh_schedule_snapshot(media_id, season_number=season_number)

    async def cleanup_inactive_profiles(self) -> int:
        return await self.profile_service.cleanup_inactive_profiles()

    async def is_managed_media(self, media_id: MediaID) -> bool:
        return await self.profile_service.is_managed_media(media_id)

    async def mark_profile_inactive_if_unmanaged(self, media_id: MediaID) -> bool:
        return await self.profile_service.mark_profile_inactive_if_unmanaged(media_id)

    async def mark_inactive_profiles(self, active_media_ids: list[MediaID]) -> int:
        return await self.profile_service.mark_inactive_profiles(active_media_ids)

    # ── Viewed State ──

    def is_viewed_media(self, media_id: MediaID) -> bool:
        with db_perf_source("media.is_viewed"):
            return self.mapping_repo.exists_by_media_id(media_id)

    def mark_viewed_search_results(self, items: list[MediaSearchResult]) -> list[MediaSearchResult]:
        with db_perf_source("media.mark_viewed_search_results"):
            viewed_indexes = self.mapping_repo.find_viewed_search_results(items)
        for index, item in enumerate(items):
            item.viewed = index in viewed_indexes
        return items

    # ── Provider Reads ──

    async def get_episode_info(self, tmdb_id: int, season_number: int, episode_number: int) -> EpisodeInfo | None:
        return await self.provider_cache_service.get_episode_info(tmdb_id, season_number, episode_number)

    async def get_season_details(self, tmdb_id: int, season_number: int) -> SeasonDetails | None:
        return await self.provider_cache_service.get_season_details(tmdb_id, season_number)

    async def get_episode_info_for_media(
        self,
        media: MediaFullInfo,
        season_number: int,
        episode_number: int,
    ) -> EpisodeInfo | None:
        return await self.provider_cache_service.get_episode_info_for_media(media, season_number, episode_number)

    async def get_season_details_for_media(self, media: MediaFullInfo, season_number: int) -> SeasonDetails | None:
        return await self.provider_cache_service.get_season_details_for_media(media, season_number)

    async def search(
        self,
        query: str,
        media_type: MediaType | None = None,
        start: int = 0,
        limit: int = 10,
        year: int | None = None,
        source: BrowseSource | None = None,
    ) -> list[MediaSearchResult]:
        return await self.provider_cache_service.search(query, media_type=media_type, start=start, limit=limit, year=year, source=source)

    # ── Schedule ──


media_service = MediaService()
