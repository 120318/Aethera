from app.schemas.exception import InvalidRequestException, MediaNotFoundException
from app.schemas.media_id import MediaID, Provider
from app.schemas.domain.media import MediaFullInfo
from app.schemas.domain.media_source import MediaSourceLookup, MediaSourceName
from app.schemas.domain.media_types import MediaType
from app.services.domain.media import media_service


class MediaDetailApplicationService:
    def _default_detail_season(self, media: MediaFullInfo) -> int | None:
        if media.media_type != MediaType.tv:
            return None
        if media.season_number and media.season_number > 0:
            return int(media.season_number)
        preferred = next((season for season in media.seasons if season.season_number == 1), None)
        if preferred:
            return 1
        available = sorted(
            int(season.season_number)
            for season in media.seasons
            if season.season_number is not None and season.season_number > 0
        )
        return available[0] if available else None

    def _requested_season(self, media_type: MediaType | None, season_number: int | None) -> int | None:
        if media_type != MediaType.tv:
            return None
        if season_number and season_number > 0:
            return int(season_number)
        return None

    async def get_detail(
        self,
        *,
        media_id: MediaID | None,
        source: MediaSourceName | None,
        source_id: str | None,
        media_type: MediaType | None,
        season_number: int | None,
    ) -> MediaFullInfo:
        requested_media_type = media_id.media_type if media_id is not None else media_type
        requested_season = self._requested_season(requested_media_type, season_number)
        if media_id is not None:
            if media_id.media_type == MediaType.tv and requested_season is None:
                raise InvalidRequestException("backendErrors.seasonRequired")
            media = await media_service.info(media_id, season_number=requested_season)
        elif source == MediaSourceName.tmdb and source_id and media_type:
            requested_season = requested_season or (1 if media_type == MediaType.tv else None)
            media = await media_service.info(
                MediaID(provider=Provider.tmdb, media_type=media_type, id=source_id),
                season_number=requested_season,
            )
        elif source == MediaSourceName.douban and source_id and media_type:
            media = await media_service.info_from_source(
                MediaSourceLookup(source=MediaSourceName.douban, source_id=source_id, media_type=media_type)
            )
        else:
            media = None
        if not media:
            raise MediaNotFoundException()
        media = media_service.apply_season_context(media, requested_season or season_number or self._default_detail_season(media))
        media.viewed = media_service.is_viewed_media(media.media_id)
        return media


media_detail_application_service = MediaDetailApplicationService()
