from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path

from app.core.action_context import action_context, get_current_action_id
from app.schemas.config import DanmuAddonConfig
from app.schemas.media_id import MediaID
from app.schemas.domain.action import (
    ActionActor,
    ActionKind,
    ActionRecord,
    ActionSource,
    ActionStatus,
    ActionTargetType,
    ActionTrigger,
)
from app.schemas.domain.action_meta import DanmuGenerateQueuedActionMeta
from app.schemas.domain.addon_events import ImportedMediaFile, MediaImportCompletedEventMeta
from app.schemas.domain.event import Event, EventType
from app.schemas.domain.library import LibraryFile, LibraryFileArtifact, LibraryFileArtifactStatus, LibraryFileArtifactType
from app.schemas.domain.media import MediaFullInfo
from app.services.audit.action_catalog import ACTION_NAME_DANMU_GENERATE
from app.services.audit.action_service import action_service
from app.services.audit.workflow_event_emitters import emit_danmu_generate_event
from app.services.config.settings_service import settings_service
from app.services.application.workflows.danmu.backfill_policy import is_recently_watchable
from app.services.application.workflows.danmu.duration_guard import danmu_duration_guard
from app.services.application.workflows.danmu.source_resolver import danmu_source_resolver
from app.services.application.workflows.danmu.sidecar_outputs import expected_sidecar_paths, remove_outputs, write_outputs
from app.services.application.workflows.scoped_seasons import (
    event_season_number,
    library_file_season_number,
    library_files_season_number,
    positive_season_number,
)
from app.services.integration.danmu.models import DanmuFetchInput
from app.services.integration.danmu.service import danmu_provider_service
from app.services.application.workflows.media_server_sync import refresh_media_server
from app.utils.library_paths import build_library_file_path

logger = logging.getLogger("app.application.danmu")
DANMU_GENERATION_TIMEOUT_SECONDS = 900


