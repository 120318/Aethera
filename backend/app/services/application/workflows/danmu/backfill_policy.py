from __future__ import annotations

from datetime import date, timedelta

from app.schemas.domain.library import LibraryFile
from app.schemas.domain.media import MediaFullInfo
from app.schemas.domain.media_types import MediaType


def is_recently_watchable(media: MediaFullInfo, library_file: LibraryFile, recent_days: int) -> bool:
    cutoff = date.today() - timedelta(days=max(1, int(recent_days)))
    today = date.today()
    return any(cutoff <= item <= today for item in watchable_dates(media, library_file))


def watchable_dates(media: MediaFullInfo, library_file: LibraryFile) -> list[date]:
    raw_dates: list[str] = []
    if media.media_type == MediaType.movie:
        raw_dates.extend(
            date_value
            for date_value in [
                media.digital_release_date,
                media.theatrical_release_date,
                media.release_date,
            ]
            if date_value
        )
    else:
        episode_number = episode_number_for_file(library_file)
        season_number = season_number_for_file(library_file)
        for airing in media.airings:
            if airing.kind != "tv_episode_air":
                continue
            if episode_number is not None and airing.episode_number != episode_number:
                continue
            if season_number is not None and airing.season_number != season_number:
                continue
            raw_dates.append(airing.date)
        if media.latest_aired_episode and media.latest_aired_episode.air_date:
            raw_dates.append(media.latest_aired_episode.air_date)
        raw_dates.extend(date_value for date_value in [media.first_air_date, media.release_date] if date_value)
    return [parsed for value in raw_dates if (parsed := parse_date(value))]


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def episode_number_for_file(library_file: LibraryFile) -> int | None:
    attrs = library_file.resource_attributes
    episodes = list(attrs.episodes or []) if attrs else []
    return int(episodes[0]) if len(episodes) == 1 else None


def season_number_for_file(library_file: LibraryFile) -> int | None:
    attrs = library_file.resource_attributes
    seasons = list(attrs.seasons or []) if attrs else []
    return int(seasons[0]) if len(seasons) == 1 else None
