import logging

from app.schemas.domain.media import MediaTarget
from app.schemas.domain.media_types import MediaType
from app.schemas.runtime.resource_list import EpisodeInfo, ResourceListResponse, SeasonInfo, resolve_episode_status
from app.services.domain.download import download_service
from app.services.domain.library.service import library_service
from app.services.domain.media import media_service

logger = logging.getLogger(__name__)


class ResourceListService:
    def task_season_number(self, task) -> int | None:
        coverage = download_service.resolve_task_episode_coverage_detail(task)
        return coverage.season_number if coverage.has_known_season else None

    def task_matches_target(self, task, target: MediaTarget) -> bool:
        if target.season_number is None:
            return True
        task_season = self.task_season_number(task)
        return task_season == target.season_number

    async def list(self, target: MediaTarget) -> ResourceListResponse:
        media_id = target.media_id
        season_number = target.season_number
        tasks = await download_service.get_tasks(media_id=media_id)
        library_episodes = await library_service.get_episodes_by_media(media_id)
        library_files = await library_service.get_files_by_media(media_id, season=season_number)
        if media_id.media_type == MediaType.movie:
            library_files = []
            seen_file_ids = set()
            for task in tasks:
                task_files = await library_service.get_files_by_task(task.id)
                for library_file in task_files:
                    if library_file.id and library_file.id in seen_file_ids:
                        continue
                    if library_file.id:
                        seen_file_ids.add(library_file.id)
                    library_files.append(library_file)

        media_has_primary_library_files = any(
            library_service.is_primary_file(library_file)
            and library_service.file_exists(library_file)
            for library_file in library_files
        )
        file_exists_map = library_service.build_file_exists_map(library_files)
        existing_episode_keys = {
            (int(library_episode.season), int(library_episode.episode))
            for library_episode in library_episodes
            if library_episode.file_id in file_exists_map and file_exists_map[library_episode.file_id]
        }
        media_info = await media_service.simple_info(media_id)
        if media_info:
            media_info = media_service.apply_season_context(media_info, season_number)
        active_season_number = media_info.season_number if media_info and media_info.media_type == MediaType.tv else None
        if media_id.media_type == MediaType.tv and season_number is not None:
            tasks = [task for task in tasks if self.task_matches_target(task, target)]

        if not tasks:
            return ResourceListResponse(
                media_id=media_id,
                tasks=[],
                seasons=(
                    [SeasonInfo(season=active_season_number, episodes=[])]
                    if active_season_number is not None
                    else []
                ),
            )

        season_dict = {}
        for task in tasks:
            coverage = download_service.resolve_task_episode_coverage_detail(task)
            season_num = coverage.season_number or active_season_number
            if media_id.media_type == MediaType.tv and season_num is None:
                logger.warning("Skip task %s in resource list because season information is missing", task.id)
                continue
            if not coverage.episode_numbers:
                continue
            for episode_num in coverage.episode_numbers:
                if season_num not in season_dict:
                    season_dict[season_num] = {}
                if episode_num not in season_dict[season_num]:
                    episode_status = resolve_episode_status(
                        task,
                        season_num,
                        episode_num,
                        existing_episode_keys,
                        media_has_primary_library_files,
                    )
                    season_dict[season_num][episode_num] = EpisodeInfo(
                        episode=episode_num,
                        status=episode_status,
                        task_ids=[],
                    )
                season_dict[season_num][episode_num].task_ids.append(task.id)

        seasons = []
        for season_num, episode_dict in sorted(season_dict.items()):
            episodes = sorted(episode_dict.values(), key=lambda item: item.episode)
            seasons.append(SeasonInfo(season=season_num, episodes=episodes))

        return ResourceListResponse(media_id=media_id, tasks=tasks, seasons=seasons)


resource_list_service = ResourceListService()
