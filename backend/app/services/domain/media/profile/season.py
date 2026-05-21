from __future__ import annotations

from app.schemas.domain.media import MediaFullInfo, MediaSimpleInfo
from app.schemas.domain.media_types import MediaType


def apply_media_season_context[T: MediaFullInfo | MediaSimpleInfo](media: T, season_number: int | None) -> T:
    if media.media_type != MediaType.tv or season_number is None:
        return media
    if season_number <= 0:
        return media
    updates = {"season_number": int(season_number)}
    try:
        seasons = media.seasons
    except AttributeError:
        seasons = []
    if seasons:
        selected = next((season for season in seasons if season.season_number == int(season_number)), None)
        if selected:
            updates["douban_id"] = selected.douban_id
            updates["douban_vote_average"] = selected.douban_vote_average
            updates["douban_rating_count"] = selected.douban_rating_count
            if selected.douban_id and selected.douban_vote_average is not None:
                updates["vote_average"] = selected.douban_vote_average
                updates["rating_count"] = selected.douban_rating_count
                updates["vote_count"] = selected.douban_rating_count
                updates["rating_source"] = "douban"
            override = selected.episode_count_override
            if override is not None and override > 0:
                updates["episodes_count"] = int(override)
                updates["episode_count_override"] = int(override)
            elif selected.episode_count is not None:
                updates["episodes_count"] = selected.episode_count
                updates["episode_count_override"] = None
    return media.model_copy(update=updates)
