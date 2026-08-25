from __future__ import annotations

from collections.abc import Iterable

from app.schemas.domain.torrent import TorrentFileItem, TorrentMetadata


def torrent_file_matches_season(
    metadata: TorrentMetadata,
    file_item: TorrentFileItem,
    season_number: int | None,
) -> bool:
    if season_number is None:
        return True
    seasons = _explicit_file_seasons(metadata, file_item)
    return not seasons or season_number in seasons


def torrent_episodes_for_season(
    metadata: TorrentMetadata,
    season_number: int | None,
) -> set[int]:
    if season_number is None:
        return set(metadata.get_episodes())
    episodes: set[int] = set()
    for file_item in metadata.files:
        if torrent_file_matches_season(metadata, file_item, season_number):
            episodes.update(file_item.get_episodes())
    return episodes


def select_torrent_episode_files(
    metadata: TorrentMetadata,
    *,
    season_number: int | None,
    episodes: set[int],
) -> list[int]:
    return [
        index
        for index, file_item in enumerate(metadata.files)
        if torrent_file_matches_season(metadata, file_item, season_number)
        and file_item.get_episodes()
        and file_item.get_episodes() & episodes
    ]


def selected_files_have_season_conflict(
    metadata: TorrentMetadata,
    *,
    season_number: int | None,
    selected_files: Iterable[int] | None,
) -> bool:
    if season_number is None:
        return False
    indices = list(selected_files or range(len(metadata.files)))
    if not indices:
        seasons = _explicit_metadata_seasons(metadata)
        return bool(seasons and season_number not in seasons)
    for index in indices:
        if 0 <= index < len(metadata.files) and not torrent_file_matches_season(
            metadata,
            metadata.files[index],
            season_number,
        ):
            return True
    return False


def _explicit_file_seasons(
    metadata: TorrentMetadata,
    file_item: TorrentFileItem,
) -> set[int]:
    if file_item.attrs and file_item.attrs.seasons:
        return {season for season in file_item.attrs.seasons if season > 0}
    if metadata.attrs and metadata.attrs.seasons:
        return _explicit_metadata_seasons(metadata)
    return set()


def _explicit_metadata_seasons(metadata: TorrentMetadata) -> set[int]:
    if not metadata.attrs or not metadata.attrs.seasons:
        return set()
    return {season for season in metadata.attrs.seasons if season > 0}
