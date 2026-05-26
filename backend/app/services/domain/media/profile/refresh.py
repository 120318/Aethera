from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.schemas.domain.managed_media_profile import ManagedMediaProfile
from app.schemas.domain.media import MediaFullInfo
from app.schemas.domain.media_source import MediaSourceLookup, MediaSourceName
from app.schemas.domain.media_types import MediaType
from app.schemas.exception.base import AppException
from app.schemas.media_id import MediaID

if TYPE_CHECKING:
    from app.services.domain.media.provider.service import MediaProviderService

logger = logging.getLogger("app.services.media")


async def fetch_profile_refresh_media(
    provider_service: MediaProviderService,
    media_id: MediaID,
    existing_profile: ManagedMediaProfile | None,
    *,
    season_number: int | None = None,
    source_douban_id: str | None = None,
) -> MediaFullInfo | None:
    if season_number is not None and season_number > 0:
        return await provider_service.info(media_id, season_number=season_number)
    if media_id.media_type == MediaType.tv:
        return None
    if not source_douban_id:
        return await provider_service.info(media_id)
    try:
        media = await provider_service.info_from_source(
            MediaSourceLookup(
                source=MediaSourceName.douban,
                source_id=source_douban_id,
                media_type=existing_profile.media_type if existing_profile else media_id.media_type,
            )
        )
    except (AppException, RuntimeError, ValueError):
        logger.warning("Douban profile refresh failed, falling back to TMDB: media=%s", media_id)
        return await provider_service.info(media_id)
    return media or await provider_service.info(media_id)
