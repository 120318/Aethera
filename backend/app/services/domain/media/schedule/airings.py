from __future__ import annotations

from collections.abc import Callable

from app.schemas.domain.media import EpisodeInfo
from app.schemas.domain.schedule import MediaScheduleSummary, ScheduleAiring, SchedulePlatform


class ScheduleAiringService:
    def build_movie_airings(self, summary: MediaScheduleSummary) -> list[ScheduleAiring]:
        airings: list[ScheduleAiring] = []
        if summary.theatrical_release_date:
            airings.append(ScheduleAiring(date=summary.theatrical_release_date, kind="movie_theatrical_release"))
        if summary.digital_release_date:
            airings.append(
                ScheduleAiring(
                    date=summary.digital_release_date,
                    kind="movie_digital_release",
                    platforms=summary.platforms,
                )
            )
        if summary.physical_release_date:
            airings.append(ScheduleAiring(date=summary.physical_release_date, kind="movie_physical_release"))
        return airings

    def build_tv_airings(
        self,
        episodes: list[EpisodeInfo],
        *,
        platforms: list[SchedulePlatform],
        date_part: Callable[[str | None], str | None],
    ) -> list[ScheduleAiring]:
        airings: list[ScheduleAiring] = []
        for episode in episodes:
            air_date = date_part(episode.air_date)
            if not air_date:
                continue
            airings.append(
                ScheduleAiring(
                    date=air_date,
                    kind="tv_episode_air",
                    season_number=episode.season_number,
                    episode_number=episode.episode_number,
                    episode_title=episode.title,
                    platforms=platforms,
                )
            )
        return airings
