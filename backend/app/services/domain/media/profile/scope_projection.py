from __future__ import annotations

import time

from app.schemas.domain.managed_media_profile import ManagedMediaProfile
from app.schemas.domain.media import MediaFullInfo
from app.schemas.domain.media_profile_scope import MediaProfilePlatform, MediaProfileScope, MediaProfileScopeAiring
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.schedule import ScheduleAiring, ScheduleEpisode, SchedulePlatform
from app.schemas.domain.vendor import Vendor
from app.schemas.exception import SearchMissingSeasonInfoException
from app.services.domain.media.schedule.platforms import SchedulePlatformService


_platform_service = SchedulePlatformService()
_danmu_capable_platform_keys = {"tencent", "qq", "iqiyi", "youku", "bilibili"}


def _platform_key(*values: str | None) -> str | None:
    canonical = _platform_service.canonical_key(*values)
    if canonical:
        return canonical
    for value in values:
        normalized = str(value or "").strip()
        if normalized:
            return normalized.lower()
    return None


def _merge_platform(
    platforms: dict[str, MediaProfilePlatform],
    platform: MediaProfilePlatform,
) -> None:
    current = platforms.get(platform.key)
    if not current:
        platforms[platform.key] = platform
        return
    current_roles = set(current.roles)
    incoming_roles = set(platform.roles)
    display_url = current.display_url or platform.display_url
    if incoming_roles & {"airing", "network"}:
        display_url = platform.display_url or current.display_url
    elif current_roles & {"airing", "network"}:
        display_url = current.display_url or platform.display_url
    platforms[platform.key] = MediaProfilePlatform(
        key=current.key,
        id=current.id or platform.id,
        name=current.name or platform.name,
        logo=current.logo or platform.logo,
        region=current.region or platform.region,
        roles=sorted(current_roles | incoming_roles),
        display_url=display_url,
        fetch_url=current.fetch_url or platform.fetch_url,
        source=current.source or platform.source,
    )


def platform_from_schedule(platform: SchedulePlatform, *, role: str, source: str | None = None) -> MediaProfilePlatform | None:
    key = _platform_key(platform.id, platform.name)
    if not key:
        return None
    normalized = _platform_service.normalize(platform)
    return MediaProfilePlatform(
        key=key,
        id=normalized.id,
        name=normalized.name,
        logo=normalized.logo,
        region=normalized.region,
        roles=[role],
        display_url=normalized.url,
        source=source,
    )


def platform_from_vendor(vendor: Vendor) -> MediaProfilePlatform | None:
    key = _platform_key(vendor.id, vendor.name)
    if not key:
        return None
    playback_url = _platform_service._vendor_playback_url(vendor)
    return MediaProfilePlatform(
        key=key,
        id=vendor.id,
        name=vendor.name,
        logo=vendor.logo,
        roles=["danmu", "online"],
        display_url=playback_url,
        fetch_url=vendor.url,
        source="douban",
    )


def platform_to_schedule(platform: MediaProfilePlatform) -> SchedulePlatform:
    return SchedulePlatform(
        id=platform.id,
        name=platform.name,
        logo=platform.logo,
        url=platform.display_url or platform.fetch_url,
        region=platform.region,
    )


def platform_to_vendor(platform: MediaProfilePlatform) -> Vendor:
    return Vendor(
        id=platform.id or platform.key,
        name=platform.name,
        logo=platform.logo,
        url=platform.fetch_url or platform.display_url,
        vtype=platform.source,
    )


def scope_airing_from_schedule(airing: ScheduleAiring, platforms: dict[str, MediaProfilePlatform]) -> MediaProfileScopeAiring:
    platform_keys: list[str] = []
    for airing_platform in airing.platforms:
        platform = platform_from_schedule(airing_platform, role="airing", source="schedule")
        if not platform:
            continue
        _merge_platform(platforms, platform)
        platform_keys.append(platform.key)
    return MediaProfileScopeAiring(
        date=airing.date,
        kind=airing.kind,
        season_number=airing.season_number,
        episode_number=airing.episode_number,
        episode_title=airing.episode_title,
        platform_keys=sorted(set(platform_keys)),
    )


def scope_airing_to_schedule(airing: MediaProfileScopeAiring, platforms: dict[str, MediaProfilePlatform]) -> ScheduleAiring:
    return ScheduleAiring(
        date=airing.date,
        kind=airing.kind,
        season_number=airing.season_number,
        episode_number=airing.episode_number,
        episode_title=airing.episode_title,
        platforms=[
            platform_to_schedule(platforms[key])
            for key in airing.platform_keys
            if key in platforms
        ],
    )


