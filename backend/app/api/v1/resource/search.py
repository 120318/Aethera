from typing import Annotated

from app.api.deps import MediaIDParam
from app.schemas.media_id import MediaID
from app.services.application.views.resource_search import ResourceSearchResponse, resource_search_result_view_service
from fastapi import APIRouter, Depends, Query

router = APIRouter()


@router.get("/search", response_model=ResourceSearchResponse)
async def search_resources(
    mid: MediaID = Depends(MediaIDParam),
    site: str | None = Query(None, description="Field description"),
    season_number: Annotated[int | None, Query(gt=0)] = None,
) -> ResourceSearchResponse:
    site_ids = [item.strip() for item in site.split(",") if item.strip()] if site else None
    return await resource_search_result_view_service.get_latest_results(
        media_id=mid,
        season_number=season_number,
        site_ids=site_ids,
    )
