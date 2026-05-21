import asyncio
import json
import logging
import time

from app.schemas.config import JellyfinConfig, MediaServerSyncConfig
from app.schemas.constants.event_types import EventTypes
from app.schemas.domain.action import ActionSource
from app.schemas.domain.addon_events import MediaDeletedEventMeta, MediaImportCompletedEventMeta
from app.schemas.domain.event import Event, EventType
from app.schemas.domain.library import LibraryFile, LibraryFileArtifactStatus
from app.schemas.domain.media import MediaFullInfo
from app.schemas.domain.media_server_sync import (
    MediaServerChange,
    MediaServerChangeType,
    MediaServerSyncItemResult,
    MediaServerSyncRunResult,
    MediaServerSyncTargetFile,
)
from app.schemas.media_id import MediaID
from app.services.application.events.consumer import event_consumer_service
from app.services.application.workflows.scoped_seasons import (
    event_season_number,
    library_files_for_season,
    library_files_season_number,
    library_files_season_numbers,
    positive_season_number,
)
from app.services.application.workflows.media_server_sync.artifacts import media_server_sync_artifacts
from app.services.application.workflows.media_server_sync.config import media_server_sync_config
from app.services.application.workflows.media_server_sync.pipeline import media_server_sync_pipeline
from app.services.application.workflows.media_server_sync.season_runner import media_server_sync_season_runner
from app.services.application.workflows.media_server_sync.state import media_server_sync_state
from app.services.application.workflows.media_server_sync.target import media_server_sync_target
from app.services.audit.workflow_event_emitters import emit_media_server_sync_events
from app.services.domain.library.service import library_service
from app.services.domain.media import media_service
from app.utils.library_paths import build_library_file_path

logger = logging.getLogger("app.media_server_sync.service")


