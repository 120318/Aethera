from __future__ import annotations

from typing import TYPE_CHECKING

from app.schemas.domain.media import MediaExecutionSnapshot, MediaFullInfo
from app.schemas.domain.media_types import MediaType
from app.schemas.exception import DownloadException, MediaNotFoundException
from app.schemas.media_id import MediaID
from app.services.domain.media.profile.season import apply_media_season_context

if TYPE_CHECKING:
    from app.services.domain.media.profile.service import MediaProfileService


class MediaExecutionSnapshotService:
    def __init__(self, profile_service: MediaProfileService) -> None:
        self.profile_service = profile_service

    def _apply_cached_tv_season_context(
        self,
        media: MediaFullInfo,
        season_number: int | None,
        *,
        require_episode_count: bool,
    ) -> MediaFullInfo:
        if media.media_type != MediaType.tv or season_number is None:
            return media
        selected = next((season for season in media.seasons if season.season_number == int(season_number)), None)
        if selected is None:
            raise DownloadException("backendErrors.mediaExecutionSnapshotSeasonMissing")
        if selected.episode_count is None and require_episode_count:
            raise DownloadException("backendErrors.mediaExecutionSnapshotEpisodeCountMissing")
        return media.model_copy(update={"season_number": int(season_number), "episodes_count": selected.episode_count})

    async def resolve_execution_snapshot(
        self,
        media_id: MediaID,
        *,
        season_number: int | None = None,
        require_tv_season: bool = False,
        require_episode_count: bool = False,
        include_schedule_snapshot: bool = False,
    ) -> MediaExecutionSnapshot:
        if media_id.media_type == MediaType.tv and require_tv_season and season_number is None:
            raise DownloadException("backendErrors.mediaExecutionSnapshotSeasonNumberRequired")

        use_simple_snapshot = media_id.media_type != MediaType.tv or season_number is None
        media = await self.profile_service.simple_info(media_id)
        if (
            media is not None
            and media_id.media_type == MediaType.tv
            and season_number is not None
            and media.season_number == season_number
        ):
            use_simple_snapshot = True
        if media is not None and media_id.media_type == MediaType.tv and use_simple_snapshot:
            media = apply_media_season_context(media, season_number)
        simple_snapshot = None
        if media is not None and use_simple_snapshot:
            simple_snapshot = MediaExecutionSnapshot.model_validate(media)
            if not include_schedule_snapshot and (media_id.media_type != MediaType.tv or not require_episode_count or simple_snapshot.episodes_count):
                return simple_snapshot

        full_media = await self.profile_service.cached_info(media_id)
        if full_media is None:
            if simple_snapshot is not None and (media_id.media_type != MediaType.tv or not require_episode_count or simple_snapshot.episodes_count):
                return simple_snapshot
            raise MediaNotFoundException()
        if media_id.media_type == MediaType.tv:
            full_media = self._apply_cached_tv_season_context(
                full_media,
                season_number,
                require_episode_count=require_episode_count,
            )
        snapshot = MediaExecutionSnapshot.model_validate(full_media)
        if media_id.media_type == MediaType.tv and require_episode_count and not snapshot.episodes_count:
            raise DownloadException("backendErrors.mediaExecutionSnapshotEpisodeCountMissing")
        return snapshot
