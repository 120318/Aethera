from __future__ import annotations

from typing import TYPE_CHECKING

from app.schemas.config import BrowseSource
from app.schemas.domain.media import EpisodeInfo, MediaFullInfo, SeasonDetails
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.search_models import MediaSearchResult
from app.services.config.settings_service import settings_service
from app.services.domain.media.profile.context import media_profile_context_service
from app.services.platform.cache_service import cache_service

if TYPE_CHECKING:
    from app.services.domain.media.provider.service import MediaProviderService

MEDIA_SEARCH_CACHE_VERSION = "20260427_viewed_mapping"


class MediaProviderCacheService:
    def __init__(self, provider_service: MediaProviderService) -> None:
        self.provider_service = provider_service

    def _media_search_cache_ttl(self) -> int:
        interval = settings_service.get_scheduler_config().subscription_sweep_interval_seconds
        try:
            normalized = int(interval)
        except (TypeError, ValueError):
            normalized = 600
        return max(normalized - 120, 0)

    def _episode_detail_key(self, *, tmdb_id: int, season_number: int, episode_number: int) -> str:
        return f"episode:{tmdb_id}:{season_number}:{episode_number}"

    def _season_detail_key(self, *, tmdb_id: int, season_number: int) -> str:
        return f"season:{tmdb_id}:{season_number}"

    def _media_search_key(
        self,
        *,
        source: str,
        query: str,
        start: int,
        limit: int,
        media_type: str,
        year: str,
    ) -> str:
        return f"{MEDIA_SEARCH_CACHE_VERSION}:{source}:{query}:{start}:{limit}:{media_type}:{year}"

    async def _get_cached_episode(self, cache_key: str) -> EpisodeInfo | None:
        cached = await cache_service.read("tmdb", "episode", cache_key)
        return EpisodeInfo.model_validate(cached) if cached else None

    async def _cache_episode(self, cache_key: str, episode: EpisodeInfo) -> None:
        await cache_service.set("tmdb", "episode", cache_key, episode, 86400)

    async def _get_cached_season(self, cache_key: str) -> SeasonDetails | None:
        cached = await cache_service.read("tmdb", "season", cache_key)
        return SeasonDetails.model_validate(cached) if cached else None

    async def _cache_season(self, cache_key: str, season: SeasonDetails) -> None:
        await cache_service.set("tmdb", "season", cache_key, season, 86400)

    async def _get_cached_search_results(self, cache_key: str) -> list[MediaSearchResult] | None:
        cached = await cache_service.read("douban", "search", cache_key)
        return [MediaSearchResult.model_validate(item) for item in cached] if cached else None

    async def _cache_search_results(self, cache_key: str, results: list[MediaSearchResult]) -> None:
        if not results:
            return
        await cache_service.set("douban", "search", cache_key, results, self._media_search_cache_ttl())

    async def get_episode_info(self, tmdb_id: int, season_number: int, episode_number: int) -> EpisodeInfo | None:
        cache_key = self._episode_detail_key(
            tmdb_id=tmdb_id,
            season_number=season_number,
            episode_number=episode_number,
        )
        cached = await self._get_cached_episode(cache_key)
        if cached:
            return cached
        result = await self.provider_service.get_episode_info(tmdb_id, season_number, episode_number)
        if result:
            await self._cache_episode(cache_key, result)
        return result

    async def get_season_details(self, tmdb_id: int, season_number: int) -> SeasonDetails | None:
        cache_key = self._season_detail_key(tmdb_id=tmdb_id, season_number=season_number)
        cached = await self._get_cached_season(cache_key)
        if cached:
            return cached
        result = await self.provider_service.get_season_details(tmdb_id, season_number)
        if result:
            await self._cache_season(cache_key, result)
        return result

    async def get_episode_info_for_media(
        self,
        media: MediaFullInfo,
        season_number: int,
        episode_number: int,
    ) -> EpisodeInfo | None:
        context = media_profile_context_service.resolve_context_from_media(media)
        tmdb_id = media_profile_context_service.tmdb_id_from_context(context)
        if not context.metadata_capabilities.has_season_episode_detail or not tmdb_id:
            return None
        return await self.get_episode_info(tmdb_id, season_number, episode_number)

    async def get_season_details_for_media(self, media: MediaFullInfo, season_number: int) -> SeasonDetails | None:
        context = media_profile_context_service.resolve_context_from_media(media)
        tmdb_id = media_profile_context_service.tmdb_id_from_context(context)
        if not context.metadata_capabilities.has_season_episode_detail or not tmdb_id:
            return None
        return await self.get_season_details(tmdb_id, season_number)

    async def search(
        self,
        query: str,
        media_type: MediaType | None = None,
        start: int = 0,
        limit: int = 10,
        year: int | None = None,
        source: BrowseSource | None = None,
    ) -> list[MediaSearchResult]:
        source = source or settings_service.get_base_services_config().browse_source
        media_type_key = media_type.value if media_type else "all"
        year_key = str(year) if year is not None else "all"
        cache_key = self._media_search_key(
            source=source.value,
            query=query,
            start=start,
            limit=limit,
            media_type=media_type_key,
            year=year_key,
        )
        cached = await self._get_cached_search_results(cache_key)
        if cached:
            return cached
        result = await self.provider_service.search(query, media_type=media_type, start=start, limit=limit, year=year, source=source)
        await self._cache_search_results(cache_key, result)
        return result
