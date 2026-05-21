from app.schemas.config import DanmuAddonConfig
from app.schemas.domain.media import MediaFullInfo
from app.schemas.media_id import MediaID
from app.services.application.workflows.scoped_seasons import positive_season_number
from app.services.domain.media import media_service
from app.services.integration.danmu.service import danmu_provider_service


class DanmuSourceResolver:
    def has_fetchable_vendor(self, media: MediaFullInfo, config: DanmuAddonConfig) -> bool:
        return danmu_provider_service.has_fetchable_vendor(media.vendors, config.providers)

    async def media_with_fetchable_source(
        self,
        media_id: MediaID,
        *,
        season_number: int | None,
        config: DanmuAddonConfig,
    ) -> MediaFullInfo | None:
        if media_id.media_type.value == "tv" and positive_season_number(season_number) is None:
            return None
        media = await media_service.info(media_id, season_number=season_number)
        if media and self.has_fetchable_vendor(media, config):
            return media
        refreshed = await media_service.refresh_profile(media_id, season_number=season_number)
        if refreshed and self.has_fetchable_vendor(refreshed, config):
            return await media_service.info(media_id, season_number=season_number) or media
        return await media_service.info(media_id, season_number=season_number)


danmu_source_resolver = DanmuSourceResolver()
