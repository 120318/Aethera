from __future__ import annotations

from datetime import date

from app.schemas.domain.media import EpisodeInfo, MediaFullInfo
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.schedule import MediaScheduleSummary, ScheduleAiring, ScheduleEpisode, SchedulePlatform
from app.services.domain.media import media_service


class MediaDetailOverviewScheduleMixin:
    async def _resolve_schedule_summary(self, media: MediaFullInfo) -> MediaScheduleSummary:
        if media.media_type == MediaType.tv and media.season_number:
            platforms = list(media.schedule.platforms) if media.schedule else []
            season_schedule = self._resolve_tv_season_schedule_from_cache(media, platforms)
            if season_schedule:
                return season_schedule
            if media.schedule and self._schedule_matches_season(media.schedule, media.season_number):
                return media.schedule
            return MediaScheduleSummary(
                media_type=media.media_type,
                first_air_date=self._season_first_air_date(media),
                platforms=platforms,
            )
        if media.schedule:
            return media.schedule
        schedule = await media_service.build_schedule_summary_for_media(media)
        return schedule

    def _resolve_tv_season_schedule_from_cache(
        self,
        media: MediaFullInfo,
        platforms: list[SchedulePlatform],
    ) -> MediaScheduleSummary | None:
        season_number = media.season_number
        if not season_number:
            return None
        season_airings = [
            airing
            for airing in media.airings
            if airing.kind == "tv_episode_air" and airing.season_number == season_number
        ]
        if not season_airings:
            return None

        season_airings.sort(key=self._airing_sort_key)
        today = date.today()
        aired: list[ScheduleAiring] = []
        upcoming: list[ScheduleAiring] = []
        for airing in season_airings:
            airing_date = self._parse_airing_date(airing.date)
            if not airing_date:
                continue
            if airing_date <= today:
                aired.append(airing)
            else:
                upcoming.append(airing)
        latest_aired = aired[-1] if aired else None
        next_episode = upcoming[0] if upcoming else None
        total_episodes = media.episodes_count
        status_label = "Airing"
        if not next_episode and total_episodes and len(aired) >= int(total_episodes):
            status_label = "Ended"
        elif not next_episode and str(media.status or "").strip().lower() == "ended":
            status_label = "Ended"

        return MediaScheduleSummary(
            media_type=media.media_type,
            status_label=status_label,
            first_air_date=self._season_first_air_date(media) or season_airings[0].date,
            platforms=list(platforms),
            aired_episode_count=len(aired),
            latest_aired_episode=self._airing_to_schedule_episode(latest_aired),
            next_episode_to_air=self._airing_to_schedule_episode(next_episode),
        )

    def _schedule_matches_season(self, schedule: MediaScheduleSummary, season_number: int) -> bool:
        schedule_episodes: list[EpisodeInfo | None] = [
            schedule.latest_aired_episode,
            schedule.next_episode_to_air,
        ]
        present = [episode for episode in schedule_episodes if episode]
        if not present:
            return False
        return all(episode.season_number == season_number for episode in present)

    def _season_first_air_date(self, media: MediaFullInfo) -> str | None:
        season_number = media.season_number
        if season_number:
            matched = next((season for season in media.seasons if season.season_number == season_number), None)
            if matched and matched.air_date:
                return matched.air_date
        return media.first_air_date or media.release_date

    def _airing_sort_key(self, airing: ScheduleAiring) -> tuple[str, int]:
        return (airing.date or "", int(airing.episode_number or 0))

    def _parse_airing_date(self, value: str | None) -> date | None:
        if not value:
            return None
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            return None

    def _airing_to_schedule_episode(self, airing: ScheduleAiring | None) -> ScheduleEpisode | None:
        if not airing:
            return None
        return ScheduleEpisode(
            season_number=airing.season_number,
            episode_number=airing.episode_number,
            air_date=airing.date,
            title=airing.episode_title,
        )
