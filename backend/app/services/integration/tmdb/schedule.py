import logging

from pydantic import BaseModel, ValidationError

from app.clients.tmdb import TMDBClient
from app.schemas.config import TMDBConfig
from app.schemas.domain.media import SeasonDetails
from app.schemas.domain.media_types import MediaType
from app.schemas.integration.media.provider import (
    ProviderPlatformInfo,
    ProviderReleaseDateEntry,
    ProviderReleaseRegion,
    ProviderScheduleDetail,
    ProviderWatchProviders,
)
from app.services.config.settings_service import settings_service
from app.services.platform.cache_service import cache_service

logger = logging.getLogger("app.services.integration.tmdb.schedule")


class TMDBScheduleGateway:
    cache_ttl_seconds: int = 6 * 3600

    def _tmdb_config(self) -> TMDBConfig:
        return settings_service.get_base_services_config().themoviedb

    def _tmdb_client(self) -> TMDBClient | None:
        config = self._tmdb_config()
        if not config.api_key:
            return None
        return TMDBClient(config)

    async def _cache_tmdb_payload(
        self,
        cache_type: str,
        identifier: str,
        payload: BaseModel,
    ) -> None:
        await cache_service.set(
            "tmdb",
            cache_type,
            identifier,
            payload,
            self.cache_ttl_seconds,
        )

    async def get_tv_details(self, tmdb_id: int) -> ProviderScheduleDetail | None:
        identifier = f"tv:{tmdb_id}"
        cached = await cache_service.read("tmdb", "tv_details", identifier)
        if cached:
            return ProviderScheduleDetail.model_validate(cached)
        tmdb_client = self._tmdb_client()
        if not tmdb_client:
            return None
        details = await tmdb_client.get_details(tmdb_id, "tv")
        if details and details.provider_id:
            payload = ProviderScheduleDetail(
                status=details.status,
                networks=details.networks,
                seasons=details.seasons,
            )
            await self._cache_tmdb_payload("tv_details", identifier, payload)
            return payload
        return None

    async def get_movie_release_dates(self, tmdb_id: int) -> list[ProviderReleaseRegion]:
        identifier = f"movie:{tmdb_id}"
        cached = await cache_service.read("tmdb", "movie_release_dates", identifier)
        if cached:
            normalized = self._normalize_cached_release_regions(cached)
            if normalized is not None:
                return normalized
            await cache_service.delete("tmdb", "movie_release_dates", identifier)
        tmdb_client = self._tmdb_client()
        if not tmdb_client:
            return []
        payload = await tmdb_client.get_movie_release_dates(tmdb_id)
        await cache_service.set("tmdb", "movie_release_dates", identifier, payload, self.cache_ttl_seconds)
        return payload

    def _normalize_cached_release_regions(
        self,
        cached,
    ) -> list[ProviderReleaseRegion] | None:
        if type(cached) is not list:
            logger.warning(
                "Invalid cached TMDB movie release dates payload type=%s, dropping cache entry",
                type(cached).__name__,
            )
            return None
        try:
            return [ProviderReleaseRegion.model_validate(item) for item in cached]
        except Exception:
            logger.warning("Invalid cached TMDB movie release dates list payload, dropping cache entry")
            return None

    async def get_season_details(self, tmdb_id: int, season_number: int) -> SeasonDetails | None:
        identifier = f"season:{tmdb_id}:{season_number}"
        cached = await cache_service.read("tmdb", "season", identifier)
        if cached:
            try:
                return SeasonDetails.model_validate(cached)
            except ValidationError:
                logger.warning(
                    "Invalid cached TMDB season payload for %s, dropping cache entry",
                    identifier,
                )
                await cache_service.delete("tmdb", "season", identifier)
        tmdb_client = self._tmdb_client()
        if not tmdb_client:
            return None
        payload = await tmdb_client.get_season_details_with_fallback(tmdb_id, season_number)
        if payload:
            await self._cache_tmdb_payload("season", identifier, payload)
            return payload
        return None

    async def get_watch_provider_payload(
        self,
        tmdb_id: int,
        media_type: MediaType,
        region: str,
    ) -> ProviderWatchProviders:
        identifier = f"{media_type.value}:{tmdb_id}:{region.upper()}"
        cached = await cache_service.read("tmdb", "watch_providers", identifier)
        if cached:
            return ProviderWatchProviders.model_validate(cached)
        tmdb_client = self._tmdb_client()
        if not tmdb_client:
            return ProviderWatchProviders()
        payload = await tmdb_client.get_watch_providers(tmdb_id, media_type.value, region)
        if not payload:
            return ProviderWatchProviders()
        await self._cache_tmdb_payload("watch_providers", identifier, payload)
        return payload

    async def get_watch_provider_payloads(
        self,
        tmdb_id: int,
        media_type: MediaType,
        regions: list[str],
    ) -> dict[str, ProviderWatchProviders]:
        normalized_regions = []
        for region in regions:
            normalized = str(region or "").upper()
            if normalized and normalized not in normalized_regions:
                normalized_regions.append(normalized)
        if not normalized_regions:
            return {}

        cached_payloads: dict[str, ProviderWatchProviders] = {}
        missing_regions: list[str] = []
        for region in normalized_regions:
            identifier = f"{media_type.value}:{tmdb_id}:{region}"
            cached = await cache_service.read("tmdb", "watch_providers", identifier)
            if cached:
                cached_payloads[region] = ProviderWatchProviders.model_validate(cached)
            else:
                missing_regions.append(region)

        if not missing_regions:
            return cached_payloads

        tmdb_client = self._tmdb_client()
        if not tmdb_client:
            return {
                **cached_payloads,
                **{region: ProviderWatchProviders() for region in missing_regions},
            }
        fetched_payloads_by_region = await tmdb_client.get_watch_providers_by_regions(
            tmdb_id,
            media_type.value,
            missing_regions,
        )
        for region, payload in fetched_payloads_by_region.items():
            identifier = f"{media_type.value}:{tmdb_id}:{region}"
            if payload:
                await self._cache_tmdb_payload("watch_providers", identifier, payload)
        return {
            **cached_payloads,
            **{region: fetched_payloads_by_region.get(region, ProviderWatchProviders()) for region in missing_regions},
        }


tmdb_schedule_gateway = TMDBScheduleGateway()
