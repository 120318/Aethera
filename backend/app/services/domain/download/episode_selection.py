from __future__ import annotations

from collections.abc import Iterable

from app.schemas.domain.torrent import TorrentMetadata
from app.services.domain.resource.torrent_season import torrent_file_matches_season
from app.services.domain.resource.torrent_file_policy import is_library_download_file, is_shared_torrent_font


def available_episodes(metadata: TorrentMetadata, season_number: int | None) -> list[int]:
    episodes: set[int] = set()
    for file_item in metadata.files:
        if is_library_download_file(metadata, file_item) and torrent_file_matches_season(metadata, file_item, season_number):
            episodes.update(episode for episode in file_item.get_episodes() if episode > 0)
    return sorted(episodes)


def selected_file_indices(
    metadata: TorrentMetadata,
    season_number: int | None,
    episodes: Iterable[int],
) -> list[int]:
    requested = {int(episode) for episode in episodes if int(episode) > 0}
    return sorted(
        file_item.index
        for file_item in metadata.files
        if is_library_download_file(metadata, file_item)
        and torrent_file_matches_season(metadata, file_item, season_number)
        and (file_item.get_episodes() & requested or is_shared_torrent_font(file_item))
    )


def episodes_for_file_indices(metadata: TorrentMetadata, indices: Iterable[int]) -> list[int]:
    selected = set(indices)
    episodes: set[int] = set()
    for file_item in metadata.files:
        if file_item.index in selected:
            episodes.update(episode for episode in file_item.get_episodes() if episode > 0)
    return sorted(episodes)


def resolve_episode_selection(
    metadata: TorrentMetadata,
    season_number: int | None,
    episodes: Iterable[int],
) -> tuple[list[int], list[int]]:
    available = set(available_episodes(metadata, season_number))
    requested = {int(episode) for episode in episodes if int(episode) > 0}
    if not requested or not requested.issubset(available):
        return [], []
    indices = selected_file_indices(metadata, season_number, requested)
    return indices, episodes_for_file_indices(metadata, indices)
