from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date
from enum import Enum

from app.schemas.domain.managed_media_profile import ManagedMediaProfile
from app.schemas.domain.media_types import MediaType
from app.services.domain.media.profile.access import model_field_list, model_field_value


SECONDS_PER_DAY = 86400

HOT_TV_SCHEDULE_INTERVAL_SECONDS = 3600
UPCOMING_MOVIE_SCHEDULE_INTERVAL_SECONDS = 21600
RECENT_SCHEDULE_INTERVAL_SECONDS = SECONDS_PER_DAY
COLD_SCHEDULE_INTERVAL_SECONDS = 7 * SECONDS_PER_DAY

HOT_DETAIL_INTERVAL_SECONDS = SECONDS_PER_DAY
COLD_DETAIL_INTERVAL_SECONDS = 7 * SECONDS_PER_DAY


class ProfileRefreshTier(str, Enum):
    hot_tv = "hot_tv"
    upcoming_movie = "upcoming_movie"
    recent = "recent"
    cold = "cold"


@dataclass(frozen=True)
class ProfileRefreshDecision:
    tier: ProfileRefreshTier
    refresh_profile: bool
    refresh_schedule: bool


def _parse_ymd(value: str | None) -> date | None:
    if not value:
        return None
    try:
        text = str(value).strip()
        if len(text) >= 10:
            text = text[:10]
        year, month, day = text.split("-")
        return date(int(year), int(month), int(day))
    except ValueError:
        return None


def _is_due(updated_at: float | None, interval_seconds: int, now: float) -> bool:
    if not updated_at:
        return True
    return now - updated_at >= interval_seconds


def _tv_air_dates(profile: ManagedMediaProfile) -> list[date]:
    dates: list[date] = []
    latest = _parse_ymd(profile.latest_aired_episode.air_date if profile.latest_aired_episode else None)
    next_air = _parse_ymd(profile.next_episode_to_air.air_date if profile.next_episode_to_air else None)
    if latest:
        dates.append(latest)
    if next_air:
        dates.append(next_air)
    for airing in profile.airings:
        air_date = _parse_ymd(airing.date)
        if air_date:
            dates.append(air_date)
    return dates


def _movie_release_dates(profile: ManagedMediaProfile) -> list[date]:
    values = [
        model_field_value(profile, "premiere_release_date"),
        model_field_value(profile, "theatrical_limited_release_date"),
        model_field_value(profile, "theatrical_release_date"),
        model_field_value(profile, "digital_release_date"),
        model_field_value(profile, "physical_release_date"),
        model_field_value(profile, "tv_release_date"),
        profile.release_date,
    ]
    dates = [_parse_ymd(value) for value in values]
    for release in model_field_list(profile, "release_dates"):
        dates.append(_parse_ymd(release.release_date))
    return [release_date for release_date in dates if release_date]


def _classify_tv(profile: ManagedMediaProfile, today: date) -> ProfileRefreshTier:
    status_text = f"{profile.status or ''} {profile.status_label or ''}".lower()
    if profile.next_episode_to_air:
        return ProfileRefreshTier.hot_tv
    if "airing" in status_text:
        return ProfileRefreshTier.hot_tv
    air_dates = _tv_air_dates(profile)
    if any(abs((air_date - today).days) <= 14 for air_date in air_dates):
        return ProfileRefreshTier.hot_tv
    latest_air = max((air_date for air_date in air_dates if air_date <= today), default=None)
    if latest_air and (today - latest_air).days <= 30:
        return ProfileRefreshTier.recent
    return ProfileRefreshTier.cold


def _classify_movie(profile: ManagedMediaProfile, today: date) -> ProfileRefreshTier:
    release_dates = _movie_release_dates(profile)
    if any(-14 <= (release_date - today).days <= 30 for release_date in release_dates):
        return ProfileRefreshTier.upcoming_movie
    latest_release = max((release_date for release_date in release_dates if release_date <= today), default=None)
    if latest_release and (today - latest_release).days <= 30:
        return ProfileRefreshTier.recent
    return ProfileRefreshTier.cold


def classify_profile_refresh_tier(
    profile: ManagedMediaProfile,
    *,
    today: date | None = None,
) -> ProfileRefreshTier:
    current_day = today or date.today()
    if profile.media_type == MediaType.tv:
        return _classify_tv(profile, current_day)
    return _classify_movie(profile, current_day)


def profile_refresh_decision(
    profile: ManagedMediaProfile,
    *,
    now: float | None = None,
    today: date | None = None,
) -> ProfileRefreshDecision:
    current_time = time.time() if now is None else now
    tier = classify_profile_refresh_tier(profile, today=today)
    schedule_interval = {
        ProfileRefreshTier.hot_tv: HOT_TV_SCHEDULE_INTERVAL_SECONDS,
        ProfileRefreshTier.upcoming_movie: UPCOMING_MOVIE_SCHEDULE_INTERVAL_SECONDS,
        ProfileRefreshTier.recent: RECENT_SCHEDULE_INTERVAL_SECONDS,
        ProfileRefreshTier.cold: COLD_SCHEDULE_INTERVAL_SECONDS,
    }[tier]
    detail_interval = COLD_DETAIL_INTERVAL_SECONDS if tier == ProfileRefreshTier.cold else HOT_DETAIL_INTERVAL_SECONDS
    refresh_profile = _is_due(profile.detail_updated_at, detail_interval, current_time)
    refresh_schedule = _is_due(profile.schedule_updated_at, schedule_interval, current_time)
    return ProfileRefreshDecision(
        tier=tier,
        refresh_profile=refresh_profile,
        refresh_schedule=refresh_schedule,
    )
