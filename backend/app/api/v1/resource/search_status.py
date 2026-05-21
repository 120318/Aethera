from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.schemas.media_id import MediaID
from app.api.deps import MediaIDParam
from app.services.application.workflows.resource_search import resource_search_service

router = APIRouter()

class SearchStatusResponse(BaseModel):
    has_searched: bool

@router.get("/search/status", response_model=SearchStatusResponse)
async def get_search_status(mid: MediaID = Depends(MediaIDParam)):
    """
    Check if local search results exist for this media.
    """
    return SearchStatusResponse(has_searched=resource_search_service.get_latest_media_cached_results(mid) is not None)
