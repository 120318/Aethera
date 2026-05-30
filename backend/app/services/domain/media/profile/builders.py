import time

from app.schemas.domain.managed_media_profile import ManagedMediaProfile
from app.schemas.domain.media import MediaFullInfo, PersonInfo
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.schedule import SchedulePlatform
from app.services.domain.media.profile.access import model_field_list, model_field_value
from app.services.domain.media.schedule.platforms import SchedulePlatformService


def _contains_cjk(text: str | None) -> bool:
    if not text:
        return False
    return any(
        0x3400 <= ord(char) <= 0x4DBF
        or 0x4E00 <= ord(char) <= 0x9FFF
        or 0xF900 <= ord(char) <= 0xFAFF
        for char in text
    )


def _localized_text(incoming: str | None, existing: str | None) -> str | None:
    if _contains_cjk(existing) and not _contains_cjk(incoming):
        return existing
    return incoming


def _localized_text_count(values: list[str]) -> int:
    return sum(1 for value in values if _contains_cjk(value))


def _localized_people_count(values: list[PersonInfo]) -> int:
    return sum(1 for value in values if _contains_cjk(f"{value.name or ''} {value.character or ''}"))


def _localized_text_items(incoming: list[str], existing: list[str]) -> list[str]:
    if existing and _localized_text_count(existing) > _localized_text_count(incoming):
        return existing
    return incoming


def _localized_people_items(incoming: list[PersonInfo], existing: list[PersonInfo]) -> list[PersonInfo]:
    if existing and _localized_people_count(existing) > _localized_people_count(incoming):
        return existing
    return incoming


def _merge_airings(media: MediaFullInfo, existing: ManagedMediaProfile | None):
    return list(media.airings or [])


def _schedule_platforms(media: MediaFullInfo) -> list[SchedulePlatform]:
    return list(media.schedule.platforms) if media.schedule else []


def _platform_key(platform: SchedulePlatform) -> str:
    return f"{(platform.id or '').strip().lower()}|{(platform.name or '').strip().lower()}"


def _airing_networks(media: MediaFullInfo) -> list[SchedulePlatform]:
    platforms: list[SchedulePlatform] = []
    for airing in media.airings or []:
        platforms.extend(list(airing.platforms or []))
    return SchedulePlatformService().dedupe(platforms)


def _merge_networks(media: MediaFullInfo, existing: ManagedMediaProfile | None) -> list[SchedulePlatform]:
    if media.media_type != MediaType.tv:
        return []
    networks = _airing_networks(media)
    return networks or (list(existing.networks) if existing else [])


def _merge_online_platforms(media: MediaFullInfo, existing: ManagedMediaProfile | None) -> list[SchedulePlatform]:
    schedule_platforms = _schedule_platforms(media)
    if media.media_type == MediaType.movie:
        return schedule_platforms or (list(existing.online_platforms) if existing else [])
    network_keys = {_platform_key(platform) for platform in _merge_networks(media, existing)}
    online_platforms = [
        platform
        for platform in schedule_platforms
        if _platform_key(platform) not in network_keys
    ]
    return SchedulePlatformService().dedupe(online_platforms) or (list(existing.online_platforms) if existing else [])


def _merge_seasons(media: MediaFullInfo, existing: ManagedMediaProfile | None) -> list:
    media_seasons = list(media.seasons or [])
    if media.media_type != MediaType.tv or media.season_number is None or media.season_number <= 0:
        return media_seasons
    current = [
        season
        for season in media_seasons
        if season.season_number is not None and int(season.season_number) == int(media.season_number)
    ]
    if not existing:
        return current
    return [
        season
        for season in existing.seasons
        if season.season_number is None or int(season.season_number) != int(media.season_number)
    ] + current


def build_profile_from_media(
    media: MediaFullInfo,
    *,
    existing: ManagedMediaProfile | None,
    is_active: bool,
    episodes_count: int | None,
) -> ManagedMediaProfile:
    now = time.time()
    schedule = media.schedule
    schedule_has_episode_progress = bool(
        schedule
        and (
            schedule.latest_aired_episode
            or schedule.next_episode_to_air
            or int(schedule.aired_episode_count or 0) > 0
        )
    )
    status_label = existing.status_label if existing else None
    aired_episode_count = existing.aired_episode_count if existing else 0
    latest_aired_episode = existing.latest_aired_episode if existing else None
    next_episode_to_air = existing.next_episode_to_air if existing else None
    schedule_updated_at = existing.schedule_updated_at if existing else None
    if schedule_has_episode_progress:
        status_label = schedule.status_label
        aired_episode_count = int(schedule.aired_episode_count or 0)
        latest_aired_episode = schedule.latest_aired_episode
        next_episode_to_air = schedule.next_episode_to_air
        schedule_updated_at = now
    return ManagedMediaProfile(
        media_id=media.media_id,
        media_type=media.media_type,
        title=_localized_text(media.title, existing.title if existing else None),
        original_title=_localized_text(media.original_title, existing.original_title if existing else None),
        poster_path=media.poster_path,
        backdrop_path=media.backdrop_path,
        logo_path=media.logo_path,
        year=media.year,
        overview=_localized_text(media.overview, existing.overview if existing else None),
        genres=_localized_text_items(list(media.genres), list(existing.genres) if existing else []),
        imdb_id=media.imdb_id,
        tmdb_id=media.tmdb_id,
        primary_metadata_source=media.primary_metadata_source,
        metadata_capabilities=media.metadata_capabilities,
        tvdb_id=media.tvdb_id,
        actors=_localized_people_items(list(media.actors), list(existing.actors) if existing else []),
        directors=_localized_people_items(list(media.directors), list(existing.directors) if existing else []),
        studios=_localized_text_items(list(media.studios), list(existing.studios) if existing else []),
        vendors=media.vendors,
        duration=media.duration,
        tmdb_vote_average=media.tmdb_vote_average,
        tmdb_rating_count=media.tmdb_rating_count,
        release_date=media.release_date,
        first_air_date=media.first_air_date,
        seasons_count=media.seasons_count,
        episodes_count=episodes_count,
        seasons=_merge_seasons(media, existing),
        status=media.status,
        original_language=media.original_language,
        status_label=status_label,
        aired_episode_count=aired_episode_count,
        latest_aired_episode=latest_aired_episode,
        next_episode_to_air=next_episode_to_air,
        premiere_release_date=media.premiere_release_date or model_field_value(existing, "premiere_release_date"),
        theatrical_limited_release_date=media.theatrical_limited_release_date or model_field_value(existing, "theatrical_limited_release_date"),
        theatrical_release_date=media.theatrical_release_date or model_field_value(existing, "theatrical_release_date"),
        digital_release_date=media.digital_release_date or model_field_value(existing, "digital_release_date"),
        physical_release_date=media.physical_release_date or model_field_value(existing, "physical_release_date"),
        tv_release_date=media.tv_release_date or model_field_value(existing, "tv_release_date"),
        release_dates=list(media.release_dates or []) or model_field_list(existing, "release_dates"),
        networks=_merge_networks(media, existing),
        online_platforms=_merge_online_platforms(media, existing),
        airings=_merge_airings(media, existing),
        is_active=is_active,
        last_seen_at=now,
        inactive_since=None if is_active else now,
        detail_ready=True,
        simple_info_updated_at=now,
        detail_updated_at=now,
        schedule_updated_at=schedule_updated_at,
        created_at=existing.created_at if existing else now,
        updated_at=now,
    )
