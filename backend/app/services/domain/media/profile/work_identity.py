from __future__ import annotations

from datetime import date

from app.schemas.domain.managed_media_profile import ManagedMediaProfile
from app.schemas.domain.media import MediaFullInfo
from app.schemas.domain.media_profile_scope import MediaProfileScope
from app.schemas.domain.media_types import MediaType


def _date_value(value: str | None) -> date | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    try:
        return date.fromisoformat(normalized[:10])
    except ValueError:
        return None


def _known_tv_start_dates(
    media: MediaFullInfo,
    existing: ManagedMediaProfile | None,
    scopes: list[MediaProfileScope],
) -> list[date]:
    values = [
        _date_value(media.first_air_date),
        _date_value(existing.first_air_date if existing else None),
        *(_date_value(scope.first_air_date) for scope in scopes),
        *(
            _date_value(scope.air_date)
            for scope in scopes
            if scope.season_number == 1
        ),
        *(
            _date_value(season.air_date)
            for season in media.seasons
            if season.season_number == 1
        ),
    ]
    return [value for value in values if value is not None]


def resolve_tv_work_year(
    incoming_year: int,
    *,
    existing_year: int | None,
    scopes: list[MediaProfileScope],
) -> int:
    """Keep a TV work's original year stable across season-level refreshes."""
    candidates = [int(incoming_year)]
    if existing_year and int(existing_year) > 0:
        candidates.append(int(existing_year))
    candidates.extend(
        value.year
        for scope in scopes
        for value in (_date_value(scope.first_air_date),)
        if value is not None
    )
    candidates.extend(
        value.year
        for scope in scopes
        for value in (_date_value(scope.air_date),)
        if scope.season_number == 1 and value is not None
    )
    return min(candidates)


def with_stable_tv_work_identity(
    media: MediaFullInfo,
    *,
    existing: ManagedMediaProfile | None,
    scopes: list[MediaProfileScope],
) -> MediaFullInfo:
    if media.media_type != MediaType.tv:
        return media

    start_dates = _known_tv_start_dates(media, existing, scopes)
    work_start_date = min(start_dates) if start_dates else None
    first_air_date = work_start_date.isoformat() if work_start_date else media.first_air_date
    year = resolve_tv_work_year(
        media.year,
        existing_year=existing.year if existing else None,
        scopes=scopes,
    )
    if work_start_date:
        year = min(year, work_start_date.year)
    return media.model_copy(update={"year": year, "first_air_date": first_air_date})