class MediaServerSyncService:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()

    def register(self) -> None:
        event_consumer_service.register(
            name="media_server_sync",
            patterns=[EventTypes.MEDIA_IMPORT_COMPLETED],
            handler=self.handle_event,
            source_type=ActionSource.system,
        )
        event_consumer_service.register(
            name="media_server_sync_delete",
            patterns=[EventTypes.MEDIA_DELETED],
            handler=self.handle_event,
            source_type=ActionSource.system,
        )

    async def handle_event(self, event: Event) -> None:
        if event.type == EventTypes.MEDIA_IMPORT_COMPLETED:
            await self.handle_import_completed(event)
            return
        if event.type == EventTypes.MEDIA_DELETED:
            await self.handle_deleted(event)

    async def handle_import_completed(self, event: Event) -> None:
        context = MediaImportCompletedEventMeta.model_validate(json.loads(event.meta) if event.meta else {})
        season_number = event_season_number(event, context.media_id)
        if context.media_id.media_type.value == "tv" and season_number is None:
            library_files = await library_service.get_files_by_task(context.task_id)
            season_number = library_files_season_number(library_files)
        if context.media_id.media_type.value == "tv" and season_number is None:
            logger.warning("Missing season for media import event: %s", context.media_id)
            return
        media_info = await media_service.info(context.media_id, season_number=season_number)
        if not media_info:
            logger.warning("Missing media_info for media import event: %s", context.media_id)
            return

        layout = await library_service.get_media_layout(context.media_id)
        sync_input = media_server_sync_target.build_input(media_info, layout)
        imported_results = [
            MediaServerSyncTargetFile(
                destination_path=item.destination_path,
                episode_number=item.episode_number,
            )
            for item in context.imported_files
        ]

        file_path = context.file_path or (sync_input.anchor_file if sync_input else "")
        transfer_results = imported_results or (sync_input.transfer_results if sync_input else [])
        media_root_dir = media_server_sync_target.resolve_media_root_dir_from_targets(
            media_info,
            file_path,
            transfer_results,
            sync_input.media_root_dir if sync_input else None,
        )
        if not file_path:
            logger.warning("Missing sync anchor file for media import event: %s", context.media_id)
            return

        media_server = media_server_sync_config.resolve_server_for_directory_id(context.directory_id)
        if media_server is None or not media_server.sync.enabled:
            return
        try:
            existing_state = media_server_sync_state.fetch_state(media_server.id, media_info.media_id)
            change_type = (
                MediaServerChangeType.CREATED
                if existing_state is None or not existing_state.last_success_at
                else MediaServerChangeType.UPDATED
            )
            emit_media_server_sync_events(
                EventType.MEDIA_SERVER_SYNC_STARTED,
                media_info,
                file_path,
                transfer_results,
                media_server.id,
                trigger="import",
                task_id=event.task_id,
            )
            await media_server_sync_pipeline.run(
                media_info,
                file_path,
                transfer_results,
                media_server.sync,
                media_server=media_server,
                media_root_dir=media_root_dir,
                change_type=change_type,
            )
            emit_media_server_sync_events(
                EventType.MEDIA_SERVER_SYNC_COMPLETED,
                media_info,
                file_path,
                transfer_results,
                media_server.id,
                trigger="import",
                task_id=event.task_id,
            )
            media_server_sync_state.touch_state(media_info, media_server.id, time.time())
        except ValueError as exc:
            emit_media_server_sync_events(
                EventType.MEDIA_SERVER_SYNC_FAILED,
                media_info,
                file_path,
                transfer_results,
                media_server.id,
                trigger="import",
                task_id=event.task_id,
                error=str(exc),
            )
            logger.exception("Failed to sync media server metadata for %s: %s", media_info.title, exc)

    async def handle_deleted(self, event: Event) -> None:
        context = MediaDeletedEventMeta.model_validate(json.loads(event.meta) if event.meta else {})
        if not context.media_id or not context.paths:
            return

        season_number = event_season_number(event, context.media_id)
        if context.media_id.media_type.value == "tv" and season_number is None:
            logger.warning("Missing season for media delete event: %s", context.media_id)
            return
        media_info = await media_service.info(context.media_id, season_number=season_number)
        if not media_info:
            logger.warning("Missing media_info for media delete event: %s", context.media_id)
            return

        media_server = media_server_sync_config.resolve_server_for_directory_id(context.directory_id)
        if media_server is None or not media_server.sync.enabled:
            return

        changes = [
            MediaServerChange(
                media_id=context.media_id,
                target_path=(context.media_root_dir if context.delete_scope == "media_root" and context.media_root_dir else path),
                change_type=MediaServerChangeType.DELETED,
                is_media_root=(context.delete_scope == "media_root"),
                reason=f"media_deleted:{context.delete_scope}",
            )
            for path in context.paths
        ]
        if context.delete_scope == "media_root" and context.media_root_dir:
            changes = changes[:1]

        try:
            await media_server_sync_pipeline.apply_media_server_changes(
                media_server=media_server,
                changes=changes,
            )
        except ValueError as exc:
            logger.exception("Failed to sync media server delete for %s: %s", media_info.title, exc)

    async def run_incremental_once(self) -> MediaServerSyncRunResult:
        enabled_servers = media_server_sync_config.list_enabled_servers()
        if not enabled_servers:
            return MediaServerSyncRunResult(skipped=True, reason="no_enabled_media_servers")
        if self._lock.locked():
            return MediaServerSyncRunResult(skipped=True, reason="locked")

        async with self._lock:
            start_ts = time.time()
            results = MediaServerSyncRunResult()
            for media_server in enabled_servers:
                server_result = await self._run_server_once(media_server, start_ts)
                results.processed += server_result.processed
                results.updated += server_result.updated
                results.failed += server_result.failed
            if results.processed == 0 and results.updated == 0 and results.failed == 0:
                return MediaServerSyncRunResult(skipped=True, reason="no_due")
            results.elapsed_seconds = round(time.time() - start_ts, 3)
            return results

    async def refresh_media_server(
        self,
        media: MediaFullInfo,
        file_path: str,
        transfer_results: list[MediaServerSyncTargetFile] | None = None,
    ) -> None:
        library_file = await library_service.find_file_by_path(file_path)
        media_server = (
            media_server_sync_config.resolve_server_for_directory_id(library_file.directory_id)
            if library_file
            else None
        )
        await media_server_sync_pipeline.refresh_media_server(media, file_path, transfer_results, media_server=media_server)

    async def rerun_for_task(self, task_id: str, season_number: int | None = None) -> int:
        library_files = await library_service.get_files_by_task(task_id)
        return await self.rerun_for_library_files(library_files, season_number=season_number)

    async def can_rerun_for_library_files(self, library_files: list[LibraryFile]) -> bool:
        target_files = self._rerun_target_files(library_files)
        if not target_files:
            return False
        return any(
            media_server is not None and media_server.sync.enabled
            for media_server in (
                media_server_sync_config.resolve_server_for_directory_id(directory_id)
                for directory_id in self._directory_ids_for_files(library_files)
            )
        )

    async def rerun_for_library_files(self, library_files: list[LibraryFile], *, season_number: int | None = None) -> int:
        target_files = self._rerun_target_files(library_files)
        if not target_files:
            raise ValueError("No imported library files are available for scraping")
        resolved_season_number = (
            positive_season_number(season_number) or library_files_season_number(library_files)
        )
        if library_files[0].media_id.media_type.value != "tv":
            resolved_season_number = None
        elif resolved_season_number is None:
            raise ValueError("TV media server sync requires a season")
        media = await media_service.info(library_files[0].media_id, season_number=resolved_season_number)
        if not media:
            raise ValueError("Media profile does not exist")
        count = 0
        for directory_id, files in self._group_files_by_directory_id(library_files).items():
            grouped_targets = self._rerun_target_files(files)
            if not grouped_targets:
                continue
            media_server = media_server_sync_config.resolve_server_for_directory_id(directory_id)
            if media_server is None or not media_server.sync.enabled:
                continue
            file_path = grouped_targets[0].destination_path
            media_root_dir = media_server_sync_target.resolve_media_root_dir_from_targets(
                media,
                file_path,
                grouped_targets,
                None,
            )
            if media_server.sync.write_nfo:
                await media_server_sync_artifacts.mark_nfo_artifacts(
                    files,
                    media,
                    file_path,
                    grouped_targets,
                    str(media_root_dir),
                    LibraryFileArtifactStatus.pending,
                )
            if media_server.sync.download_images:
                await media_server_sync_artifacts.mark_image_artifacts(
                    files,
                    media,
                    file_path,
                    str(media_root_dir),
                    LibraryFileArtifactStatus.pending,
                )
            emit_media_server_sync_events(
                EventType.MEDIA_SERVER_SYNC_STARTED,
                media,
                file_path,
                grouped_targets,
                media_server.id,
                trigger="manual",
            )
            try:
                await media_server_sync_pipeline.run(
                    media,
                    file_path,
                    grouped_targets,
                    media_server.sync,
                    media_server=media_server,
                    media_root_dir=media_root_dir,
                    change_type=MediaServerChangeType.UPDATED,
                )
            except ValueError as exc:
                emit_media_server_sync_events(
                    EventType.MEDIA_SERVER_SYNC_FAILED,
                    media,
                    file_path,
                    grouped_targets,
                    media_server.id,
                    trigger="manual",
                    error=str(exc),
                )
                raise
            emit_media_server_sync_events(
                EventType.MEDIA_SERVER_SYNC_COMPLETED,
                media,
                file_path,
                grouped_targets,
                media_server.id,
                trigger="manual",
            )
            if media_server.sync.write_nfo:
                await media_server_sync_artifacts.mark_nfo_artifacts(
                    files,
                    media,
                    file_path,
                    grouped_targets,
                    str(media_root_dir),
                    LibraryFileArtifactStatus.succeeded,
                )
            if media_server.sync.download_images:
                await media_server_sync_artifacts.mark_image_artifacts(
                    files,
                    media,
                    file_path,
                    str(media_root_dir),
                    LibraryFileArtifactStatus.succeeded,
                )
            media_server_sync_state.touch_state(media, media_server.id, time.time())
            count += len(grouped_targets)
        if count == 0:
            raise ValueError("Target media library scraping is not enabled")
        return count

    def _rerun_target_files(self, library_files: list[LibraryFile]) -> list[MediaServerSyncTargetFile]:
        return [
            MediaServerSyncTargetFile(
                destination_path=str(build_library_file_path(library_file.path, library_file.file_name)),
                episode_number=self._episode_number_for_library_file(library_file),
            )
            for library_file in library_files
            if library_service.is_primary_file(library_file) and library_service.file_exists(library_file)
        ]

    @staticmethod
    def _group_files_by_directory_id(library_files: list[LibraryFile]) -> dict[str, list[LibraryFile]]:
        grouped: dict[str, list[LibraryFile]] = {}
        for library_file in library_files:
            if library_file.directory_id:
                grouped.setdefault(library_file.directory_id, []).append(library_file)
        return grouped

    def _directory_ids_for_files(self, library_files: list[LibraryFile]) -> list[str]:
        return sorted(self._group_files_by_directory_id(library_files))

    @staticmethod
    def _episode_number_for_library_file(library_file: LibraryFile) -> int | None:
        attrs = library_file.resource_attributes
        episodes = list(attrs.episodes or []) if attrs else []
        return int(episodes[0]) if len(episodes) == 1 else None

    async def _run_server_once(
        self,
        media_server: JellyfinConfig,
        start_ts: float,
    ) -> MediaServerSyncRunResult:
        sync_cfg = media_server.sync
        now = start_ts
        due = media_server_sync_state.list_due_ids(media_server.id, now, limit=sync_cfg.batch_size)
        if len(due) < sync_cfg.batch_size:
            media_server_sync_state.bootstrap_due_queue(
                media_server.id,
                await self._collect_candidates(media_server.id),
                now,
                sync_cfg.batch_size - len(due),
                sync_cfg.interval_hours,
            )
            due = media_server_sync_state.list_due_ids(media_server.id, now, limit=sync_cfg.batch_size)
        if not due:
            return MediaServerSyncRunResult()

        concurrency = max(1, min(sync_cfg.batch_size, 4))
        semaphore = asyncio.Semaphore(concurrency)
        results = MediaServerSyncRunResult()
        tasks = [
            asyncio.create_task(
                self._run_sync_task(semaphore, media_server, media_id, now, sync_cfg)
            )
            for media_id in due
        ]
        for future in asyncio.as_completed(tasks):
            out = await future
            results.processed += 1
            if out.updated:
                results.updated += 1
            if out.failed:
                results.failed += 1
        return results

    async def _run_sync_task(
        self,
        semaphore: asyncio.Semaphore,
        media_server: JellyfinConfig,
        media_id: MediaID,
        now: float,
        sync_cfg: MediaServerSyncConfig,
    ) -> MediaServerSyncItemResult:
        async with semaphore:
            return await self._sync_one(media_server, media_id, now, sync_cfg)

    async def _collect_candidates(self, media_server_id: str) -> list[MediaID]:
        directory_ids = media_server_sync_config.directory_ids_for_media_server(media_server_id)
        return sorted(await library_service.list_media_ids_by_directory_ids(directory_ids), key=str)

    async def _sync_one(
        self,
        media_server: JellyfinConfig,
        media_id: MediaID,
        now: float,
        sync_cfg: MediaServerSyncConfig,
    ) -> MediaServerSyncItemResult:
        state = media_server_sync_state.get_or_create_state(media_server.id, media_id)
        out = MediaServerSyncItemResult(media_server_id=media_server.id, media_id=media_id)
        try:
            directory_ids = media_server_sync_config.directory_ids_for_media_server(media_server.id)
            files = await library_service.get_files_by_media_and_directory_ids(media_id, directory_ids)
            season_numbers = library_files_season_numbers(files) if media_id.media_type.value == "tv" else [0]
            if media_id.media_type.value == "tv" and not season_numbers:
                raise ValueError("TV media server sync requires a season")
            for season_number in season_numbers:
                scoped_files = library_files_for_season(files, season_number) if media_id.media_type.value == "tv" else files
                season_updated = await media_server_sync_season_runner.sync_one_season(
                    media_server,
                    media_id,
                    season_number if media_id.media_type.value == "tv" else None,
                    scoped_files,
                    state,
                    now,
                    sync_cfg,
                )
                out.updated = out.updated or season_updated
            return out
        except ValueError as exc:
            out.failed = True
            media_server_sync_state.record_failure(state, exc, now, sync_cfg)
            return out

media_server_sync_service = MediaServerSyncService()


async def run_incremental_sync_once() -> MediaServerSyncRunResult:
    return await media_server_sync_service.run_incremental_once()


def register_media_server_sync() -> None:
    media_server_sync_service.register()


async def refresh_media_server(
    media: MediaFullInfo,
    file_path: str,
    transfer_results: list[MediaServerSyncTargetFile] | None = None,
) -> None:
    await media_server_sync_service.refresh_media_server(media, file_path, transfer_results)
