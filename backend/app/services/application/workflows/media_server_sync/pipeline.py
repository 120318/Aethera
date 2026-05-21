import logging
from pathlib import Path

from app.schemas.config import JellyfinConfig, MediaServerSyncConfig
from app.schemas.domain.media import MediaFullInfo
from app.schemas.domain.media_server_sync import MediaServerChange, MediaServerChangeType, MediaServerSyncTargetFile
from app.services.application.workflows.media_server_sync.nfo_plan import media_server_sync_nfo_plan
from app.services.application.workflows.media_server_sync.target import media_server_sync_target
from app.services.domain.media import media_service
from app.services.integration.media_server import media_server_gateway
from app.services.integration.tmdb.images import to_tmdb_image_url
from app.utils.http_file import download_url_to_file

logger = logging.getLogger("app.media_server_sync.pipeline")


class MediaServerSyncPipeline:
    async def run(
        self,
        media: MediaFullInfo,
        file_path: str,
        transfer_results: list[MediaServerSyncTargetFile] | None,
        sync_cfg: MediaServerSyncConfig,
        *,
        media_server: JellyfinConfig,
        media_root_dir: str | None,
        change_type: MediaServerChangeType,
    ) -> None:
        normalized_results = transfer_results or []
        if sync_cfg.fetch_metadata:
            await self._enrich_media_by_primary_source(media)
        if sync_cfg.write_nfo:
            await media_server_sync_nfo_plan.write_nfo_files(
                media,
                file_path,
                normalized_results,
                media_root_dir=media_root_dir,
            )
        if sync_cfg.download_images:
            await self._download_images(media, file_path, normalized_results, media_root_dir=media_root_dir)
        if sync_cfg.refresh_after_sync:
            await self.refresh_media_server(
                media,
                file_path,
                normalized_results,
                media_server=media_server,
                media_root_dir=media_root_dir,
                change_type=change_type,
            )

    async def refresh_media_server(
        self,
        media: MediaFullInfo,
        file_path: str,
        transfer_results: list[MediaServerSyncTargetFile] | None = None,
        *,
        media_server: JellyfinConfig | None = None,
        media_root_dir: str | None = None,
        change_type: MediaServerChangeType = MediaServerChangeType.UPDATED,
    ) -> None:
        if media_server is None:
            return

        target_dir = Path(media_root_dir) if media_root_dir else media_server_sync_target.resolve_media_root_dir(media, file_path, transfer_results)
        await self.apply_media_server_changes(
            media_server=media_server,
            changes=[
                MediaServerChange(
                    media_id=media.media_id,
                    target_path=str(target_dir),
                    change_type=change_type,
                    is_media_root=True,
                    reason="media_sync_refresh",
                )
            ],
        )

    async def apply_media_server_changes(
        self,
        *,
        media_server: JellyfinConfig,
        changes: list[MediaServerChange],
    ) -> bool:
        return await media_server_gateway.apply_changes(media_server, changes)

    async def _download_images(
        self,
        media: MediaFullInfo,
        file_path: str,
        transfer_results: list[MediaServerSyncTargetFile] | None = None,
        media_root_dir: str | None = None,
    ) -> None:
        target_dir = Path(media_root_dir) if media_root_dir else media_server_sync_target.resolve_media_root_dir(media, file_path, transfer_results)
        if media.poster_path:
            await download_url_to_file(to_tmdb_image_url(media.poster_path), target_dir / "poster.jpg")
        if media.backdrop_path:
            await download_url_to_file(to_tmdb_image_url(media.backdrop_path), target_dir / "fanart.jpg")
        if media.logo_path:
            await download_url_to_file(to_tmdb_image_url(media.logo_path), target_dir / "logo.png")

    async def _enrich_media_by_primary_source(self, media_info: MediaFullInfo) -> None:
        context = media_service.resolve_media_context(media_info)
        tmdb_id = media_service.tmdb_id_from_media_context(context)
        if context.primary_metadata_source != "tmdb" or not tmdb_id:
            return
        if media_info.media_type.value == "tv" and not media_info.season_number:
            return

        try:
            data = await media_service.info(media_info.media_id, season_number=media_info.season_number)
            if not data:
                return

            media_info.title = data.title or media_info.title
            media_info.original_title = data.original_title or media_info.original_title
            media_info.overview = data.overview or media_info.overview
            media_info.imdb_id = data.imdb_id or media_info.imdb_id
            media_info.tvdb_id = data.tvdb_id or media_info.tvdb_id
            media_info.release_date = data.release_date or media_info.release_date
            media_info.first_air_date = data.first_air_date or media_info.first_air_date
            media_info.duration = data.duration or media_info.duration
            media_info.poster_path = data.poster_path or media_info.poster_path
            media_info.backdrop_path = data.backdrop_path or media_info.backdrop_path
            media_info.logo_path = data.logo_path or media_info.logo_path
            media_info.studios = data.studios or media_info.studios
            media_info.actors = list(data.actors or [])[:15]
            media_info.directors = list(data.directors or [])
        except ValueError as exc:
            logger.warning("Failed to fetch TMDB override for %s: %s", media_info.title, exc)


media_server_sync_pipeline = MediaServerSyncPipeline()
