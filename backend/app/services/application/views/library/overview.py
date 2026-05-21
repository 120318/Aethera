import asyncio
import logging

from app.schemas.domain.download import TaskStatus
from app.schemas.domain.media import MediaFullInfo, MediaSimpleInfo
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.schedule import MediaScheduleSummary
from app.schemas.media_id import MediaID
from app.schemas.runtime.library_overview import LibraryOverviewResponse, LibraryOverviewSnapshot, NextEpisodeToAir
from app.services.domain.download import download_service
from app.services.domain.library.service import MediaLibrarySnapshot, library_service
from app.services.domain.media import media_service

logger = logging.getLogger(__name__)

OVERVIEW_ACTIVE_TASK_STATUSES = [
    TaskStatus.PENDING,
    TaskStatus.DOWNLOADING,
    TaskStatus.PAUSED,
    TaskStatus.TRANSFERRING,
    TaskStatus.FINISHED,
    TaskStatus.MIGRATING,
]


class LibraryOverviewService:
    def _as_positive_int(self, value: int | None) -> int | None:
        if type(value) is not int or value <= 0:
            return None
        return value

    async def get_overview(self, media_id: MediaID) -> LibraryOverviewResponse:
        media = await media_service.cached_info(media_id)
        schedule = None
        if media and media.media_type == MediaType.movie:
            schedule = await media_service.build_schedule_summary_for_media(media)
        snapshot = await self.build_snapshot(media_id, media, schedule=schedule)
        return LibraryOverviewResponse(media_id=media_id, **snapshot.model_dump())

    def resolve_full_media_total_episodes(self, media: MediaFullInfo | None) -> int:
        active_season_number = media.season_number if media and media.media_type == MediaType.tv else None
        total_episodes = (media.episodes_count or 0) if media else 0
        if media and active_season_number is not None:
            matched_season = next((season for season in media.seasons if season.season_number == active_season_number), None)
            if matched_season and matched_season.episode_count is not None:
                total_episodes = int(matched_season.episode_count or 0)
        return total_episodes

    def resolve_simple_media_total_episodes(self, media: MediaSimpleInfo | None) -> int:
        return int(media.episodes_count or 0) if media else 0

    async def build_snapshot(
        self,
        media_id: MediaID,
        media: MediaFullInfo | None = None,
        schedule: MediaScheduleSummary | None = None,
        library_snapshot: MediaLibrarySnapshot | None = None,
    ) -> LibraryOverviewSnapshot:
        if media is None:
            simple_media = await media_service.simple_info(media_id)
            active_season_number = (
                simple_media.season_number
                if simple_media and simple_media.media_type == MediaType.tv
                else None
            )
            total_episodes = self.resolve_simple_media_total_episodes(simple_media)
        else:
            active_season_number = media.season_number if media.media_type == MediaType.tv else None
            total_episodes = self.resolve_full_media_total_episodes(media)
            schedule = schedule or media.schedule

        snapshot_task = (
            self._loaded_library_snapshot(library_snapshot)
            if library_snapshot is not None
            else library_service.get_media_library_snapshot(media_id, season=active_season_number)
        )
        library_snapshot, active_tasks = await asyncio.gather(
            snapshot_task,
            download_service.list_media_tasks_for_overview(status=OVERVIEW_ACTIVE_TASK_STATUSES, media_id=media_id),
        )
        present_episodes = library_snapshot.present_episodes
        library_files = library_snapshot.files

        downloading_episode_set: set[int] = set()
        for task in active_tasks:
            coverage = download_service.resolve_task_episode_coverage_detail(task)
            if active_season_number is not None and not coverage.has_known_season:
                continue
            if active_season_number is not None and coverage.season_number != active_season_number:
                continue
            for episode in coverage.episode_numbers:
                normalized_episode = self._as_positive_int(episode)
                if normalized_episode is not None:
                    downloading_episode_set.add(normalized_episode)

        next_episode_source = schedule.next_episode_to_air if schedule else None
        next_episode = None
        if next_episode_source:
            next_episode = NextEpisodeToAir(
                season_number=next_episode_source.season_number,
                episode_number=next_episode_source.episode_number,
                air_date=next_episode_source.air_date,
                title=next_episode_source.title,
            )

        library_file_count = len(library_files)
        original_disc_packages = library_service.build_package_summaries(library_files)
        collected_count = library_file_count if media_id.media_type == MediaType.movie else len(present_episodes)
        downloading_count = len(active_tasks) if media_id.media_type == MediaType.movie else len(downloading_episode_set)

        return LibraryOverviewSnapshot(
            total_episodes=total_episodes,
            collected_count=collected_count,
            collected_episodes=sorted(
                [normalized for ep in present_episodes if (normalized := self._as_positive_int(ep)) is not None]
            ),
            downloading_count=downloading_count,
            downloading_episodes=sorted(downloading_episode_set),
            library_file_count=library_file_count,
            original_disc_package_count=len(original_disc_packages),
            original_disc_file_count=sum(package.file_count for package in original_disc_packages),
            active_task_count=len(active_tasks),
            next_episode_to_air=next_episode,
            schedule=schedule,
        )

    async def _loaded_library_snapshot(self, snapshot: MediaLibrarySnapshot) -> MediaLibrarySnapshot:
        return snapshot


library_overview_service = LibraryOverviewService()