class DanmuApplicationService:
    def config(self) -> DanmuAddonConfig:
        return settings_service.get_addons_config().danmu

    async def can_generate_for_media(self, media_id: MediaID, *, season_number: int | None = None) -> bool:
        config = self.config()
        if not config.enabled or not config.directory_ids:
            return False
        resolved_season_number = positive_season_number(season_number)
        if media_id.media_type.value == "tv" and resolved_season_number is None:
            return False
        media = await danmu_source_resolver.media_with_fetchable_source(
            media_id,
            season_number=resolved_season_number,
            config=config,
        )
        return bool(media and danmu_source_resolver.has_fetchable_vendor(media, config))

    async def handle_event(self, event: Event) -> None:
        if event.type != EventType.MEDIA_IMPORT_COMPLETED:
            return
        config = self.config()
        if not config.enabled or not config.directory_ids:
            return
        try:
            meta = MediaImportCompletedEventMeta.model_validate_json(event.meta)
        except ValueError as exc:
            logger.warning("Danmu skipped: invalid media import meta event=%s error=%s", event.id, exc)
            return
        if not meta.media_id:
            return
        if meta.directory_id not in config.directory_ids:
            return
        from app.services.domain.library.service import library_service

        library_files = await library_service.get_files_by_task(meta.task_id)
        season_number = event_season_number(event, meta.media_id) if meta.media_id.media_type.value == "tv" else None
        if meta.media_id.media_type.value == "tv" and season_number is None:
            season_number = library_files_season_number(library_files)
        if meta.media_id.media_type.value == "tv" and season_number is None:
            logger.warning("Danmu skipped: missing season media=%s", meta.media_id)
            return
        media = await danmu_source_resolver.media_with_fetchable_source(
            meta.media_id,
            season_number=season_number,
            config=config,
        )
        if not media:
            logger.warning("Danmu skipped: media info unavailable media=%s", meta.media_id)
            return
        library_files_by_path = {
            str(build_library_file_path(library_file.path, library_file.file_name)): library_file
            for library_file in library_files
            if library_file.id
        }
        imported_files = meta.imported_files or [
            ImportedMediaFile(destination_path=meta.file_path, episode_number=None)
        ]
        for imported_file in imported_files:
            video_path = Path(imported_file.destination_path)
            if not imported_file.destination_path:
                continue
            await self._generate_for_video(
                media,
                video_path,
                imported_file.episode_number,
                trigger=ActionTrigger.event,
                event=event,
                config=config,
                library_file=library_files_by_path.get(str(video_path)),
            )

    async def run_backfill(self) -> None:
        config = self.config()
        if not config.enabled or not config.backfill_enabled or not config.directory_ids:
            return

        from app.services.domain.library.service import library_service

        files = await library_service.list_files()
        artifacts_by_file_id: dict[str, list[LibraryFileArtifact]] = {}
        artifacts = await library_service.get_artifacts_by_file_ids([library_file.id for library_file in files])
        for artifact in artifacts:
            artifacts_by_file_id.setdefault(artifact.library_file_id, []).append(artifact)
        media_cache: dict[str, MediaFullInfo | None] = {}
        for library_file in files:
            if not library_service.is_primary_file(library_file):
                continue
            if library_file.directory_id not in config.directory_ids:
                continue
            video_path = build_library_file_path(library_file.path, library_file.file_name)
            if not video_path.exists():
                continue
            season_number = library_file_season_number(library_file) if library_file.media_id.media_type.value == "tv" else None
            media_key = f"{library_file.media_id}:season={season_number or ''}"
            if media_key not in media_cache:
                media_cache[media_key] = await danmu_source_resolver.media_with_fetchable_source(
                    library_file.media_id,
                    season_number=season_number,
                    config=config,
                )
            media = media_cache[media_key]
            if not media or not danmu_source_resolver.has_fetchable_vendor(media, config):
                continue
            if not self._should_backfill_video(
                media,
                library_file,
                video_path,
                config,
                artifacts=artifacts_by_file_id.get(library_file.id, []),
            ):
                continue
            await self._generate_for_video(
                media,
                video_path,
                self._episode_number_for_file(library_file),
                trigger=ActionTrigger.scheduler,
                event=None,
                config=config,
                library_file=library_file,
            )

    async def run_for_task(self, task_id: str) -> int:
        config = self.config()
        if not config.enabled or not config.directory_ids:
            raise ValueError("Danmu addon is not enabled or has no bound directories")

        from app.services.domain.library.service import library_service

        library_files = await library_service.get_files_by_task(task_id)
        return await self.run_for_library_files(library_files, task_id=task_id)

    async def run_for_library_files(self, library_files: list[LibraryFile], *, task_id: str | None = None) -> int:
        config = self.config()
        if not config.enabled or not config.directory_ids:
            raise ValueError("Danmu addon is not enabled or has no bound directories")

        from app.services.domain.library.service import library_service

        primary_files = [
            library_file
            for library_file in library_files
            if library_service.is_primary_file(library_file) and library_service.file_exists(library_file)
        ]
        if not primary_files:
            raise ValueError("No imported library files are available for danmu generation")

        season_number = library_files_season_number(primary_files) if primary_files[0].media_id.media_type.value == "tv" else None
        media = await danmu_source_resolver.media_with_fetchable_source(
            primary_files[0].media_id,
            season_number=season_number,
            config=config,
        )
        if not media:
            raise ValueError("Media info does not exist")
        if not danmu_source_resolver.has_fetchable_vendor(media, config):
            raise ValueError("Media has no available danmu source")

        generated = 0
        for library_file in primary_files:
            video_path = build_library_file_path(library_file.path, library_file.file_name)
            if library_file.directory_id not in config.directory_ids:
                continue
            if await self._generate_for_video(
                media,
                video_path,
                self._episode_number_for_file(library_file),
                trigger=ActionTrigger.manual,
                event=None,
                config=config,
                task_id=task_id or library_file.task_id,
                library_file=library_file,
            ):
                generated += 1
        if generated == 0:
            raise ValueError("No danmu files were generated")
        return generated

    async def can_run_for_library_files(self, library_files: list[LibraryFile], *, media: MediaFullInfo | None = None) -> bool:
        config = self.config()
        if not config.enabled or not config.directory_ids:
            return False

        from app.services.domain.library.service import library_service

        primary_files = [
            library_file
            for library_file in library_files
            if library_service.is_primary_file(library_file) and library_service.file_exists(library_file)
        ]
        if not primary_files:
            return False

        season_number = library_files_season_number(primary_files) if primary_files[0].media_id.media_type.value == "tv" else None
        resolved_media = media or await danmu_source_resolver.media_with_fetchable_source(
            primary_files[0].media_id,
            season_number=season_number,
            config=config,
        )
        if not resolved_media or not danmu_source_resolver.has_fetchable_vendor(resolved_media, config):
            return False

        return any(library_file.directory_id in config.directory_ids for library_file in primary_files)

    async def _generate_for_video(
        self,
        media: MediaFullInfo,
        video_path: Path,
        episode_number: int | None,
        *,
        trigger: ActionTrigger,
        event: Event | None,
        config: DanmuAddonConfig,
        task_id: str | None = None,
        library_file: LibraryFile | None = None,
    ) -> bool:
        if not danmu_source_resolver.has_fetchable_vendor(media, config):
            return False
        action_id, owns_action = self._resolve_generation_action(
            event=event,
            trigger=trigger,
            media=media,
            video_path=str(video_path),
            episode_number=episode_number,
            task_id=task_id,
        )
        if owns_action:
            action_service.mark_running(action_id, started_at=datetime.now())
        event_task_id = task_id or (event.task_id if event else None)
        try:
            await self._mark_danmu_artifacts(library_file, video_path, config, LibraryFileArtifactStatus.pending)
            emit_danmu_generate_event(EventType.DANMU_GENERATE_STARTED, media, video_path, episode_number, action_id, event_task_id)
            async with asyncio.timeout(DANMU_GENERATION_TIMEOUT_SECONDS):
                with action_context(action_id):
                    result = await danmu_provider_service.fetch(
                        media.vendors,
                        DanmuFetchInput(
                            media_type=media.media_type,
                            episode_number=episode_number,
                            absolute_episode_number=self._absolute_episode_number(
                                media,
                                self._season_number_for_file(library_file) if library_file else media.season_number,
                                episode_number,
                            ),
                            episode_count=media.episodes_count,
                            title=media.title,
                            season_number=self._season_number_for_file(library_file) if library_file else media.season_number,
                        ),
                        config.providers,
                    )
                    if not result or not result.comments:
                        await self._mark_danmu_artifacts(
                            library_file,
                            video_path,
                            config,
                            LibraryFileArtifactStatus.skipped,
                        )
                        if owns_action:
                            action_service.mark_skipped(action_id, message_params={"reason": "no_danmu"})
                        logger.info("Danmu skipped: no comments returned path=%s", video_path)
                        emit_danmu_generate_event(
                            EventType.DANMU_GENERATE_FAILED,
                            media,
                            video_path,
                            episode_number,
                            action_id,
                            event_task_id,
                            provider=result.provider if result else None,
                            error_key="runtimeReasons.danmuNotFound",
                        )
                        return False
                    if await danmu_duration_guard.has_duration_mismatch(video_path, result, config):
                        remove_outputs(video_path, config)
                        await self._mark_danmu_artifacts(
                            library_file,
                            video_path,
                            config,
                            LibraryFileArtifactStatus.skipped,
                            last_error="duration_mismatch",
                        )
                        if owns_action:
                            action_service.mark_skipped(action_id, message_params={"reason": "duration_mismatch"})
                        emit_danmu_generate_event(
                            EventType.DANMU_GENERATE_FAILED,
                            media,
                            video_path,
                            episode_number,
                            action_id,
                            event_task_id,
                            provider=result.provider,
                            error_key="runtimeReasons.danmuDurationMismatch",
                        )
                        return False
                    xml_path, ass_path = write_outputs(video_path, result, config)
                    await self._mark_written_danmu_artifacts(library_file, xml_path, ass_path)
                    logger.info(
                        "Danmu generated: provider=%s path=%s xml=%s ass=%s",
                        result.provider,
                        video_path,
                        xml_path,
                        ass_path,
                    )
                    await self._refresh_media_server(media, video_path)
                    emit_danmu_generate_event(
                        EventType.DANMU_GENERATE_COMPLETED,
                        media,
                        video_path,
                        episode_number,
                        action_id,
                        event_task_id,
                        provider=result.provider,
                        xml_path=xml_path,
                        ass_path=ass_path,
                    )
            if owns_action:
                action_service.mark_completed(action_id)
            return True
        except TimeoutError:
            error = f"danmu generation timed out after {DANMU_GENERATION_TIMEOUT_SECONDS} seconds"
            logger.warning("Danmu generation timed out: path=%s", video_path)
            await self._mark_danmu_artifacts(library_file, video_path, config, LibraryFileArtifactStatus.failed, last_error=error)
            if owns_action:
                action_service.mark_failed(action_id, error=error)
            emit_danmu_generate_event(
                EventType.DANMU_GENERATE_FAILED,
                media,
                video_path,
                episode_number,
                action_id,
                event_task_id,
                error=error,
            )
            return False
        except asyncio.CancelledError:
            logger.warning("Danmu generation cancelled: path=%s", video_path)
            await self._mark_danmu_artifacts(library_file, video_path, config, LibraryFileArtifactStatus.failed, last_error="cancelled")
            if owns_action:
                action_service.mark_failed(action_id, error="cancelled")
            emit_danmu_generate_event(
                EventType.DANMU_GENERATE_FAILED,
                media,
                video_path,
                episode_number,
                action_id,
                event_task_id,
                error="cancelled",
            )
            raise
        except Exception as exc:
            logger.exception("Danmu generation failed: path=%s", video_path)
            await self._mark_danmu_artifacts(library_file, video_path, config, LibraryFileArtifactStatus.failed, last_error=str(exc))
            if owns_action:
                action_service.mark_failed(action_id, error=str(exc))
            emit_danmu_generate_event(
                EventType.DANMU_GENERATE_FAILED,
                media,
                video_path,
                episode_number,
                action_id,
                event_task_id,
                error=str(exc),
            )
            return False

    def _should_backfill_video(
        self,
        media: MediaFullInfo,
        library_file: LibraryFile,
        video_path: Path,
        config: DanmuAddonConfig,
        *,
        artifacts: list[LibraryFileArtifact] | None = None,
    ) -> bool:
        expected_paths = expected_sidecar_paths(video_path, config)
        if not expected_paths or all(path.exists() for path in expected_paths):
            return False
        if self._has_skipped_artifacts_for_expected_paths(video_path, config, artifacts or []):
            return False
        return is_recently_watchable(media, library_file, config.backfill_recent_days)

    def _has_skipped_artifacts_for_expected_paths(
        self,
        video_path: Path,
        config: DanmuAddonConfig,
        artifacts: list[LibraryFileArtifact],
    ) -> bool:
        expected_paths = {str(path) for path in expected_sidecar_paths(video_path, config)}
        if not expected_paths:
            return False
        artifacts_by_path = {artifact.expected_path: artifact for artifact in artifacts}
        return all(
            (artifact := artifacts_by_path.get(path)) is not None
            and artifact.status == LibraryFileArtifactStatus.skipped
            for path in expected_paths
        )

    async def _mark_danmu_artifacts(
        self,
        library_file: LibraryFile | None,
        video_path: Path,
        config: DanmuAddonConfig,
        status: LibraryFileArtifactStatus,
        *,
        last_error: str | None = None,
    ) -> None:
        if not library_file:
            return
        from app.services.domain.library.service import library_service

        for path in expected_sidecar_paths(video_path, config):
            artifact_type = LibraryFileArtifactType.danmu_xml if path.suffix == ".xml" else LibraryFileArtifactType.danmu_ass
            await library_service.mark_artifact(
                library_file_id=library_file.id,
                artifact_type=artifact_type,
                expected_path=str(path),
                status=status,
                last_error=last_error,
            )

    async def _mark_written_danmu_artifacts(
        self,
        library_file: LibraryFile | None,
        xml_path: Path | None,
        ass_path: Path | None,
    ) -> None:
        if not library_file:
            return
        from app.services.domain.library.service import library_service

        if xml_path:
            await library_service.mark_artifact(
                library_file_id=library_file.id,
                artifact_type=LibraryFileArtifactType.danmu_xml,
                expected_path=str(xml_path),
                status=LibraryFileArtifactStatus.succeeded,
            )
        if ass_path:
            await library_service.mark_artifact(
                library_file_id=library_file.id,
                artifact_type=LibraryFileArtifactType.danmu_ass,
                expected_path=str(ass_path),
                status=LibraryFileArtifactStatus.succeeded,
            )

    @staticmethod
    def _episode_number_for_file(library_file: LibraryFile) -> int | None:
        attrs = library_file.resource_attributes
        episodes = list(attrs.episodes or []) if attrs else []
        return int(episodes[0]) if len(episodes) == 1 else None

    @staticmethod
    def _season_number_for_file(library_file: LibraryFile) -> int | None:
        attrs = library_file.resource_attributes
        seasons = list(attrs.seasons or []) if attrs else []
        return int(seasons[0]) if len(seasons) == 1 else None

    @staticmethod
    def _absolute_episode_number(media: MediaFullInfo, season_number: int | None, episode_number: int | None) -> int | None:
        if not season_number or not episode_number or season_number <= 1:
            return episode_number
        previous_count = 0
        for season in sorted(media.seasons, key=lambda item: int(item.season_number or 0)):
            current_season = int(season.season_number or 0)
            if current_season <= 0 or current_season >= season_number:
                continue
            count = season.episode_count_override or season.episode_count
            if not count or int(count) <= 0:
                return episode_number
            previous_count += int(count)
        return previous_count + int(episode_number) if previous_count else episode_number

    async def _refresh_media_server(self, media: MediaFullInfo, video_path: Path) -> None:
        try:
            await refresh_media_server(media, str(video_path))
        except Exception as exc:
            logger.warning(
                "Danmu media server refresh failed: media=%s path=%s error=%s",
                media.media_id,
                video_path,
                exc,
            )

    def _resolve_generation_action(
        self,
        *,
        event: Event | None,
        trigger: ActionTrigger,
        media: MediaFullInfo,
        video_path: str,
        episode_number: int | None,
        task_id: str | None = None,
    ) -> tuple[str, bool]:
        current_action_id = get_current_action_id()
        if trigger == ActionTrigger.manual and current_action_id:
            return current_action_id, False
        return self._create_action(
            event=event,
            trigger=trigger,
            media=media,
            video_path=video_path,
            episode_number=episode_number,
            task_id=task_id,
        ).id, True

    def _create_action(
        self,
        *,
        event: Event | None,
        trigger: ActionTrigger,
        media: MediaFullInfo,
        video_path: str,
        episode_number: int | None,
        task_id: str | None = None,
    ) -> ActionRecord:
        return action_service.create_action(
            kind=ActionKind.addon,
            action_name=ACTION_NAME_DANMU_GENERATE,
            status=ActionStatus.queued,
            actor=ActionActor.system,
            trigger=trigger,
            source=ActionSource.addon,
            target_type=ActionTargetType.danmu_sidecar,
            target_id=video_path,
            media=media,
            task_id=task_id or (event.task_id if event else None),
            subscription_id=event.subscription_id if event else None,
            correlation_id=event.correlation_id if event else None,
            meta=DanmuGenerateQueuedActionMeta(
                video_path=video_path,
                episode_number=episode_number,
                trigger_event_type=event.type if event else None,
                trigger_event_id=event.id if event else None,
            ),
        )


danmu_application_service = DanmuApplicationService()
