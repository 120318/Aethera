from __future__ import annotations

from datetime import date
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Literal

from app.schemas.media_id import MediaID
from app.schemas.domain.media import EpisodeInfo, MediaFullInfo, MediaSeasonInfo
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.schedule import MediaScheduleSummary, ScheduleAiring, ScheduleEpisode, SchedulePlatform
from app.schemas.integration.media.provider import ProviderMediaBundle, ProviderSearchItem, ProviderWatchProviders
from app.schemas.domain.vendor import Vendor
from app.services.domain.media.profile.access import model_field_list, model_field_value


def normalize_title(value: str) -> str:
    if not value:
        return ""
    normalized = value.lower()
    normalized = re.sub(r"[\s._-]+", " ", normalized)
    normalized = "".join(ch for ch in normalized if not unicodedata.category(ch).startswith(("P", "S")))
    normalized = re.sub(r"第\s*[一二三四五六七八九十\d]+\s*季", "", normalized)
    normalized = re.sub(r"season\s*\d+", "", normalized)
    return normalized.strip()


def subject_type(media_type: MediaType) -> Literal["movie", "tv"]:
    return "movie" if media_type == MediaType.movie else "tv"


def dedupe_vendors(vendors: list[Vendor]) -> list[Vendor]:
    deduped: list[Vendor] = []
    seen: set[str] = set()
    for vendor in vendors:
        key = f"{(vendor.name or '').strip().lower()}|{(vendor.url or '').strip().lower().rstrip('/')}"
        if not key.strip("|") or key in seen:
            continue
        seen.add(key)
        deduped.append(vendor)
    return deduped


def resolve_year(value: str | None) -> int | None:
    if not value or len(str(value)) < 4:
        return None
    try:
        return int(str(value)[:4])
    except ValueError:
        return None


def _resolve_media_year(
    *,
    src_date: str | None,
    schedule: MediaScheduleSummary | None,
    seasons: list[MediaSeasonInfo],
    selected_season: int | None,
) -> int:
    year = resolve_year(src_date)
    if year:
        return year
    if schedule and schedule.first_air_date:
        year = resolve_year(schedule.first_air_date)
        if year:
            return year
    if selected_season is not None:
        for season in seasons:
            if season.season_number == selected_season:
                year = resolve_year(season.air_date)
                if year:
                    return year
                break
    return 0


def resolve_tmdb_selected_season(
    available: list[MediaSeasonInfo],
    desired_season: int | None,
    desired_year: int | None,
) -> int | None:
    if desired_season and any(season.season_number == desired_season for season in available):
        return desired_season
    if desired_year:
        for season in available:
            if season.air_date and resolve_year(season.air_date) == desired_year:
                return season.season_number
    if desired_season is not None:
        return desired_season
    available_seasons = sorted(
        int(season.season_number)
        for season in available
        if season.season_number is not None and season.season_number > 0
    )
    return available_seasons[0] if available_seasons else None


def resolve_tmdb_selected_episode_count(
    seasons: list[MediaSeasonInfo],
    season_number: int | None,
    fallback: int | None,
) -> int | None:
    if season_number is None:
        return fallback
    for season in seasons:
        if season.season_number == season_number:
            return season.episode_count or fallback
    return fallback


def _date_part(value: str | None) -> str | None:
    if not value:
        return None
    text = str(value)
    if len(text) < 10:
        return None
    return text[:10]


