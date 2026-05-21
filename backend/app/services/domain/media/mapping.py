from collections.abc import Callable

from pydantic import BaseModel, ConfigDict

from app.clients.tmdb import TMDBClient
from app.db.repositories.media_identity_repository import MediaIdentityRepository
from app.db.repositories.media_external_mapping_repository import MediaExternalMappingRepository
from app.schemas.domain.media import MediaSimpleInfo
from app.schemas.domain.media_types import MediaType
from app.schemas.exception import ConfigurationException, InvalidRequestException, MediaNotFoundException
from app.schemas.media_id import MediaID, Provider
from app.schemas.persistence.media_external_mapping import MediaExternalMappingRecord
from app.services.config.settings_service import settings_service


class TMDBMappingAttachResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    canonical_media_id: MediaID
    source_media_id: MediaID
    season_number: int | None = None
    previous_mapping: MediaExternalMappingRecord | None = None
    source_douban_media_id: MediaID | None = None


class MediaExternalMappingService:
    def __init__(
        self,
        *,
        mapping_repo: MediaExternalMappingRepository | None = None,
        identity_repo: MediaIdentityRepository | None = None,
        tmdb_config_getter=None,
        tmdb_client_factory: Callable | None = None,
    ) -> None:
        self.mapping_repo = mapping_repo or MediaExternalMappingRepository()
        self.identity_repo = identity_repo or MediaIdentityRepository()
        self.tmdb_config_getter = tmdb_config_getter or (lambda: settings_service.get_base_services_config().themoviedb)
        self.tmdb_client_factory = tmdb_client_factory or TMDBClient

    async def attach_tmdb_mapping(
        self,
        media: MediaSimpleInfo | None,
        *,
        tmdb_id: int,
        season_number: int | None = None,
        episode_count_override: int | None = None,
    ) -> TMDBMappingAttachResult:
        if not media:
            raise MediaNotFoundException()

        tmdb_config = self.tmdb_config_getter()
        if not str(tmdb_config.api_key or "").strip():
            raise ConfigurationException("backendErrors.config.tmdbApiKeyRequired")

        client = self.tmdb_client_factory(tmdb_config)
        subject_type = "movie" if media.media_type == MediaType.movie else "tv"
        details = await client.get_details_with_fallback(tmdb_id, subject_type)
        if not details or not details.provider_id:
            raise InvalidRequestException("backendErrors.tmdbIdInvalidOrTypeMismatch")

        external = await client.get_external_ids(tmdb_id, subject_type)
        resolved_imdb_id = external.imdb_id if external and str(external.imdb_id or "").strip() else media.imdb_id
        target_season_number = (season_number or media.season_number or 1) if media.media_type == MediaType.tv else None
        previous_mapping = (
            self.mapping_repo.find_by_douban_id_and_season(
                media.douban_id,
                media.media_type.value,
                target_season_number,
            )
            if media.douban_id
            else (
                self.mapping_repo.find_by_media_id_and_season(media.media_id, target_season_number)
                if media.media_type == MediaType.tv
                else self.mapping_repo.find_by_media_id(media.media_id)
            )
        )
        canonical_media_id = MediaID(provider=Provider.tmdb, media_type=media.media_type, id=str(tmdb_id))
        self.mapping_repo.upsert(
            media_id=canonical_media_id,
            tmdb_id=tmdb_id,
            imdb_id=resolved_imdb_id,
            douban_id=media.douban_id,
            season_number=target_season_number,
            episode_count_override=episode_count_override if media.media_type == MediaType.tv else None,
        )
        return TMDBMappingAttachResult(
            canonical_media_id=canonical_media_id,
            source_media_id=media.media_id,
            season_number=target_season_number,
            previous_mapping=previous_mapping,
            source_douban_media_id=MediaID(provider=Provider.douban, media_type=media.media_type, id=media.douban_id) if media.douban_id else None,
        )

    def finalize_tmdb_mapping_attach(self, result: TMDBMappingAttachResult) -> None:
        source_media_id = result.source_media_id
        if source_media_id != result.canonical_media_id:
            self.identity_repo.merge_media_id(source_media_id, result.canonical_media_id)

        previous_mapping = result.previous_mapping
        if previous_mapping and previous_mapping.media_id != result.canonical_media_id:
            if previous_mapping.media_id != source_media_id:
                self.identity_repo.merge_media_id(previous_mapping.media_id, result.canonical_media_id)
            self.mapping_repo.remove(previous_mapping.media_id, previous_mapping.season_number)

    def rollback_tmdb_mapping_attach(self, result: TMDBMappingAttachResult) -> None:
        self.mapping_repo.remove(result.canonical_media_id, result.season_number)
        previous_mapping = result.previous_mapping
        if previous_mapping:
            self.mapping_repo.upsert(
                media_id=previous_mapping.media_id,
                tmdb_id=previous_mapping.tmdb_id,
                imdb_id=previous_mapping.imdb_id,
                douban_id=previous_mapping.douban_id,
                season_number=previous_mapping.season_number,
                episode_count_override=previous_mapping.episode_count_override,
            )
            return
        if result.source_douban_media_id:
            self.mapping_repo.remove(result.source_douban_media_id, result.season_number)


media_external_mapping_service = MediaExternalMappingService()
