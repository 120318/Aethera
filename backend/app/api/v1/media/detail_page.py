from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import OptionalMediaIDParam
from app.schemas.domain.media_source import MediaSourceName
from app.schemas.domain.media_types import MediaType
from app.schemas.media_id import MediaID
from app.schemas.runtime.media_detail_page import MediaDetailPageResponse
from app.services.application.views.media_detail_page import media_detail_page_application_service

router = APIRouter()


@router.get("/detail-page", response_model=MediaDetailPageResponse)
async def get_media_detail_page(
    mid: MediaID | None = Depends(OptionalMediaIDParam),
    source: MediaSourceName | None = Query(None),
    source_id: str | None = Query(None),
    media_type: MediaType | None = Query(None),
    title: str | None = Query(None),
    year: int | None = Query(None),
    season_number: Annotated[int | None, Query(gt=0)] = None,
    active_tab: str = Query("resources"),
) -> MediaDetailPageResponse:
    return await media_detail_page_application_service.get_page(
        media_id=mid,
        source=source,
        source_id=source_id,
        media_type=media_type,
        title=title,
        year=year,
        season_number=season_number,
        active_tab=active_tab,
    )
