from app.api.deps import MediaIDParam
from app.schemas.media_id import MediaID
from app.schemas.runtime.library_overview import LibraryOverviewResponse
from app.services.application.views.library import library_overview_service
from fastapi import APIRouter, Depends

router = APIRouter()


@router.get("/overview", response_model=LibraryOverviewResponse)
async def get_library_overview(
    media_id: MediaID = Depends(MediaIDParam),
) -> LibraryOverviewResponse:
    return await library_overview_service.get_overview(media_id)
