from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from app.schemas.domain.download import TaskData, TaskEpisodeCoverage, TaskEpisodeCoverageSource, TaskStatus
from app.schemas.domain.media_types import MediaType
from app.schemas.media_id import MediaID
from app.services.domain.resource.quality import RESOURCE_FORM_BLURAY_DISC, RESOURCE_FORM_DVD_DISC


logger = logging.getLogger("app.services.download")


def _positive_int(value) -> int | None:
    if type(value) is int and value > 0:
        return value
    return None


def list_episode_coverage_statuses() -> list[TaskStatus]:
    return [
        TaskStatus.PENDING,
        TaskStatus.DOWNLOADING,
        TaskStatus.PAUSED,
        TaskStatus.FINISHED,
        TaskStatus.TRANSFERRING,
        TaskStatus.MIGRATING,
        TaskStatus.COMPLETED,
    ]


def list_library_present_statuses() -> list[TaskStatus]:
    return [
        TaskStatus.COMPLETED,
        TaskStatus.PARTIAL_MISSING,
        TaskStatus.SEEDING_ABSENT,
    ]


def resolve_task_episode_coverage_detail(task: TaskData) -> TaskEpisodeCoverage:
    context = task.context
    ctx_attrs = context.parsed_attributes if context and context.parsed_attributes else None
    context_media_season = _positive_int(context.media.season_number) if context and context.media else None
    selected_indices = set(context.selected_files) if context and context.selected_files else None
    ctx_season = None
    ctx_episodes: set[int] = set()
    if ctx_attrs:
        if ctx_attrs.seasons:
            ctx_season = ctx_attrs.seasons[0]
        if selected_indices is None and ctx_attrs.episodes:
            for ep in ctx_attrs.episodes:
                if ep > 0:
                    ctx_episodes.add(ep)

    file_seasons: set[int] = set()
    file_episodes: set[int] = set()
    if task.metadata and task.metadata.files:
        for index, f in enumerate(task.metadata.files):
            if selected_indices is not None and index not in selected_indices:
                continue
            attrs = f.attrs
            if not attrs:
                continue
            season_val = attrs.seasons[0] if attrs.seasons else None
            if season_val is not None and season_val > 0:
                file_seasons.add(season_val)
            eps_val = attrs.episodes
            if eps_val:
                for ep in eps_val:
                    if ep > 0:
                        file_episodes.add(ep)

    season_source = TaskEpisodeCoverageSource.UNKNOWN
    season = ctx_season
    if season is not None:
        season_source = TaskEpisodeCoverageSource.PARSED_CONTEXT
    if season is None and file_seasons:
        season = sorted(file_seasons)[0]
        season_source = TaskEpisodeCoverageSource.FILE_METADATA
    if season is None:
        season = context_media_season
        if season is not None:
            season_source = TaskEpisodeCoverageSource.TASK_CONTEXT

    is_tv_disc_package = (
        task.media_id.media_type == MediaType.tv
        and (
            (ctx_attrs and ctx_attrs.resource_form in {RESOURCE_FORM_BLURAY_DISC, RESOURCE_FORM_DVD_DISC})
            or (task.metadata and task.metadata.attrs and task.metadata.attrs.resource_form in {RESOURCE_FORM_BLURAY_DISC, RESOURCE_FORM_DVD_DISC})
        )
    )
    episode_mismatch = False
    if ctx_episodes:
        episodes = sorted(ctx_episodes)
        if file_episodes and not file_episodes.issubset(ctx_episodes):
            episode_mismatch = True
            logger.warning(
                "Task %s episodes mismatch between context and metadata: context=%s, metadata=%s",
                task.id,
                episodes,
                sorted(file_episodes),
            )
    else:
        episodes = sorted(file_episodes) if file_episodes else ([] if is_tv_disc_package else [1])

    season_mismatch = False
    if ctx_season and file_seasons and ctx_season not in file_seasons:
        season_mismatch = True
        logger.warning(
            "Task %s season mismatch between context and metadata: context=%s, metadata=%s",
            task.id,
            ctx_season,
            sorted(file_seasons),
        )
    if context_media_season and season != context_media_season:
        season_mismatch = True
        logger.warning(
            "Task %s season mismatch between task media context and parsed coverage: context_media=%s, resolved=%s",
            task.id,
            context_media_season,
            season,
        )

    if task.media_id.media_type == MediaType.tv and season is None:
        logger.warning("Task %s missing season information for tv media %s", task.id, task.media_id)

    return TaskEpisodeCoverage(
        season_number=season,
        episode_numbers=episodes,
        source=season_source,
        season_mismatch=season_mismatch,
        episode_mismatch=episode_mismatch,
    )


def resolve_task_episode_coverage(task: TaskData) -> tuple[int | None, list[int]]:
    coverage = resolve_task_episode_coverage_detail(task)
    return coverage.season_number, coverage.episode_numbers


class DownloadCoverageService:
    def __init__(self, get_tasks: Callable[..., Awaitable[list[TaskData]]]) -> None:
        self._get_tasks = get_tasks

    async def list_active_episodes_by_media(
        self,
        media_id: MediaID,
        season: int | None = None,
    ) -> set[int]:
        tasks = await self._get_tasks(status=list_episode_coverage_statuses(), media_id=media_id)
        episodes: set[int] = set()
        for task in tasks:
            coverage = resolve_task_episode_coverage_detail(task)
            if season is not None and coverage.season_number != season:
                continue
            if coverage.episode_numbers:
                episodes.update(coverage.episode_numbers)
        return episodes
