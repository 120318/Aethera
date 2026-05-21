from datetime import date

from app.schemas.domain.managed_media_profile import ManagedMediaProfile
from app.schemas.domain.media_types import MediaType
from app.schemas.domain.schedule import ScheduleAiring
from app.schemas.exception import InvalidCalendarRangeException
from app.schemas.media_id import MediaID
from app.schemas.runtime.calendar import CalendarAiringItem, CalendarAiringsResponse, CalendarScope
from app.services.domain.media import media_service
from app.services.domain.subscription.query_service import subscription_query_service


def _parse_iso_date(value: str, name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise InvalidCalendarRangeException("backendErrors.calendarDateInvalid", params={"name": name})


def _in_range(value: str, start: date, end: date) -> bool:
    try:
        parsed = date.fromisoformat(value[:10])
    except ValueError:
        return False
    return start <= parsed <= end


def _sub_matches_scope(active: bool, followed: bool, scope: CalendarScope) -> bool:
    if scope == "subscribed":
        return active
    if scope == "followed":
        return followed and not active
    return followed or active


def _display_rating(profile: ManagedMediaProfile) -> tuple[float | None, int | None, str | None]:
    if profile.douban_vote_average is not None:
        return profile.douban_vote_average, profile.douban_rating_count, "douban"
    tmdb_vote_average = profile.tmdb_vote_average
    tmdb_rating_count = profile.tmdb_rating_count
    if tmdb_vote_average is None and profile.rating_source == "tmdb":
        tmdb_vote_average = profile.vote_average
        tmdb_rating_count = profile.rating_count
    return tmdb_vote_average, tmdb_rating_count, "tmdb" if tmdb_vote_average is not None else profile.rating_source


def _airing_to_item(profile: ManagedMediaProfile, airing: ScheduleAiring) -> CalendarAiringItem:
    vote_average, rating_count, rating_source = _display_rating(profile)
    return CalendarAiringItem(
        date=airing.date,
        kind=airing.kind,
        media_id=profile.media_id,
        media_type=profile.media_type,
        title=profile.title,
        year=profile.year,
        poster=profile.poster_path,
        vote_average=vote_average,
        vote_count=rating_count,
        rating_count=rating_count,
        rating_source=rating_source,
        platforms=airing.platforms,
        season_number=airing.season_number,
        episode_number=airing.episode_number,
        episode_title=airing.episode_title,
    )


def _calendar_media_key(media_id: MediaID, season_number: int | None) -> str:
    return f"{media_id}:{season_number or ''}"


def _profile_airing_matches_season(profile: ManagedMediaProfile, season_number: int | None, airing: ScheduleAiring) -> bool:
    if profile.media_type != MediaType.tv:
        return True
    if season_number is None:
        return True
    return airing.season_number == season_number


def _append_profile_airings(
    items: list[CalendarAiringItem],
    profile: ManagedMediaProfile,
    season_number: int | None,
    start: date,
    end: date,
) -> None:
    for airing in profile.airings:
        if not _profile_airing_matches_season(profile, season_number, airing):
            continue
        if _in_range(airing.date, start, end):
            items.append(_airing_to_item(profile, airing))


async def build_calendar_airings(from_date: str, to_date: str, scope: CalendarScope) -> CalendarAiringsResponse:
    start = _parse_iso_date(from_date, "from")
    end = _parse_iso_date(to_date, "to")
    if start > end:
        raise InvalidCalendarRangeException("backendErrors.calendarRangeInvalid")
    if (end - start).days > 120:
        raise InvalidCalendarRangeException("backendErrors.calendarRangeTooLarge")

    subscriptions = [
        subscription
        for subscription in await subscription_query_service.list_states()
        if _sub_matches_scope(subscription.active, subscription.followed, scope)
    ]
    if not subscriptions:
        return CalendarAiringsResponse(from_date=from_date, to_date=to_date, scope=scope, count=0, data=[])

    seen: set[str] = set()
    targets: list[tuple[MediaID, int | None]] = []
    for subscription in subscriptions:
        media_key = _calendar_media_key(subscription.media_id, subscription.season_number)
        if media_key in seen:
            continue
        seen.add(media_key)
        targets.append((subscription.media_id, subscription.season_number))

    profiles_by_target = await media_service.list_profiles_by_media_targets(targets)
    items: list[CalendarAiringItem] = []
    for media_id, season_number in targets:
        profile = profiles_by_target.get(_calendar_media_key(media_id, season_number))
        if not profile or not profile.detail_ready:
            continue
        _append_profile_airings(items, profile, season_number, start, end)

    items.sort(key=lambda item: (item.date, item.title or "", int(item.season_number or 0), int(item.episode_number or 0)))
    return CalendarAiringsResponse(from_date=from_date, to_date=to_date, scope=scope, count=len(items), data=items)
