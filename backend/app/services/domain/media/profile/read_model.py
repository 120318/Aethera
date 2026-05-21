import logging
from app.schemas.domain.managed_media_profile import ManagedMediaProfile
from app.schemas.domain.media import EpisodeInfo, MediaFullInfo, MediaSimpleInfo
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.schedule import MediaScheduleSummary, ScheduleEpisode
from app.schemas.exception import MediaNotFoundException
from app.schemas.media_id import MediaID
from app.services.domain.media.profile.access import model_field_list, model_field_value

logger = logging.getLogger("app.services.media")


class MediaProfileReadModel:
    def has_complete_detail(self, profile: ManagedMediaProfile) -> bool:
        return bool(profile.detail_ready and profile.title and profile.year is not None and profile.year > 0)

    def _display_rating(self, profile: ManagedMediaProfile) -> tuple[float | None, int | None, str | None]:
        if profile.douban_id:
            return profile.douban_vote_average, profile.douban_rating_count, "douban"
        tmdb_vote_average = profile.tmdb_vote_average
        tmdb_rating_count = profile.tmdb_rating_count
        if tmdb_vote_average is None and profile.rating_source == "tmdb":
            tmdb_vote_average = profile.vote_average
            tmdb_rating_count = profile.rating_count
        return tmdb_vote_average, tmdb_rating_count, "tmdb" if tmdb_vote_average is not None else profile.rating_source

    def to_simple(self, media_id: MediaID, profile: ManagedMediaProfile) -> MediaSimpleInfo:
        if profile.year is None:
            raise MediaNotFoundException()
        return MediaSimpleInfo(
            media_id=media_id,
            title=profile.title,
            year=profile.year,
            media_type=profile.media_type,
            imdb_id=profile.imdb_id,
            douban_id=profile.douban_id,
            tmdb_id=profile.tmdb_id,
            primary_metadata_source=profile.primary_metadata_source,
            metadata_capabilities=profile.metadata_capabilities,
            seasons_count=profile.seasons_count,
            season_number=None,
            seasons=list(profile.seasons),
            episodes_count=profile.episodes_count,
            aired_episode_count=0,
        )

    def to_full(self, media_id: MediaID, profile: ManagedMediaProfile) -> MediaFullInfo:
        if profile.year is None:
            raise MediaNotFoundException()
        vote_average, rating_count, rating_source = self._display_rating(profile)
        seasons = [
            season.model_copy(update={"episode_count": int(season.episode_count_override)})
            if season.episode_count_override is not None and season.episode_count_override > 0
            else season
            for season in profile.seasons
        ]
        return MediaFullInfo(
            media_id=media_id,
            title=profile.title,
            original_title=profile.original_title,
            year=profile.year,
            media_type=profile.media_type,
            imdb_id=profile.imdb_id,
            douban_id=profile.douban_id,
            tmdb_id=profile.tmdb_id,
            primary_metadata_source=profile.primary_metadata_source,
            metadata_capabilities=profile.metadata_capabilities,
            tvdb_id=profile.tvdb_id,
            overview=profile.overview,
            genres=profile.genres,
            poster_path=profile.poster_path,
            backdrop_path=profile.backdrop_path,
            logo_path=profile.logo_path,
            actors=profile.actors,
            directors=profile.directors,
            studios=profile.studios,
            duration=profile.duration,
            vendors=profile.vendors,
            rating_count=rating_count,
            vote_average=vote_average,
            vote_count=rating_count,
            rating_source=rating_source,
            douban_vote_average=profile.douban_vote_average,
            douban_rating_count=profile.douban_rating_count,
            tmdb_vote_average=profile.tmdb_vote_average,
            tmdb_rating_count=profile.tmdb_rating_count,
            release_date=profile.release_date,
            first_air_date=profile.first_air_date,
            episodes_count=profile.episodes_count,
            seasons_count=profile.seasons_count,
            season_number=None,
            seasons=seasons,
            status_label=profile.status_label,
            aired_episode_count=profile.aired_episode_count,
            latest_aired_episode=self._to_episode_info(profile.latest_aired_episode),
            next_episode_to_air=self._to_episode_info(profile.next_episode_to_air),
            premiere_release_date=model_field_value(profile, "premiere_release_date"),
            theatrical_limited_release_date=model_field_value(profile, "theatrical_limited_release_date"),
            theatrical_release_date=model_field_value(profile, "theatrical_release_date"),
            digital_release_date=model_field_value(profile, "digital_release_date"),
            physical_release_date=model_field_value(profile, "physical_release_date"),
            tv_release_date=model_field_value(profile, "tv_release_date"),
            release_dates=model_field_list(profile, "release_dates"),
            networks=list(profile.networks),
            online_platforms=list(profile.online_platforms),
            schedule=self._profile_schedule(profile),
            airings=list(profile.airings),
            status=profile.status,
            original_language=profile.original_language,
        )

    def snapshot_to_full(self, media_id: MediaID, profile: ManagedMediaProfile) -> MediaFullInfo | None:
        try:
            return self.to_full(media_id, profile)
        except MediaNotFoundException:
            logger.warning("Managed media profile missing required title/year: %s", media_id)
            return None

    def _to_episode_info(self, episode: ScheduleEpisode | None) -> EpisodeInfo | None:
        if not episode:
            return None
        if episode.season_number is None or episode.season_number <= 0:
            return None
        if episode.episode_number is None or episode.episode_number <= 0:
            return None
        return EpisodeInfo(
            season_number=episode.season_number,
            episode_number=episode.episode_number,
            air_date=episode.air_date,
            title=episode.title,
        )

    def _profile_schedule(self, profile: ManagedMediaProfile) -> MediaScheduleSummary | None:
        if profile.media_type == MediaType.movie:
            if (
                not profile.theatrical_release_date
                and not profile.digital_release_date
                and not model_field_value(profile, "physical_release_date")
                and not profile.online_platforms
            ):
                return None
            return MediaScheduleSummary(
                media_type=MediaType.movie,
                premiere_release_date=model_field_value(profile, "premiere_release_date"),
                theatrical_limited_release_date=model_field_value(profile, "theatrical_limited_release_date"),
                theatrical_release_date=profile.theatrical_release_date or profile.release_date,
                digital_release_date=profile.digital_release_date,
                physical_release_date=model_field_value(profile, "physical_release_date"),
                tv_release_date=model_field_value(profile, "tv_release_date"),
                release_dates=model_field_list(profile, "release_dates"),
                online_platforms=list(profile.online_platforms),
            )
        if profile.media_type == MediaType.tv:
            if (
                not profile.status_label
                and not profile.first_air_date
                and not profile.networks
                and profile.aired_episode_count <= 0
                and not profile.latest_aired_episode
                and not profile.next_episode_to_air
            ):
                return None
            return MediaScheduleSummary(
                media_type=MediaType.tv,
                status_label=profile.status_label,
                first_air_date=profile.first_air_date or profile.release_date,
                networks=list(profile.networks),
                online_platforms=list(profile.online_platforms),
                aired_episode_count=profile.aired_episode_count,
                latest_aired_episode=profile.latest_aired_episode,
                next_episode_to_air=profile.next_episode_to_air,
            )
        return None
