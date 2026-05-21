from app.db.repositories.media_external_mapping_repository import MediaExternalMappingRepository
from app.schemas.domain.media_source import MediaSourceLookup, MediaSourceName, MediaTMDBMappingRequiredData
from app.schemas.domain.media_types import MediaType
from app.schemas.exception import MediaTMDBMappingRequiredException, RequestParamException
from app.schemas.media_id import MediaID, Provider
from app.services.domain.media.provider.clients import MediaProviderClients
from app.services.domain.media.provider.normalization import pick_best_tmdb_search_id


class MediaProviderMapping:
    def __init__(
        self,
        *,
        clients: MediaProviderClients,
        mapping_repo: MediaExternalMappingRepository | None = None,
    ) -> None:
        self.clients = clients
        self.mapping_repo = mapping_repo or MediaExternalMappingRepository()

    def parse_tmdb_media_id(self, media_id: MediaID) -> int:
        try:
            return int(media_id.id)
        except ValueError as exc:
            raise RequestParamException("media_id", media_id.id) from exc

    def canonical_tmdb_media_id(self, media_type: MediaType, tmdb_id: int) -> MediaID:
        return MediaID(provider=Provider.tmdb, media_type=media_type, id=str(tmdb_id))

    async def get_cached_tmdb_mapping(
        self,
        media_id: MediaID,
        season_number: int | None = None,
    ) -> tuple[int | None, str | None, str | None, int | None, int | None]:
        if media_id.media_type == MediaType.tv:
            cached = (
                self.mapping_repo.find_by_media_id_and_season(media_id, season_number)
                if season_number and season_number > 0
                else None
            )
        else:
            cached = self.mapping_repo.find_by_media_id(media_id)
        if not cached:
            return None, None, None, None, None
        return cached.tmdb_id, cached.imdb_id, cached.douban_id, cached.season_number, cached.episode_count_override

    async def set_cached_tmdb_mapping(
        self,
        media_id: MediaID,
        tmdb_id: int | None,
        imdb_id: str | None,
        douban_id: str | None,
        season_number: int | None,
        episode_count_override: int | None = None,
    ) -> None:
        self.mapping_repo.upsert(
            media_id=media_id,
            tmdb_id=tmdb_id,
            imdb_id=imdb_id,
            douban_id=douban_id,
            season_number=season_number,
            episode_count_override=episode_count_override,
        )

    async def get_tmdb_id(self, title: str, year: int | None, media_type: MediaType) -> int | None:
        try:
            results = await self.clients.get_tmdb_client().search(media_type.value, title, year)
            return pick_best_tmdb_search_id(title, results)
        except (TypeError, ValueError):
            return None

    async def resolve_tmdb_mapping(
        self,
        media_id: MediaID,
        title: str,
        year: int | None,
        media_type: MediaType,
        desired_season: int | None,
    ) -> tuple[int | None, str | None, int | None]:
        cached_tmdb_id, cached_imdb_id, _cached_douban_id, cached_season_number, _cached_episode_count_override = await self.get_cached_tmdb_mapping(media_id, desired_season)
        if cached_tmdb_id:
            return cached_tmdb_id, cached_imdb_id, desired_season or cached_season_number
        tmdb_id = await self.get_tmdb_id(title, year, media_type)
        return tmdb_id, None, desired_season

    def raise_tmdb_mapping_required(
        self,
        lookup: MediaSourceLookup,
        *,
        title: str,
        year: int,
        season_number: int | None,
        search_query: str | None = None,
    ) -> None:
        raise MediaTMDBMappingRequiredException(
            MediaTMDBMappingRequiredData(
                source=lookup.source.value,
                source_id=lookup.source_id,
                media_type=lookup.media_type,
                title=title,
                year=year,
                search_query=search_query,
                season_number=season_number if lookup.media_type == MediaType.tv else None,
                douban_id=lookup.source_id if lookup.source == MediaSourceName.douban else None,
            )
        )
