from __future__ import annotations

import logging

from app.schemas.config import BrowseSource
from app.schemas.domain.media import EpisodeInfo, MediaFullInfo, MediaIdentity, MediaSimpleInfo, SeasonDetails
from app.schemas.domain.media_source import MediaSourceLookup
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.search_models import MediaSearchResult
from app.schemas.exception import InvalidRequestException, MediaNotFoundException
from app.schemas.media_id import MediaID, Provider
from app.services.config.settings_service import settings_service
from app.services.domain.media.profile.context import media_profile_context_service
from app.services.domain.media.provider.clients import MediaProviderClients
from app.services.domain.media.provider.detail import MediaProviderDetail
from app.services.domain.media.provider.discover import MediaProviderDiscover
from app.services.domain.media.provider.mapping import MediaProviderMapping
from app.services.domain.media.provider.normalization import resolve_tmdb_selected_season, subject_type
from app.services.domain.media.provider.search import search_douban, search_tmdb
from app.utils import parse_tv_title

logger = logging.getLogger("app.services.media")


class MediaProviderService:
    def __init__(self) -> None:
        self.clients = MediaProviderClients()
        self.mapping = MediaProviderMapping(clients=self.clients)
        self.detail = MediaProviderDetail(clients=self.clients, mapping=self.mapping)
        self.discover = MediaProviderDiscover(self.clients)

    def _require_media_identity(self, media_id: MediaID, title: str | None, year: int | None) -> MediaIdentity:
        return self.detail.require_media_identity(media_id, title, year)

    def _canonical_tmdb_media_id(self, media_type: MediaType, tmdb_id: int) -> MediaID:
        return self.mapping.canonical_tmdb_media_id(media_type, tmdb_id)

    def supports_discover_key(self, key: str) -> bool:
        return self.discover.supports_discover_key(key)

    def supports_tmdb_discover_key(self, key: str) -> bool:
        return self.discover.supports_tmdb_discover_key(key)

    def discover_available(self) -> bool:
        return self.discover.discover_available()

    def tmdb_discover_available(self) -> bool:
        return self.discover.tmdb_discover_available()

    async def discover_items(self, key: str, start: int = 0, count: int = 20):
        return await self.discover.discover_items(key, start=start, count=count)

    async def tmdb_discover_items(self, key: str, start: int = 0, count: int = 20):
        return await self.discover.tmdb_discover_items(key, start=start, count=count)

    async def info(
        self,
        mid: MediaID,
        *,
        season_number: int | None = None,
        include_default_season_details: bool = False,
        default_season_year: int | None = None,
    ) -> MediaFullInfo | None:
        return await self.detail.info(
            mid,
            season_number=season_number,
            include_default_season_details=include_default_season_details,
            default_season_year=default_season_year,
        )

    async def info_from_source(self, lookup: MediaSourceLookup) -> MediaFullInfo | None:
        return await self.detail.info_from_source(lookup)

    async def attach_source_tmdb_mapping(
        self,
        lookup: MediaSourceLookup,
        *,
        tmdb_id: int,
        season_number: int | None = None,
        episode_count_override: int | None = None,
    ) -> MediaID:
        client = self.clients.get_douban_client()
        if not client:
            raise MediaNotFoundException()
        subject_type_value = subject_type(lookup.media_type)
        detail = await client.get_subject_detail(lookup.source_id, subject_type_value)
        if not detail:
            raise MediaNotFoundException()

        title = detail.title or ""
        resolved_season = season_number
        if lookup.media_type == MediaType.tv:
            title, parsed_season = parse_tv_title(title)
            resolved_season = season_number or parsed_season
        self._require_media_identity(
            MediaID(provider=Provider.douban, media_type=lookup.media_type, id=lookup.source_id),
            title,
            detail.year,
        )

        tmdb_details, _vendors = await self.detail.get_tmdb_detail_bundle(tmdb_id, subject_type_value)
        if not tmdb_details or not tmdb_details.provider_id:
            raise InvalidRequestException("backendErrors.tmdbIdInvalidOrTypeMismatch")
        if lookup.media_type == MediaType.tv:
            resolved_season = resolve_tmdb_selected_season(tmdb_details.seasons, resolved_season, detail.year)
            if not resolved_season or resolved_season <= 0:
                raise InvalidRequestException("backendErrors.seasonRequired")
        external = tmdb_details.external_ids or await self.clients.get_tmdb_client().get_external_ids(tmdb_id, subject_type_value)
        canonical_media_id = self._canonical_tmdb_media_id(lookup.media_type, tmdb_id)
        await self.mapping.set_cached_tmdb_mapping(
            canonical_media_id,
            tmdb_id,
            external.imdb_id if external else None,
            lookup.source_id,
            resolved_season if lookup.media_type == MediaType.tv else None,
            episode_count_override if lookup.media_type == MediaType.tv else None,
        )
        return canonical_media_id

    async def get_episode_info(self, tmdb_id: int, season_number: int, episode_number: int) -> EpisodeInfo | None:
        try:
            return await self.clients.get_tmdb_client().get_episode_details_with_fallback(tmdb_id, season_number, episode_number)
        except ValueError:
            return None

    async def get_season_details(self, tmdb_id: int, season_number: int) -> SeasonDetails | None:
        try:
            return await self.clients.get_tmdb_client().get_season_details_with_fallback(tmdb_id, season_number)
        except ValueError:
            return None

    async def simple_info(self, media_id: MediaID) -> MediaSimpleInfo | None:
        media = await self.info(media_id)
        return media_profile_context_service.enrich_simple_media(MediaSimpleInfo(
            media_id=media.media_id,
            title=media.title,
            year=media.year,
            media_type=media.media_type,
            imdb_id=media.imdb_id,
            douban_id=media.douban_id,
            tmdb_id=media.tmdb_id,
            seasons_count=media.seasons_count,
            season_number=media.season_number,
            episodes_count=media.episodes_count,
            aired_episode_count=media.aired_episode_count,
        )) if media else None

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
        if source == BrowseSource.tmdb:
            return await self._search_tmdb(query, media_type=media_type, start=start, limit=limit, year=year)
        return await self._search_douban(query, media_type=media_type, start=start, limit=limit, year=year)

    async def _search_douban(
        self,
        query: str,
        media_type: MediaType | None = None,
        start: int = 0,
        limit: int = 10,
        year: int | None = None,
    ) -> list[MediaSearchResult]:
        return await search_douban(
            client=self.clients.get_douban_client(),
            query=query,
            media_type=media_type,
            start=start,
            limit=limit,
            year=year,
            require_media_identity=self._require_media_identity,
            logger=logger,
        )

    async def _search_tmdb(
        self,
        query: str,
        media_type: MediaType | None = None,
        start: int = 0,
        limit: int = 10,
        year: int | None = None,
    ) -> list[MediaSearchResult]:
        return await search_tmdb(
            client=self.clients.get_tmdb_client(),
            query=query,
            media_type=media_type,
            start=start,
            limit=limit,
            year=year,
            canonical_tmdb_media_id=self._canonical_tmdb_media_id,
        )
