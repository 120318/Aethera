from typing import Optional

from pydantic import BaseModel

from app.db.repositories.media_external_mapping_repository import MediaExternalMappingRepository
from app.schemas.domain.media import MediaFullInfo, MediaSeasonInfo
from app.schemas.domain.media_types import MediaType
from app.schemas.persistence.media_external_mapping import MediaExternalMappingRecord


class ExternalIdUpdates(BaseModel):
    douban_id: str | None = None
    imdb_id: str | None = None
    tmdb_id: int | None = None

    def model_update(self):
        return self.model_dump(exclude_none=True)


def _episode_count_from_seasons(
    media_type: MediaType,
    seasons: list[MediaSeasonInfo],
    fallback_count: Optional[int],
    *,
    scoped_to_season: bool,
) -> Optional[int]:
    if media_type != MediaType.tv:
        return fallback_count
    season_counts = [
        int(season.episode_count_override)
        if season.episode_count_override is not None and season.episode_count_override > 0
        else season.episode_count
        for season in seasons
        if (
            season.episode_count is not None
            or (season.episode_count_override is not None and season.episode_count_override > 0)
        )
    ]
    if season_counts:
        return sum(int(count) for count in season_counts)
    if scoped_to_season:
        return None
    return fallback_count


def profile_episode_count(media: MediaFullInfo) -> Optional[int]:
    if media.media_type == MediaType.tv and media.season_number is not None:
        selected = next(
            (season for season in media.seasons if int(season.season_number) == int(media.season_number)),
            None,
        )
        if selected:
            if selected.episode_count_override is not None and selected.episode_count_override > 0:
                return int(selected.episode_count_override)
            return selected.episode_count
        return media.episodes_count
    return _episode_count_from_seasons(
        media.media_type,
        media.seasons,
        media.episodes_count,
        scoped_to_season=media.season_number is not None,
    )


def non_douban_rating_updates(media: MediaFullInfo):
    tmdb_vote_average = media.tmdb_vote_average
    tmdb_rating_count = media.tmdb_rating_count
    if tmdb_vote_average is None and media.rating_source == "tmdb":
        tmdb_vote_average = media.vote_average
        tmdb_rating_count = media.rating_count
    return {
        "vote_average": tmdb_vote_average,
        "rating_count": tmdb_rating_count,
        "vote_count": tmdb_rating_count,
        "rating_source": "tmdb" if tmdb_vote_average is not None else None,
    }


def with_cached_season_metadata(media: MediaFullInfo, season_number: Optional[int]) -> MediaFullInfo:
    if media.media_type != MediaType.tv or not season_number:
        return media
    selected = next(
        (season for season in media.seasons if int(season.season_number) == int(season_number)),
        None,
    )
    selected_douban_id = selected.douban_id if selected else None
    updates = {
        "douban_id": selected_douban_id,
        "season_number": int(season_number),
    }
    if selected_douban_id and selected and selected.douban_vote_average is not None:
        updates["douban_vote_average"] = selected.douban_vote_average
        updates["douban_rating_count"] = selected.douban_rating_count
        updates["vote_average"] = selected.douban_vote_average
        updates["rating_count"] = selected.douban_rating_count
        updates["vote_count"] = selected.douban_rating_count
        updates["rating_source"] = "douban"
    if selected and selected.episode_count_override is not None and selected.episode_count_override > 0:
        updates["episodes_count"] = int(selected.episode_count_override)
        updates["episode_count_override"] = int(selected.episode_count_override)
    else:
        updates["episode_count_override"] = None
    if not selected_douban_id:
        updates.update(non_douban_rating_updates(media))
    return media.model_copy(update=updates)


def _external_id_updates(
    media: MediaFullInfo,
    mapping: MediaExternalMappingRecord | None,
    *,
    include_douban_id: bool,
) -> ExternalIdUpdates:
    updates = ExternalIdUpdates()
    if not mapping:
        return updates
    if include_douban_id and mapping.douban_id and media.douban_id != mapping.douban_id:
        updates.douban_id = mapping.douban_id
    if mapping.imdb_id and media.imdb_id != mapping.imdb_id:
        updates.imdb_id = mapping.imdb_id
    if mapping.tmdb_id and media.tmdb_id != mapping.tmdb_id:
        updates.tmdb_id = mapping.tmdb_id
    return updates


def with_season_external_ids(
    media: MediaFullInfo,
    season_number: Optional[int],
    mapping_repo: MediaExternalMappingRepository,
) -> MediaFullInfo:
    effective_season = int(season_number or media.season_number or 0)
    mapping = (
        mapping_repo.find_by_media_id_and_season(media.media_id, effective_season)
        if media.media_type == MediaType.tv and effective_season > 0
        else mapping_repo.find_by_media_id(media.media_id)
    )
    external_id_updates = _external_id_updates(media, mapping, include_douban_id=media.media_type != MediaType.tv)
    external_id_update_data = external_id_updates.model_update()
    if media.media_type != MediaType.tv:
        return media.model_copy(update=external_id_update_data) if external_id_update_data else media
    if effective_season <= 0:
        return media.model_copy(update=external_id_update_data) if external_id_update_data else media

    selected_douban_id = mapping.douban_id if mapping and mapping.douban_id else None
    episode_count_override = (
        int(mapping.episode_count_override)
        if mapping and mapping.episode_count_override is not None and mapping.episode_count_override > 0
        else None
    )

    seasons = [
        season.model_copy(update={
            "douban_id": selected_douban_id,
            "douban_vote_average": media.douban_vote_average if selected_douban_id else None,
            "douban_rating_count": media.douban_rating_count if selected_douban_id else None,
            **(
                {
                    "episode_count_override": episode_count_override,
                }
                if episode_count_override is not None
                else {}
            ),
        })
        if season.season_number is not None and int(season.season_number) == effective_season
        else season
        for season in media.seasons
    ]
    updates = {
        "seasons": seasons,
        "season_number": effective_season,
        "douban_id": selected_douban_id,
        **external_id_update_data,
    }
    if not selected_douban_id:
        updates.update(non_douban_rating_updates(media))
    if episode_count_override is not None:
        updates["episodes_count"] = episode_count_override
        updates["episode_count_override"] = episode_count_override
    else:
        updates["episode_count_override"] = None
    return media.model_copy(update=updates)
