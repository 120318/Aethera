from typing import Annotated

from app.api.deps import OptionalMediaIDParam
from app.schemas.media_id import MediaID
from app.schemas.domain.media import MediaFullInfo
from app.schemas.domain.media_source import MediaSourceName
from app.schemas.domain.media_types import MediaType
from app.services.application.views.media_detail import media_detail_application_service
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

router = APIRouter()


class MediaDetailResponse(BaseModel):
    media: MediaFullInfo


@router.get("/detail", response_model=MediaDetailResponse)
async def get_media_detail(
    mid: MediaID | None = Depends(OptionalMediaIDParam),
    source: MediaSourceName | None = Query(None),
    source_id: str | None = Query(None),
    media_type: MediaType | None = Query(None),
    season_number: Annotated[int | None, Query(gt=0)] = None,
) -> MediaDetailResponse:
    media = await media_detail_application_service.get_detail(
        media_id=mid,
        source=source,
        source_id=source_id,
        media_type=media_type,
        season_number=season_number,
    )
    return MediaDetailResponse(media=media)
