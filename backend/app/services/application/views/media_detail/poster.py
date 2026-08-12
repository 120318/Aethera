from app.schemas.domain.media import MediaFullInfo
from app.schemas.domain.media_types import MediaType


def apply_media_detail_poster(media: MediaFullInfo, season_number: int | None) -> MediaFullInfo:
    if media.media_type != MediaType.tv or season_number is None or season_number <= 0:
        return media
    selected_season = next(
        (season for season in media.seasons if season.season_number == int(season_number)),
        None,
    )
    if not selected_season or not selected_season.poster_path:
        return media
    return media.model_copy(update={"poster_path": selected_season.poster_path})
