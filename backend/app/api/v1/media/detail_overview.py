from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import MediaIDParam, require_tv_season
from app.schemas.media_id import MediaID
from app.schemas.runtime.media_detail_overview import MediaDetailOverviewResponse
from app.services.application.views.media_detail_overview import media_detail_overview_service

router = APIRouter()


@router.get("/detail-overview", response_model=MediaDetailOverviewResponse)
async def get_media_detail_overview(
    mid: MediaID = Depends(MediaIDParam),
    season_number: Annotated[int | None, Query(gt=0)] = None,
) -> MediaDetailOverviewResponse:
    return await media_detail_overview_service.get_overview(
        mid,
        season_number=require_tv_season(mid, season_number),
    )