def _parse_date(value: str | None) -> date | None:
    text = _date_part(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _episode_sort_key(episode: EpisodeInfo) -> tuple[str, int, int]:
    return (episode.air_date or "", int(episode.season_number or 0), int(episode.episode_number or 0))


def _to_schedule_episode(episode: EpisodeInfo | None) -> ScheduleEpisode | None:
    if not episode:
        return None
    return ScheduleEpisode(
        season_number=episode.season_number,
        episode_number=episode.episode_number,
        air_date=episode.air_date,
        title=episode.title,
    )


def _to_episode_info(episode: ScheduleEpisode | None) -> EpisodeInfo | None:
    if not episode or not episode.season_number or not episode.episode_number:
        return None
    return EpisodeInfo(
        season_number=episode.season_number,
        episode_number=episode.episode_number,
        air_date=episode.air_date,
        title=episode.title,
    )


def _aired_episodes(episodes: list[EpisodeInfo]) -> list[EpisodeInfo]:
    today = date.today()
    return [
        episode
        for episode in episodes
        if (air_date := _parse_date(episode.air_date)) and air_date <= today
    ]


def _next_episode(episodes: list[EpisodeInfo]) -> EpisodeInfo | None:
    today = date.today()
    for episode in episodes:
        air_date = _parse_date(episode.air_date)
        if air_date and air_date > today:
            return episode
    return None


def _is_next_episode_valid(
    next_episode: ScheduleEpisode | None,
    latest_aired_episode: ScheduleEpisode | None,
    total_episodes: int | None,
) -> bool:
    if not next_episode:
        return False
    air_date = _parse_date(next_episode.air_date)
    if not air_date or air_date <= date.today():
        return False
    if total_episodes and next_episode.episode_number and next_episode.episode_number > total_episodes:
        return False
    if (
        latest_aired_episode
        and latest_aired_episode.season_number is not None
        and next_episode.season_number is not None
        and latest_aired_episode.season_number == next_episode.season_number
        and latest_aired_episode.episode_number
        and next_episode.episode_number
        and next_episode.episode_number <= latest_aired_episode.episode_number
    ):
        return False
    return True


def _tv_status_label(
    status: str | None,
    aired_count: int,
    total_episodes: int | None,
    next_episode: ScheduleEpisode | None,
) -> str:
    if next_episode:
        return "Airing"
    if total_episodes and aired_count >= total_episodes:
        return "Ended"
    if (status or "").strip().lower() == "ended":
        return "Ended"
    return "Airing"


def _build_tv_schedule_summary(
    *,
    details: ProviderMediaBundle,
    selected_season: int | None,
    selected_episode_count: int | None,
    networks: list[SchedulePlatform],
) -> MediaScheduleSummary | None:
    season_details = details.selected_season_details
    if not season_details or not selected_season:
        return None
    if season_details.season_number != selected_season:
        return None

    season_episodes = [
        episode
        for episode in season_details.episodes
        if int(episode.episode_number or 0) > 0
    ]
    season_episodes.sort(key=_episode_sort_key)
    aired = _aired_episodes(season_episodes)
    latest_aired_episode = _to_schedule_episode(aired[-1]) if aired else None
    next_episode = _to_schedule_episode(_next_episode(season_episodes))
    if not _is_next_episode_valid(next_episode, latest_aired_episode, selected_episode_count):
        next_episode = None
    if not next_episode:
        fallback_next_episode = _to_schedule_episode(details.next_episode_to_air)
        if _is_next_episode_valid(fallback_next_episode, latest_aired_episode, selected_episode_count):
            next_episode = fallback_next_episode

    first_air_date = _date_part(season_details.air_date)
    if not first_air_date:
        first_air_date = next(
            (_date_part(episode.air_date) for episode in season_episodes if _date_part(episode.air_date)),
            None,
        )
    return MediaScheduleSummary(
        media_type=MediaType.tv,
        status_label=_tv_status_label(details.status, len(aired), selected_episode_count, next_episode),
        first_air_date=first_air_date or details.first_air_date or details.release_date,
        networks=networks,
        aired_episode_count=len(aired),
        latest_aired_episode=latest_aired_episode,
        next_episode_to_air=next_episode,
    )


def _build_tv_airings(details: ProviderMediaBundle, networks: list[SchedulePlatform]) -> list[ScheduleAiring]:
    season_details = details.selected_season_details
    if not season_details:
        return []
    airings: list[ScheduleAiring] = []
    for episode in season_details.episodes:
        air_date = _date_part(episode.air_date)
        if not air_date:
            continue
        airings.append(
            ScheduleAiring(
                date=air_date,
                kind="tv_episode_air",
                season_number=episode.season_number,
                episode_number=episode.episode_number,
                episode_title=episode.title,
                platforms=networks,
            )
        )
    airings.sort(key=lambda item: (item.date, int(item.season_number or 0), int(item.episode_number or 0)))
    return airings


def _build_movie_airings(schedule: MediaScheduleSummary) -> list[ScheduleAiring]:
    airings: list[ScheduleAiring] = []
    if schedule.theatrical_release_date:
        airings.append(ScheduleAiring(date=schedule.theatrical_release_date, kind="movie_theatrical_release"))
    if schedule.digital_release_date:
        airings.append(
            ScheduleAiring(
                date=schedule.digital_release_date,
                kind="movie_digital_release",
                platforms=list(schedule.online_platforms),
            )
        )
    if schedule.physical_release_date:
        airings.append(ScheduleAiring(date=schedule.physical_release_date, kind="movie_physical_release"))
    return airings


def normalize_tmdb_vendors(
    tmdb_id: int,
    subject_type_value: str,
    cn_vendors: ProviderWatchProviders | None,
    us_vendors: ProviderWatchProviders | None,
) -> list[Vendor]:
    normalized: list[Vendor] = []
    seen: set[str] = set()
    for region, payload in (("CN", cn_vendors), ("US", us_vendors)):
        if not payload:
            continue
        watch_url = f"https://www.themoviedb.org/{subject_type_value}/{tmdb_id}/watch?locale={region}"
        for provider_list in (payload.flatrate, payload.ads, payload.free, payload.buy, payload.rent):
            for provider in provider_list:
                provider_id = provider.id
                provider_name = provider.name
                key = str(provider_id or provider_name or "").strip().lower()
                if not key or key in seen:
                    continue
                seen.add(key)
                normalized.append(
                    Vendor(
                        id=str(provider_id) if provider_id is not None else None,
                        name=provider_name,
                        logo=provider.logo,
                        url=provider.url or watch_url,
                    )
                )
    return dedupe_vendors(normalized)


def build_tmdb_media_info(
    mid: MediaID,
    details: ProviderMediaBundle,
    imdb_id: str | None,
    vote_average: float | None,
    rating_count: int | None,
    rating_source: str,
    season_number: int | None,
    vendors: list[Vendor],
    douban_id: str | None = None,
    episode_count_override: int | None = None,
) -> MediaFullInfo:
    has_display_rating = vote_average is not None and vote_average > 0
    douban_vote_average = vote_average if rating_source == "douban" and has_display_rating else None
    douban_rating_count = rating_count if rating_source == "douban" and has_display_rating else None
    tmdb_vote_average = details.rating.value if details.rating.value is not None and details.rating.value > 0 else None
    tmdb_rating_count = details.rating.count if tmdb_vote_average is not None else None
    source = subject_type(mid.media_type)
    src_date = details.release_date if source == "movie" else details.first_air_date
    seasons = list(details.seasons)
    requested_season = season_number
    if requested_season is None and mid.media_type == MediaType.tv and details.selected_season_details:
        requested_season = details.selected_season_details.season_number
    selected_season = resolve_tmdb_selected_season(seasons, requested_season, None)
    selected_episode_count = resolve_tmdb_selected_episode_count(seasons, selected_season, details.episodes_count)
    season_detail_count = (
        details.selected_season_details.episode_count
        if details.selected_season_details
        and details.selected_season_details.season_number == selected_season
        and details.selected_season_details.episode_count is not None
        else None
    )
    if season_detail_count is not None and (selected_episode_count is None or season_detail_count > selected_episode_count):
        selected_episode_count = season_detail_count
        seasons = [
            season.model_copy(update={"episode_count": selected_episode_count})
            if season.season_number == selected_season
            else season
            for season in seasons
        ]
    if (
        mid.media_type == MediaType.tv
        and selected_season is not None
        and episode_count_override is not None
        and episode_count_override > 0
    ):
        selected_episode_count = int(episode_count_override)
        seasons = [
            season.model_copy(update={
                "episode_count_override": selected_episode_count,
            })
            if season.season_number == selected_season
            else season
            for season in seasons
        ]
    online_platforms = [
        SchedulePlatform(id=vendor.id, name=vendor.name, logo=vendor.logo, url=vendor.url)
        for vendor in vendors
        if vendor.name
    ]
    networks = [
        SchedulePlatform(id=network.id, name=network.name, logo=network.logo)
        for network in details.networks
        if network.name
    ]
    schedule = None
    premiere_release_date = model_field_value(details, "premiere_release_date")
    theatrical_limited_release_date = model_field_value(details, "theatrical_limited_release_date")
    theatrical_release_date = model_field_value(details, "theatrical_release_date")
    digital_release_date = model_field_value(details, "digital_release_date")
    physical_release_date = model_field_value(details, "physical_release_date")
    tv_release_date = model_field_value(details, "tv_release_date")
    if mid.media_type == MediaType.movie:
        schedule = MediaScheduleSummary(
            media_type=MediaType.movie,
            premiere_release_date=premiere_release_date,
            theatrical_limited_release_date=theatrical_limited_release_date,
            theatrical_release_date=theatrical_release_date or details.release_date,
            digital_release_date=digital_release_date,
            physical_release_date=physical_release_date,
            tv_release_date=tv_release_date,
            release_dates=model_field_list(details, "release_dates"),
            online_platforms=online_platforms,
        )
    elif mid.media_type == MediaType.tv:
        schedule = _build_tv_schedule_summary(
            details=details,
            selected_season=selected_season,
            selected_episode_count=selected_episode_count,
            networks=networks,
        )
        if schedule:
            schedule = schedule.model_copy(update={"online_platforms": online_platforms})
    latest_aired_episode = _to_episode_info(schedule.latest_aired_episode) if schedule else None
    next_episode_to_air = _to_episode_info(schedule.next_episode_to_air) if schedule else details.next_episode_to_air
    year = _resolve_media_year(
        src_date=src_date,
        schedule=schedule,
        seasons=seasons,
        selected_season=selected_season,
    )
    return MediaFullInfo(
        media_id=mid,
        title=details.title,
        original_title=details.original_title,
        year=year,
        media_type=mid.media_type,
        imdb_id=imdb_id,
        douban_id=douban_id,
        tmdb_id=int(details.provider_id) if details.provider_id else None,
        primary_metadata_source="tmdb",
        tvdb_id=details.external_ids.tvdb_id,
        overview=details.overview,
        genres=details.genres,
        poster_path=details.poster_path,
        backdrop_path=details.backdrop_path,
        actors=details.actors,
        directors=details.directors,
        studios=details.studios,
        networks=networks,
        duration=details.runtime,
        vendors=vendors,
        rating_count=rating_count,
        vote_average=vote_average,
        vote_count=rating_count,
        rating_source=rating_source,
        douban_vote_average=douban_vote_average,
        douban_rating_count=douban_rating_count,
        tmdb_vote_average=tmdb_vote_average,
        tmdb_rating_count=tmdb_rating_count,
        release_date=details.release_date,
        premiere_release_date=premiere_release_date,
        theatrical_limited_release_date=theatrical_limited_release_date,
        theatrical_release_date=theatrical_release_date,
        digital_release_date=digital_release_date,
        physical_release_date=physical_release_date,
        tv_release_date=tv_release_date,
        release_dates=model_field_list(details, "release_dates"),
        first_air_date=details.first_air_date,
        episodes_count=selected_episode_count if mid.media_type == MediaType.tv else None,
        episode_count_override=episode_count_override if mid.media_type == MediaType.tv else None,
        seasons_count=details.seasons_count or len(seasons),
        season_number=selected_season if mid.media_type == MediaType.tv else None,
        seasons=seasons,
        next_episode_to_air=next_episode_to_air,
        status_label=schedule.status_label if schedule else None,
        aired_episode_count=schedule.aired_episode_count if schedule else 0,
        latest_aired_episode=latest_aired_episode,
        online_platforms=online_platforms,
        schedule=schedule,
        airings=_build_movie_airings(schedule) if mid.media_type == MediaType.movie and schedule else _build_tv_airings(details, networks),
        status=details.status,
        original_language=details.original_language,
    )


def pick_best_tmdb_search_id(title: str, results: list[ProviderSearchItem]) -> int | None:
    if not results:
        return None
    best: ProviderSearchItem | None = None
    best_ratio = 0.0
    for result in results:
        candidates = [result.title]
        if any(item.strip() == (title or "").strip() for item in candidates):
            return int(result.provider_id)
        normalized_candidates = [normalize_title(item) for item in candidates]
        target_normalized = normalize_title(title)
        if any(item == target_normalized for item in normalized_candidates if item):
            return int(result.provider_id)
        max_ratio = max(
            [SequenceMatcher(None, target_normalized, item).ratio() for item in normalized_candidates if item] or [0.0]
        )
        if max_ratio > best_ratio:
            best_ratio = max_ratio
            best = result
    return int(best.provider_id) if best and best_ratio >= 0.45 else int(results[0].provider_id)
