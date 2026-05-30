from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.schemas.constants.event_types import EventTypes
from app.schemas.domain.command import CommandCreateRequest, CommandInitiator, CommandType, PilotEpisodeCommandRequestPayload
from app.schemas.domain.download import DownloadTaskCreateInput
from app.schemas.domain.event import EventActor, EventEntityRef, EventLevel, EventSource, MediaEventCreate
from app.schemas.domain.media import MediaExecutionSnapshot, MediaTarget
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.resource_search import MediaSearchQuery
from app.schemas.domain.subscription import SubscriptionUnmatchedRule
from app.schemas.exception import DownloadException
from app.schemas.exception.base import AppException
from app.services.domain.resource.pilot_selection import select_pilot_resources
from app.services.domain.resource.selection import (
    ResourceSelectionPlan,
    partition_search_results,
    select_resources as select_download_resources,
)
from app.services.application.commands.service import command_service
from app.services.audit.event_service import event_service
from app.services.config.settings_service import settings_service
from app.services.domain.download import download_service
from app.services.domain.library.service import library_service
from app.services.domain.media import media_service
from app.services.domain.subscription.download_config_service import subscription_download_config_service
from app.services.application.workflows.resource_search import resource_search_service
from app.services.platform.domain_lock_service import domain_lock_service

logger = logging.getLogger("app.services.subscription.pilot_download")


