from typing import Annotated

from app.api.deps import MediaIDParam, require_tv_season
from app.schemas.domain.media import MediaTarget
from app.schemas.media_id import MediaID
from app.schemas.runtime.resource_list import ResourceListResponse
from app.services.application.views.resource_status.service import resource_list_service
from fastapi import APIRouter, Depends, Query

router = APIRouter()


@router.get("/list", response_model=ResourceListResponse)
async def list_resources(
    media_id: MediaID = Depends(MediaIDParam),
    season_number: Annotated[int | None, Query(gt=0)] = None,
) -> ResourceListResponse:
    return await resource_list_service.list(
        MediaTarget(media_id=media_id, season_number=require_tv_season(media_id, season_number))
    )