def _to_schedule_episode(episode) -> ScheduleEpisode | None:
    if not episode:
        return None
    return ScheduleEpisode(
        season_number=episode.season_number,
        episode_number=episode.episode_number,
        air_date=episode.air_date,
        title=episode.title,
    )


def scope_number_for_media(media: MediaFullInfo) -> int:
    if media.media_type == MediaType.movie:
        return 0
    if media.season_number is None or media.season_number <= 0:
        raise SearchMissingSeasonInfoException()
    return int(media.season_number)


def _scope_douban_id(
    media: MediaFullInfo,
    selected_season,
    existing: MediaProfileScope | None,
) -> str | None:
    if media.media_type == MediaType.tv:
        return (selected_season.douban_id if selected_season else None) or (existing.douban_id if existing else None)
    return media.douban_id or (existing.douban_id if existing else None)


def _scope_douban_vote_average(
    media: MediaFullInfo,
    selected_season,
    existing: MediaProfileScope | None,
) -> float | None:
    if media.media_type == MediaType.tv:
        selected_rating = selected_season.douban_vote_average if selected_season else None
    else:
        selected_rating = media.douban_vote_average
    return selected_rating if selected_rating is not None else existing.douban_vote_average if existing else None


def _scope_douban_rating_count(
    media: MediaFullInfo,
    selected_season,
    existing: MediaProfileScope | None,
) -> int | None:
    if media.media_type == MediaType.tv:
        selected_count = selected_season.douban_rating_count if selected_season else None
    else:
        selected_count = media.douban_rating_count
    return selected_count if selected_count is not None else existing.douban_rating_count if existing else None


def build_scope_from_media(media: MediaFullInfo, existing: MediaProfileScope | None = None) -> MediaProfileScope | None:
    scope_number = scope_number_for_media(media)
    now = time.time()
    platforms: dict[str, MediaProfilePlatform] = {}
    airing_platform_keys: set[str] = set()
    for existing_platform in existing.platforms if existing else []:
        key = _platform_key(existing_platform.id, existing_platform.name, existing_platform.key)
        if not key:
            continue
        _merge_platform(platforms, existing_platform.model_copy(update={"key": key}))
    for vendor in media.vendors:
        platform = platform_from_vendor(vendor)
        if platform:
            _merge_platform(platforms, platform)
    for airing in media.airings:
        for airing_platform in airing.platforms:
            platform = platform_from_schedule(airing_platform, role="network", source="schedule")
            if platform:
                airing_platform_keys.add(platform.key)
                _merge_platform(platforms, platform)
    if media.schedule and (media.media_type != MediaType.tv or airing_platform_keys):
        for schedule_platform in media.schedule.platforms:
            platform = platform_from_schedule(
                schedule_platform,
                role="online",
                source="schedule",
            )
            if media.media_type == MediaType.tv and platform and platform.key in airing_platform_keys:
                continue
            if platform:
                _merge_platform(platforms, platform)
    scope_airings = [
        scope_airing_from_schedule(airing, platforms)
        for airing in media.airings
        if media.media_type != MediaType.tv or airing.season_number == scope_number
    ] or (list(existing.airings) if existing else [])
    selected_season = next(
        (
            season
            for season in media.seasons
            if media.media_type == MediaType.tv and int(season.season_number) == scope_number
        ),
        None,
    )
    schedule = media.schedule
    return MediaProfileScope(
        media_id=media.media_id,
        season_number=scope_number,
        media_type=media.media_type,
        name=selected_season.name if selected_season else existing.name if existing else None,
        air_date=selected_season.air_date if selected_season else existing.air_date if existing else media.release_date,
        episode_count=selected_season.episode_count if selected_season else existing.episode_count if existing else None,
        episode_count_override=media.episode_count_override or (selected_season.episode_count_override if selected_season else None),
        poster_path=selected_season.poster_path if selected_season else existing.poster_path if existing else media.poster_path,
        douban_id=_scope_douban_id(media, selected_season, existing),
        douban_vote_average=_scope_douban_vote_average(media, selected_season, existing),
        douban_rating_count=_scope_douban_rating_count(media, selected_season, existing),
        first_air_date=media.first_air_date or (schedule.first_air_date if schedule else None) or (existing.first_air_date if existing else None),
        status_label=(schedule.status_label if schedule else None) or (existing.status_label if existing else None),
        aired_episode_count=(schedule.aired_episode_count if schedule else 0) or (existing.aired_episode_count if existing else 0),
        latest_aired_episode=_to_schedule_episode((schedule.latest_aired_episode if schedule else None) or (existing.latest_aired_episode if existing else None)),
        next_episode_to_air=_to_schedule_episode((schedule.next_episode_to_air if schedule else None) or (existing.next_episode_to_air if existing else None)),
        premiere_release_date=media.premiere_release_date or (schedule.premiere_release_date if schedule else None) or (existing.premiere_release_date if existing else None),
        theatrical_limited_release_date=media.theatrical_limited_release_date or (schedule.theatrical_limited_release_date if schedule else None) or (existing.theatrical_limited_release_date if existing else None),
        theatrical_release_date=media.theatrical_release_date or (schedule.theatrical_release_date if schedule else None) or (existing.theatrical_release_date if existing else None),
        digital_release_date=media.digital_release_date or (schedule.digital_release_date if schedule else None) or (existing.digital_release_date if existing else None),
        physical_release_date=media.physical_release_date or (schedule.physical_release_date if schedule else None) or (existing.physical_release_date if existing else None),
        tv_release_date=media.tv_release_date or (schedule.tv_release_date if schedule else None) or (existing.tv_release_date if existing else None),
        release_dates=list(media.release_dates or []) or (list(schedule.release_dates) if schedule else []) or (list(existing.release_dates) if existing else []),
        platforms=list(platforms.values()),
        airings=scope_airings,
        updated_at=now,
    )