class PilotDownloadApplicationService:
    @staticmethod
    def resolve_quick_download_label(media_type: MediaType) -> str:
        return "Download" if media_type == MediaType.movie else "Pilot"

    async def queue(
        self,
        *,
        target: MediaTarget,
    ):
        media = await media_service.resolve_execution_snapshot(
            target.media_id,
            season_number=target.season_number,
            require_tv_season=True,
            require_episode_count=True,
        )
        effective_config = await subscription_download_config_service.resolve_effective_config(
            media.media_id,
            media.media_type,
            season_number=media.season_number if media.media_type == MediaType.tv else None,
        )
        if not effective_config.directory_id:
            raise DownloadException("backendErrors.downloadDirectoryMissing")
        command = await command_service.create_command(
            CommandCreateRequest(
                type=CommandType.PILOT_EPISODE,
                initiator=CommandInitiator.MANUAL,
                payload=PilotEpisodeCommandRequestPayload(
                    target=target,
                ),
            )
        )
        media = command.payload.media
        if media is None:
            raise DownloadException("backendErrors.mediaExecutionSnapshotRequired")
        event_service.emit_media(
            MediaEventCreate(
                type=EventTypes.PILOT_EPISODE_QUEUED,
                level=EventLevel.info,
                message_params={
                    "directory_id": effective_config.directory_id or "",
                    "site_count": str(len(effective_config.sites or [])),
                },
                media=media,
                actor=EventActor.user,
                source=EventSource.base,
                entities=[EventEntityRef(type="command", id=command.id)],
                correlation_id=command.id,
                action_id=command.id,
            ),
        )
        return command

    async def execute(
        self,
        *,
        media: MediaExecutionSnapshot,
        season_number: int | None = None,
    ) -> int:
        async with self._acquire_media_execution_flow(media.media_id, reason="pilot") as acquired:
            active_media = await self._resolve_execution_snapshot(media, season_number)
            action_label = self.resolve_quick_download_label(active_media.media_type)
            if not acquired:
                raise DownloadException("backendErrors.mediaResourceFlowBusy")

            effective_config = await subscription_download_config_service.resolve_effective_config(
                active_media.media_id,
                active_media.media_type,
                season_number=active_media.season_number if active_media.media_type == MediaType.tv else None,
            )
            directory_id = effective_config.directory_id
            if not directory_id:
                raise DownloadException("backendErrors.downloadDirectoryMissing")
            resolved_filters = effective_config.filters
            resolved_quality_profile_id = effective_config.quality_profile_id
            quality_profile = (
                settings_service.get_quality_profile(resolved_quality_profile_id)
                if resolved_quality_profile_id else (effective_config.quality_profile or settings_service.get_default_quality_profile())
            )
            if quality_profile is None:
                quality_profile = effective_config.quality_profile or settings_service.get_default_quality_profile()
            resolved_sites = effective_config.sites
            resolved_unmatched_rules = list(effective_config.unmatched_rules)
            episode_mode = active_media.media_type == MediaType.tv
            if episode_mode:
                if not active_media.episodes_count or active_media.season_number is None:
                    raise DownloadException("backendErrors.pilotSeasonOrEpisodeMissing")
                target_episodes = self._pilot_target_episodes(active_media.episodes_count)
                if not target_episodes:
                    raise DownloadException("backendErrors.pilotEpisodesMissing")
                logger.info(
                    "Pilot download started: media=%s season=%s target_episodes=%s sites=%s filters=%s unmatched_rules=%d",
                    active_media.media_id,
                    active_media.season_number,
                    sorted(target_episodes),
                    resolved_sites or [],
                    "configured" if resolved_filters else "none",
                    len(resolved_unmatched_rules),
                )
                target_episodes = await self._available_pilot_target_episodes(
                    media_id=active_media.media_id,
                    season_number=active_media.season_number,
                    target_episodes=target_episodes,
                )
            else:
                target_episodes = {1}
                logger.info(
                    "Configured download started: media=%s sites=%s filters=%s unmatched_rules=%d",
                    active_media.media_id,
                    resolved_sites or [],
                    "configured" if resolved_filters else "none",
                    len(resolved_unmatched_rules),
                )
                await self._ensure_movie_quick_download_available(active_media.media_id)

            selection_plan = ResourceSelectionPlan(
                media_id=active_media.media_id,
                season_number=active_media.season_number if episode_mode else None,
                episode_mode=episode_mode,
                filters=resolved_filters,
                quality_profile=quality_profile,
                target_episodes=target_episodes,
                required_scores={},
            )
            selected = await self._search_and_select_resources(
                media=active_media,
                sites=resolved_sites,
                unmatched_rules=resolved_unmatched_rules,
                selection_plan=selection_plan,
                episode_mode=episode_mode,
                action_label=action_label,
            )
            if not selected:
                raise DownloadException("backendErrors.pilotNoResource" if episode_mode else "backendErrors.quickDownloadNoResource")
            return await self._create_download_tasks(
                media=active_media,
                directory_id=directory_id,
                selected=selected,
                target_episodes=target_episodes,
                episode_mode=episode_mode,
            )

    async def _resolve_execution_snapshot(self, media: MediaExecutionSnapshot, season_number: int | None) -> MediaExecutionSnapshot:
        active_media = media.model_copy(update={"season_number": season_number}) if season_number else media
        if active_media.media_type != MediaType.tv or active_media.episodes_count:
            return active_media
        if active_media.season_number is None:
            return active_media

        return await media_service.resolve_execution_snapshot(
            active_media.media_id,
            season_number=active_media.season_number,
            require_tv_season=True,
            require_episode_count=True,
        )

    async def _search_and_select_resources(
        self,
        *,
        media: MediaExecutionSnapshot,
        sites: list[str] | None,
        unmatched_rules: list[SubscriptionUnmatchedRule] | None,
        selection_plan: ResourceSelectionPlan,
        episode_mode: bool,
        action_label: str,
    ):
        search_results = await resource_search_service.search_media(
            MediaSearchQuery(
                media=media,
                indexers=sites,
                unmatched_rules=list(unmatched_rules or []),
                use_cache=False,
            )
        )
        if episode_mode:
            logger.info(
                "Pilot search completed: media=%s season=%s results=%d target_episodes=%s",
                media.media_id,
                media.season_number,
                len(search_results),
                sorted(selection_plan.target_episodes),
            )
        else:
            logger.info("Configured download search completed: media=%s results=%d", media.media_id, len(search_results))

        standard_results, unmatched_results, has_any_id_match = partition_search_results(
            selection_plan,
            search_results,
            unmatched_rules=unmatched_rules,
        )
        logger.info(
            "%s candidate partition completed: media=%s standard=%d unmatched=%d id_matched=%s",
            action_label,
            media.media_id,
            len(standard_results),
            len(unmatched_results),
            has_any_id_match,
        )
        if not standard_results:
            raise DownloadException("backendErrors.pilotNoMatchedResource" if episode_mode else "backendErrors.quickDownloadNoMatchedResource")

        if episode_mode:
            return await select_pilot_resources(
                standard_results,
                quality_profile=selection_plan.quality_profile,
                target_episodes=selection_plan.target_episodes,
            )
        return await select_download_resources(
            standard_results,
            episodes=selection_plan.target_episodes,
            filters=selection_plan.filters,
            quality_profile=selection_plan.quality_profile,
            required_scores={},
            episode_mode=False,
        )

    async def _create_download_tasks(
        self,
        *,
        media: MediaExecutionSnapshot,
        directory_id: str,
        selected,
        target_episodes: set[int],
        episode_mode: bool,
    ) -> int:
        created_tasks = 0
        for payload, selected_files, resource in selected:
            if episode_mode:
                logger.info(
                    "Pilot resource selected: media=%s title=%s site=%s covered=%s selected_files=%s size=%s",
                    media.media_id,
                    resource.resources.title,
                    resource.resources.site,
                    sorted(payload.metadata.get_episodes() & target_episodes),
                    selected_files,
                    payload.metadata.size,
                )
            else:
                logger.info(
                    "Configured download resource selected: media=%s title=%s site=%s selected_files=%s size=%s",
                    media.media_id,
                    resource.resources.title,
                    resource.resources.site,
                    selected_files,
                    payload.metadata.size,
                )
            task = await download_service.create_download(
                DownloadTaskCreateInput(
                    media=media,
                    directory_id=directory_id,
                    result_id=resource.resources.result_id,
                    selected_files=selected_files,
                ),
                resource.resources,
            )
            created_tasks += 1
            try:
                await media_service.upsert_active_profile_from_identity(media)
            except AppException as exc:
                logger.warning(
                    "Pilot task created but media profile upsert failed: media=%s task=%s error=%s",
                    media.media_id,
                    task.id,
                    exc,
                )
        return created_tasks

    async def _ensure_pilot_available(
        self,
        *,
        media_id,
        season_number: int,
        target_episodes: set[int],
    ) -> None:
        await self._available_pilot_target_episodes(
            media_id=media_id,
            season_number=season_number,
            target_episodes=target_episodes,
        )

    async def _available_pilot_target_episodes(
        self,
        *,
        media_id,
        season_number: int,
        target_episodes: set[int],
    ) -> set[int]:
        present_episodes = await library_service.get_present_episodes(media_id, season=season_number)
        downloading_episodes = await download_service.list_active_episodes_by_media(media_id, season=season_number)
        occupied_episodes = (present_episodes | downloading_episodes) & target_episodes
        available_episodes = target_episodes - occupied_episodes
        logger.debug(
            "Pilot occupancy check: media=%s season=%s target=%s present=%s downloading=%s occupied=%s available=%s",
            media_id,
            season_number,
            sorted(target_episodes),
            sorted(present_episodes & target_episodes),
            sorted(downloading_episodes & target_episodes),
            sorted(occupied_episodes),
            sorted(available_episodes),
        )
        if not available_episodes:
            raise DownloadException("backendErrors.pilotEpisodesAlreadyCovered")
        return available_episodes

    async def _ensure_movie_quick_download_available(self, media_id) -> None:
        library_files = await library_service.get_files_by_media(media_id)
        if library_files:
            raise DownloadException("backendErrors.movieAlreadyInLibrary")
        active_tasks = await download_service.get_tasks(
            status=download_service.list_episode_coverage_statuses(),
            media_id=media_id,
        )
        if active_tasks:
            raise DownloadException("backendErrors.movieAlreadyDownloading")

    @staticmethod
    def _pilot_target_episodes(episodes_count: int) -> set[int]:
        pilot_limit = min(int(episodes_count), 3)
        if pilot_limit <= 0:
            return set()
        return set(range(1, pilot_limit + 1))

    @asynccontextmanager
    async def _acquire_media_execution_flow(self, media_id, *, reason: str) -> AsyncIterator[bool]:
        _ = reason
        async with domain_lock_service.acquire_media_acquire(media_id) as acquired:
            yield acquired


pilot_download_application_service = PilotDownloadApplicationService()
