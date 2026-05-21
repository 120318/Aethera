import re

from app.schemas.domain.event import Event
from app.schemas.domain.library import LibraryFile
from app.schemas.media_id import MediaID


def positive_season_number(value: int | None) -> int | None:
    if value is None:
        return None
    number = int(value)
    return number if number > 0 else None


def event_season_number(event: Event, media_id: MediaID) -> int | None:
    if event.media is None or event.media.media_id != media_id:
        return None
    return positive_season_number(event.media.season_number)


def library_file_season_number(library_file: LibraryFile) -> int | None:
    file_season = _season_number_from_library_file_path(library_file)
    if file_season is not None:
        return file_season
    attrs = library_file.resource_attributes
    if attrs is None:
        return None
    seasons = {
        number
        for number in (positive_season_number(raw) for raw in attrs.seasons)
        if number is not None
    }
    return next(iter(seasons)) if len(seasons) == 1 else None


def _season_number_from_library_file_path(library_file: LibraryFile) -> int | None:
    values = [
        str(library_file.file_name or ""),
        str(library_file.path or ""),
    ]
    for value in values:
        season_number = _season_number_from_text(value)
        if season_number is not None:
            return season_number
    return None


def _season_number_from_text(value: str) -> int | None:
    if not value:
        return None
    matched = re.search(r"[Ss](\d{1,2})[Ee]\d{1,3}", value)
    if matched:
        return positive_season_number(int(matched.group(1)))
    matched = re.search(r"(?:^|[/\\])Season[ ._-]*(\d{1,2})(?:[/\\]|$)", value, re.IGNORECASE)
    if matched:
        return positive_season_number(int(matched.group(1)))
    return None


def library_files_season_number(library_files: list[LibraryFile]) -> int | None:
    seasons = {
        number
        for number in (library_file_season_number(library_file) for library_file in library_files)
        if number is not None
    }
    return next(iter(seasons)) if len(seasons) == 1 else None


def library_files_season_numbers(library_files: list[LibraryFile]) -> list[int]:
    seasons: set[int] = set()
    for library_file in library_files:
        season_number = library_file_season_number(library_file)
        if season_number is not None:
            seasons.add(season_number)
            continue
    return sorted(seasons)


def library_files_for_season(library_files: list[LibraryFile], season_number: int) -> list[LibraryFile]:
    result: list[LibraryFile] = []
    for library_file in library_files:
        if library_file_season_number(library_file) == season_number:
            result.append(library_file)
    return result