def build_scopes_from_media(
    media: MediaFullInfo,
    existing_scopes: list[MediaProfileScope],
) -> list[MediaProfileScope]:
    existing_by_number = {scope.season_number: scope for scope in existing_scopes}
    scope = build_scope_from_media(
        media,
        existing=existing_by_number.get(scope_number_for_media(media)),
    )
    return [scope] if scope else []


def apply_scopes_to_profile(
    profile: ManagedMediaProfile,
    scopes: list[MediaProfileScope],
    *,
    season_number: int | None = None,
) -> ManagedMediaProfile:
    selected = select_scope(profile, scopes, season_number=season_number)
    seasons = [
        scope.to_season_info()
        for scope in scopes
        if profile.media_type == MediaType.tv and scope.season_number > 0
    ]
    if not selected:
        return profile.model_copy(update={"seasons": seasons})
    platform_map = {platform.key: platform for platform in selected.platforms}
    networks = [
        platform_to_schedule(platform)
        for platform in selected.platforms
        if "network" in platform.roles
    ]
    online_platforms = [
        platform_to_schedule(platform)
        for platform in selected.platforms
        if "online" in platform.roles or "release" in platform.roles or platform.display_url
    ]
    vendors = [
        platform_to_vendor(platform)
        for platform in selected.platforms
        if "danmu" in platform.roles
        or platform.fetch_url
        or (platform.key in _danmu_capable_platform_keys and platform.display_url)
    ]
    airings = [
        scope_airing_to_schedule(airing, platform_map)
        for airing in selected.airings
    ]
    return profile.model_copy(update={
        "vendors": vendors,
        "seasons": seasons,
        "status_label": selected.status_label,
        "first_air_date": selected.first_air_date,
        "aired_episode_count": selected.aired_episode_count,
        "latest_aired_episode": selected.latest_aired_episode,
        "next_episode_to_air": selected.next_episode_to_air,
        "premiere_release_date": selected.premiere_release_date,
        "theatrical_limited_release_date": selected.theatrical_limited_release_date,
        "theatrical_release_date": selected.theatrical_release_date,
        "digital_release_date": selected.digital_release_date,
        "physical_release_date": selected.physical_release_date,
        "tv_release_date": selected.tv_release_date,
        "release_dates": selected.release_dates,
        "networks": networks,
        "online_platforms": online_platforms,
        "airings": airings,
    })


def select_scope(
    profile: ManagedMediaProfile,
    scopes: list[MediaProfileScope],
    *,
    season_number: int | None = None,
) -> MediaProfileScope | None:
    if profile.media_type == MediaType.movie:
        return next((scope for scope in scopes if scope.season_number == 0), None)
    if season_number and season_number > 0:
        return next((scope for scope in scopes if scope.season_number == season_number), None)
    return None


def has_scope_detail(profile: ManagedMediaProfile, scopes: list[MediaProfileScope], season_number: int | None) -> bool:
    if profile.media_type == MediaType.movie:
        return any(scope.season_number == 0 for scope in scopes)
    if not season_number:
        return False
    return any(scope.season_number == season_number for scope in scopes)
