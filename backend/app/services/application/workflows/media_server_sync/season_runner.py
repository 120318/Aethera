from app.schemas.config import JellyfinConfig, MediaServerSyncConfig
from app.schemas.domain.event import EventType
from app.schemas.domain.library import LibraryFile, LibraryFileArtifactStatus
from app.schemas.domain.media import MediaFullInfo
from app.schemas.domain.media_server_sync import MediaServerChangeType, MediaServerSyncState, MediaServerSyncTargetFile
from app.schemas.media_id import MediaID
from app.services.application.workflows.media_server_sync.artifacts import media_server_sync_artifacts
from app.services.application.workflows.media_server_sync.needs import media_server_sync_needs
from app.services.application.workflows.media_server_sync.pipeline import media_server_sync_pipeline
from app.services.application.workflows.media_server_sync.state import media_server_sync_state
from app.services.audit.workflow_event_emitters import emit_media_server_sync_events
from app.services.domain.library.service import library_service
from app.services.domain.media import media_service


class MediaServerSyncSeasonRunner:
    async def sync_one_season(
        self,
        media_server: JellyfinConfig,
        media_id: MediaID,
        season_number: int | None,
        files: list[LibraryFile],
        state: MediaServerSyncState,
        now: float,
        sync_cfg: MediaServerSyncConfig,
    ) -> bool:
        media = await media_service.info(media_id, season_number=season_number)
        if not media:
            raise ValueError("media not found")
        layout = await library_service.get_media_layout_for_files(media_id, files)
        needs = await media_server_sync_needs.detect(media, state, sync_cfg, layout)
        if not needs.should_run:
            if sync_cfg.write_nfo:
                await media_server_sync_artifacts.mark_nfo_artifacts(
                    files,
                    media,
                    needs.anchor_file,
                    needs.transfer_results,
                    needs.media_root_dir,
                    LibraryFileArtifactStatus.succeeded,
                )
            if sync_cfg.download_images:
                await media_server_sync_artifacts.mark_image_artifacts(
                    files,
                    media,
                    needs.anchor_file,
                    needs.media_root_dir,
                    LibraryFileArtifactStatus.succeeded,
                )
            media_server_sync_state.record_checked(state, needs, now, sync_cfg)
            return False
        if sync_cfg.write_nfo:
            await media_server_sync_artifacts.mark_nfo_artifacts(
                files,
                media,
                needs.anchor_file,
                needs.transfer_results,
                needs.media_root_dir,
                LibraryFileArtifactStatus.pending,
            )
        if sync_cfg.download_images:
            await media_server_sync_artifacts.mark_image_artifacts(
                files,
                media,
                needs.anchor_file,
                needs.media_root_dir,
                LibraryFileArtifactStatus.pending,
            )
        emit_media_server_sync_events(
            EventType.MEDIA_SERVER_SYNC_STARTED,
            media,
            needs.anchor_file or "",
            needs.transfer_results,
            media_server.id,
            trigger="scheduler",
        )
        try:
            await self.apply_updates(media_server, media, needs.anchor_file, needs.transfer_results, needs.media_root_dir)
        except ValueError as exc:
            emit_media_server_sync_events(
                EventType.MEDIA_SERVER_SYNC_FAILED,
                media,
                needs.anchor_file or "",
                needs.transfer_results,
                media_server.id,
                trigger="scheduler",
                error=str(exc),
            )
            raise
        emit_media_server_sync_events(
            EventType.MEDIA_SERVER_SYNC_COMPLETED,
            media,
            needs.anchor_file or "",
            needs.transfer_results,
            media_server.id,
            trigger="scheduler",
        )
        if sync_cfg.write_nfo:
            await media_server_sync_artifacts.mark_nfo_artifacts(
                files,
                media,
                needs.anchor_file,
                needs.transfer_results,
                needs.media_root_dir,
                LibraryFileArtifactStatus.succeeded,
            )
        if sync_cfg.download_images:
            await media_server_sync_artifacts.mark_image_artifacts(
                files,
                media,
                needs.anchor_file,
                needs.media_root_dir,
                LibraryFileArtifactStatus.succeeded,
            )
        media_server_sync_state.record_success(state, needs, now, sync_cfg)
        return True

    async def apply_updates(
        self,
        media_server: JellyfinConfig,
        media: MediaFullInfo,
        anchor_file: str | None,
        transfer_results: list[MediaServerSyncTargetFile],
        media_root_dir: str | None,
    ) -> None:
        if not anchor_file:
            raise ValueError("missing anchor file")
        await media_server_sync_pipeline.run(
            media,
            anchor_file,
            transfer_results,
            media_server.sync,
            media_server=media_server,
            media_root_dir=media_root_dir,
            change_type=MediaServerChangeType.UPDATED,
        )


media_server_sync_season_runner = MediaServerSyncSeasonRunner()
