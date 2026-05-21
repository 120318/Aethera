from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import MediaIDParam, require_tv_season
from app.schemas.media_id import MediaID
from app.schemas.runtime.library_resource_list import LibraryListResponse
from app.services.application.views.library import library_resource_list_service

router = APIRouter()


@router.get("/list", response_model=LibraryListResponse, response_model_exclude_none=True)
async def list_library_resources(
    media_id: MediaID = Depends(MediaIDParam),
    season_number: Annotated[int | None, Query(gt=0)] = None,
) -> LibraryListResponse:
    return await library_resource_list_service.list_resources(
        media_id,
        season_number=require_tv_season(media_id, season_number),
    )
