from __future__ import annotations

import asyncio
from datetime import date

from app.schemas.domain.media import EpisodeInfo, MediaFullInfo
from app.schemas.domain.media_context import ResolvedMediaContext
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.vendor import Vendor
from app.schemas.integration.media.provider import (
    ProviderReleaseDateEntry,
    ProviderReleaseRegion,
    ProviderWatchProviders,
)
from app.schemas.domain.schedule import MediaScheduleSummary, MovieReleaseDateDetail, ScheduleAiring, ScheduleEpisode, SchedulePlatform
from app.services.integration.tmdb.schedule import tmdb_schedule_gateway
from app.services.domain.media.profile.context import media_profile_context_service
from app.services.domain.media.schedule.airings import ScheduleAiringService
from app.services.domain.media.schedule.platforms import SchedulePlatformService


class MediaScheduleService:
    def __init__(self) -> None:
        self.platforms = SchedulePlatformService()
        self.airings = ScheduleAiringService()

    def _date_part(self, value: str | None) -> str | None:
        if not value:
            return None
        text = str(value)
        if len(text) < 10:
            return None
        return text[:10]

    def _parse_date(self, value: str | None) -> date | None:
        text = self._date_part(value)
        if not text:
            return None
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None

    def _release_region_weight(self, region: ProviderReleaseRegion) -> int:
        code = (region.iso_3166_1 or "").upper()
        if code in self.platforms.preferred_regions:
            return self.platforms.preferred_regions.index(code)
        return len(self.platforms.preferred_regions)

    def _release_item_weight(self, item: ProviderReleaseDateEntry, target_types: set[int]) -> tuple[int, str]:
        release_type = int(item.type or 0)
        type_weight = 0 if release_type in target_types else 1
        release_date = self._date_part(item.release_date) or "9999-12-31"
        return type_weight, release_date

    def _select_release_date(self, regions: list[ProviderReleaseRegion], target_types: set[int]) -> str | None:
        candidates: list[tuple[int, int, str]] = []
        for region in regions:
            region_weight = self._release_region_weight(region)
            for item in region.release_dates:
                release_type = int(item.type or 0)
                release_date = self._date_part(item.release_date)
                if release_type in target_types and release_date:
                    item_weight, item_date = self._release_item_weight(item, target_types)
                    candidates.append((region_weight, item_weight, item_date))
        if not candidates:
            return None
        candidates.sort(key=lambda candidate: (candidate[0], candidate[1], candidate[2]))
        return candidates[0][2]

    def _flatten_release_dates(self, regions: list[ProviderReleaseRegion]) -> list[MovieReleaseDateDetail]:
        details: list[MovieReleaseDateDetail] = []
        for region in regions:
            region_code = (region.iso_3166_1 or "").upper() or None
            for item in region.release_dates:
                release_date = self._date_part(item.release_date)
                if not release_date:
                    continue
                details.append(
                    MovieReleaseDateDetail(
                        region=region_code,
                        type=item.type,
                        release_date=release_date,
                        certification=item.certification,
                        note=item.note,
                        descriptors=list(item.descriptors or []),
                        language=item.iso_639_1,
                    )
                )
        details.sort(
            key=lambda item: (
                self._release_region_weight(ProviderReleaseRegion(iso_3166_1=item.region)),
                int(item.type or 0),
                item.release_date or "9999-12-31",
            )
        )
        return details

    async def _get_schedule_movie_release_dates(self, tmdb_id: int) -> list[ProviderReleaseRegion]:
        return await tmdb_schedule_gateway.get_movie_release_dates(tmdb_id)

    async def _get_schedule_watch_provider_payload(self, tmdb_id: int, media_type: MediaType, region: str) -> ProviderWatchProviders:
        return await tmdb_schedule_gateway.get_watch_provider_payload(tmdb_id, media_type, region)

    async def _get_schedule_season_details(self, tmdb_id: int, season_number: int):
        return await tmdb_schedule_gateway.get_season_details(tmdb_id, season_number)

    async def _get_online_platforms(self, tmdb_id: int, media_type: MediaType):
        platforms = []
        payloads_by_region = await tmdb_schedule_gateway.get_watch_provider_payloads(
            tmdb_id,
            media_type,
            self.platforms.preferred_regions,
        )
        for region in self.platforms.preferred_regions:
            payload = payloads_by_region.get(region, ProviderWatchProviders())
            url = payload.link
            for bucket in self.platforms.online_provider_buckets:
                providers = self.platforms.provider_bucket(payload, bucket)
                for provider in providers or []:
                    platform = self.platforms.provider_platform(provider, region, url)
                    if platform:
                        platforms.append(platform)
        return self.platforms.dedupe(platforms)

    def _online_platforms_from_vendors(self, vendors: list[Vendor]) -> list[SchedulePlatform]:
        platforms = [
            self.platforms.normalize(
                SchedulePlatform(
                    id=vendor.id,
                    name=vendor.name,
                    logo=vendor.logo,
                    url=vendor.url,
                )
            )
            for vendor in vendors
            if vendor.name
        ]
        return self.platforms.dedupe(platforms)

    def _merged_online_platforms(self, media: MediaFullInfo) -> list[SchedulePlatform]:
        platforms = self.platforms.dedupe([
            *list(media.online_platforms or []),
            *self._online_platforms_from_vendors(list(media.vendors or [])),
        ])
        return self.platforms.dedupe(
            self.platforms.apply_vendor_links(platforms, list(media.vendors or []))
        )

    def merged_online_platforms(self, media: MediaFullInfo) -> list[SchedulePlatform]:
        return self._merged_online_platforms(media)

    def _episode_sort_key(self, episode: EpisodeInfo) -> tuple[str, int, int]:
        return (episode.air_date or "", int(episode.season_number or 0), int(episode.episode_number or 0))

    def _season_numbers(self, season_number: int | None) -> list[int]:
        return [season_number] if season_number else []

    async def _get_tv_season_episodes(self, tmdb_id: int, season_numbers: list[int]) -> tuple[list[EpisodeInfo], str | None]:
        episodes: list[EpisodeInfo] = []
        season_air_date: str | None = None
        for season_number in season_numbers:
            season = await self._get_schedule_season_details(tmdb_id, season_number)
            if not season:
                continue
            if not season_air_date:
                season_air_date = self._date_part(season.air_date)
            if not season.episodes:
                continue
            for episode in season.episodes:
                if int(episode.episode_number or 0) > 0:
                    episodes.append(episode)
        episodes.sort(key=self._episode_sort_key)
        return episodes, season_air_date

    def _tv_aired_episodes(self, episodes: list[EpisodeInfo]) -> list[EpisodeInfo]:
        today = date.today()
        aired: list[EpisodeInfo] = []
        for episode in episodes:
            air_date = self._parse_date(episode.air_date)
            if air_date and air_date <= today:
                aired.append(episode)
        return aired

    def _tv_next_episode(self, episodes: list[EpisodeInfo]) -> EpisodeInfo | None:
        today = date.today()
        for episode in episodes:
            air_date = self._parse_date(episode.air_date)
            if air_date and air_date > today:
                return episode
        return None

    def _tv_season_first_air_date(self, season_air_date: str | None, season_episodes: list[EpisodeInfo], media: MediaFullInfo) -> str | None:
        if season_air_date:
            return season_air_date
        for episode in season_episodes:
            first_episode_date = self._date_part(episode.air_date)
            if first_episode_date:
                return first_episode_date
        return media.first_air_date or media.release_date

    def _is_same_episode(self, first: ScheduleEpisode | None, second: ScheduleEpisode | None) -> bool:
        if not first or not second:
            return False
        if first.season_number is None or second.season_number is None:
            return False
        if first.episode_number is None or second.episode_number is None:
            return False
        return first.season_number == second.season_number and first.episode_number == second.episode_number

    def _is_next_episode_valid(
        self,
        next_episode: ScheduleEpisode | None,
        latest_aired_episode: ScheduleEpisode | None,
        total_episodes: int | None,
    ) -> bool:
        if not next_episode:
            return False
        air_date = self._parse_date(next_episode.air_date)
        if not air_date or air_date <= date.today():
            return False
        if total_episodes and next_episode.episode_number and next_episode.episode_number > total_episodes:
            return False
        same_season_as_latest = (
            latest_aired_episode
            and latest_aired_episode.season_number is not None
            and next_episode.season_number is not None
            and latest_aired_episode.season_number == next_episode.season_number
        )
        if same_season_as_latest and latest_aired_episode.episode_number and next_episode.episode_number:
            if next_episode.episode_number <= latest_aired_episode.episode_number:
                return False
        return True

    def _tv_status_label(
        self,
        media: MediaFullInfo,
        aired_count: int,
        total_episodes: int | None,
        next_episode: ScheduleEpisode | None,
    ) -> str:
        if next_episode:
            return "Airing"
        if total_episodes and aired_count >= total_episodes:
            return "Ended"
        status = (media.status or "").strip().lower()
        if status == "ended":
            return "Ended"
        return "Airing"

    def _to_schedule_episode(self, episode: EpisodeInfo | None) -> ScheduleEpisode | None:
        if not episode:
            return None
        return ScheduleEpisode(
            season_number=episode.season_number,
            episode_number=episode.episode_number,
            air_date=episode.air_date,
            title=episode.title,
        )

    def _to_tmdb_schedule_episode(self, episode: EpisodeInfo | None) -> ScheduleEpisode | None:
        if not episode:
            return None
        return ScheduleEpisode(
            season_number=episode.season_number,
            episode_number=episode.episode_number,
            air_date=episode.air_date,
            title=episode.title,
        )

    def _tv_networks(self, media: MediaFullInfo) -> list[SchedulePlatform]:
        networks = [self.platforms.normalize(platform) for platform in list(media.networks or [])]
        return self.platforms.dedupe(self.platforms.apply_vendor_links(networks, list(media.vendors or [])))

    def _tv_online_platforms(self, media: MediaFullInfo, networks: list[SchedulePlatform]) -> list[SchedulePlatform]:
        online_platforms = self._merged_online_platforms(media)
        return self.platforms.exclude_matching(online_platforms, networks)

    def _tv_platforms(self, media: MediaFullInfo, networks: list[SchedulePlatform]) -> list[SchedulePlatform]:
        return self.platforms.merge(networks, self._merged_online_platforms(media))

    async def _build_tv_schedule_inputs(
        self,
        context: ResolvedMediaContext,
        season_number: int | None,
    ) -> tuple[list[EpisodeInfo], list[EpisodeInfo], str | None]:
        tmdb_id = media_profile_context_service.tmdb_id_from_context(context)
        season_episodes: list[EpisodeInfo] = []
        season_air_date: str | None = None
        if tmdb_id and season_number:
            season_episodes, season_air_date = await self._get_tv_season_episodes(tmdb_id, self._season_numbers(season_number))
        aired_episodes = self._tv_aired_episodes(season_episodes)
        return season_episodes, aired_episodes, season_air_date

    async def build_movie_schedule_summary(self, media: MediaFullInfo) -> MediaScheduleSummary:
        context = media_profile_context_service.resolve_context_from_media(media)
        tmdb_id = media_profile_context_service.tmdb_id_from_context(context)
        release_dates_task = (
            self._get_schedule_movie_release_dates(tmdb_id)
            if context.metadata_capabilities.has_movie_release_window and tmdb_id
            else None
        )
        online_platforms = self._online_platforms_from_vendors(list(media.vendors or []))
        online_platforms_task = (
            self._get_online_platforms(tmdb_id, MediaType.movie)
            if not online_platforms and context.metadata_capabilities.has_watch_providers and tmdb_id
            else None
        )
        release_dates_result, online_platforms_result = await asyncio.gather(
            release_dates_task or self._empty_release_dates(),
            online_platforms_task or self._empty_online_platforms(),
        )

        premiere_release_date = self._select_release_date(release_dates_result, {1})
        theatrical_limited_release_date = self._select_release_date(release_dates_result, {2})
        theatrical_release_date = self._select_release_date(release_dates_result, {2, 3})
        digital_release_date = self._select_release_date(release_dates_result, {4})
        physical_release_date = self._select_release_date(release_dates_result, {5})
        tv_release_date = self._select_release_date(release_dates_result, {6})
        if not online_platforms:
            online_platforms = online_platforms_result
        online_platforms = self.platforms.dedupe(
            self.platforms.apply_vendor_links(online_platforms, list(media.vendors or []))
        )
        return MediaScheduleSummary(
            media_type=MediaType.movie,
            premiere_release_date=premiere_release_date,
            theatrical_limited_release_date=theatrical_limited_release_date,
            theatrical_release_date=theatrical_release_date or media.release_date,
            digital_release_date=digital_release_date,
            physical_release_date=physical_release_date,
            tv_release_date=tv_release_date,
            release_dates=self._flatten_release_dates(release_dates_result),
            platforms=online_platforms,
        )

    async def _empty_release_dates(self) -> list[ProviderReleaseRegion]:
        return []

    async def _empty_online_platforms(self) -> list[SchedulePlatform]:
        return []

    async def build_tv_schedule_summary(self, media: MediaFullInfo, season_number: int | None) -> MediaScheduleSummary:
        context = media_profile_context_service.resolve_context_from_media(media)
        if not context.metadata_capabilities.has_schedule or not season_number:
            networks = self._tv_networks(media)
            platforms = self._tv_platforms(media, networks)
            return MediaScheduleSummary(
                media_type=MediaType.tv,
                first_air_date=media.first_air_date or media.release_date,
                platforms=platforms,
            )
        season_episodes, aired_episodes, season_air_date = await self._build_tv_schedule_inputs(context, season_number)
        next_episode = self._to_schedule_episode(media.next_episode_to_air)
        latest_aired_episode = self._to_tmdb_schedule_episode(aired_episodes[-1]) if aired_episodes else None
        computed_next_episode = self._to_tmdb_schedule_episode(self._tv_next_episode(season_episodes))
        if computed_next_episode:
            next_episode = computed_next_episode
        if self._is_same_episode(latest_aired_episode, next_episode):
            next_episode = None
        if not self._is_next_episode_valid(next_episode, latest_aired_episode, media.episodes_count):
            next_episode = None
        networks = self._tv_networks(media)
        platforms = self._tv_platforms(media, networks)
        return MediaScheduleSummary(
            media_type=MediaType.tv,
            status_label=self._tv_status_label(media, len(aired_episodes), media.episodes_count, next_episode),
            first_air_date=self._tv_season_first_air_date(season_air_date, season_episodes, media),
            platforms=platforms,
            aired_episode_count=len(aired_episodes),
            latest_aired_episode=latest_aired_episode,
            next_episode_to_air=next_episode,
        )

    async def build_schedule_summary_for_media(self, media: MediaFullInfo) -> MediaScheduleSummary:
        if media.media_type == MediaType.movie:
            return await self.build_movie_schedule_summary(media)
        if media.media_type == MediaType.tv:
            return await self.build_tv_schedule_summary(media, media.season_number)
        return MediaScheduleSummary(media_type=media.media_type)

    async def build_airings_for_media(self, media: MediaFullInfo) -> list[ScheduleAiring]:
        if media.media_type == MediaType.movie:
            summary = await self.build_movie_schedule_summary(media)
            return self.airings.build_movie_airings(summary)
        context = media_profile_context_service.resolve_context_from_media(media)
        if media.media_type != MediaType.tv or not context.metadata_capabilities.has_schedule:
            return []

        season_episodes, _, _ = await self._build_tv_schedule_inputs(context, media.season_number)
        networks = self._tv_networks(media)
        return self.airings.build_tv_airings(season_episodes, platforms=self._tv_platforms(media, networks), date_part=self._date_part)

    async def build_schedule_bundle(self, media: MediaFullInfo) -> tuple[MediaScheduleSummary, list[ScheduleAiring]]:
        if media.media_type == MediaType.tv:
            summary = await self.build_schedule_summary_for_media(media)
            context = media_profile_context_service.resolve_context_from_media(media)
            if not context.metadata_capabilities.has_schedule or not media.season_number:
                return summary, []
            season_episodes, _, _ = await self._build_tv_schedule_inputs(context, media.season_number)
            airings = self.airings.build_tv_airings(season_episodes, platforms=summary.platforms, date_part=self._date_part)
            return summary, airings
        return await self.build_schedule_summary_for_media(media), await self.build_airings_for_media(media)
