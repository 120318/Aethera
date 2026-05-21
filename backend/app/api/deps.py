from typing import Optional

from fastapi import Query

from app.schemas.domain.media_types import MediaType
from app.schemas.exception import RequestParamException
from app.schemas.exception.exceptions import InvalidRequestException
from app.schemas.media_id import MediaID


def MediaIDParam(media_id: str = Query(...)) -> MediaID:
    """FastAPI dependency to parse a query param string into MediaID.

    text：text endpoint text mid: MediaID = Depends(MediaIDParam)
    """
    try:
        return MediaID.parse(media_id)
    except Exception as e:
        raise RequestParamException("media_id", str(media_id)) from e


def OptionalMediaIDParam(media_id: Optional[str] = Query(None)) -> Optional[MediaID]:
    if media_id is None:
        return None
    try:
        return MediaID.parse(media_id)
    except Exception as e:
        raise RequestParamException("media_id", str(media_id)) from e


def MediaIDPath(media_id: str) -> MediaID:
    try:
        return MediaID.parse(media_id)
    except Exception as e:
        raise RequestParamException("media_id", str(media_id)) from e


def require_tv_season(media_id: MediaID, season_number: int | None) -> int | None:
    if media_id.media_type != MediaType.tv:
        return None
    if season_number is None or season_number <= 0:
        raise InvalidRequestException("backendErrors.seasonRequired")
    return int(season_number)
