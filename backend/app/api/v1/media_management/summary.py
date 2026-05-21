from fastapi import APIRouter
from pydantic import BaseModel

from app.schemas.runtime.media_management import MediaManagementSummary
from app.services.application.views.media_management import media_management_service

router = APIRouter()


class MediaManagementSummaryResponse(BaseModel):
    data: MediaManagementSummary


@router.get("/summary", response_model=MediaManagementSummaryResponse)
async def get_media_management_summary() -> MediaManagementSummaryResponse:
    return MediaManagementSummaryResponse(data=await media_management_service.get_summary())

