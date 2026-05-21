from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.schemas.config import BrowseSource
from app.schemas.exception.exceptions import InvalidRequestException
from app.schemas.domain.search_models import MediaSearchResult
from app.schemas.domain.media_types import MediaType
from app.services.domain.media import media_service

router = APIRouter()

class SearchResponse(BaseModel):
    results: list[MediaSearchResult]

@router.get("/search", response_model=SearchResponse)
async def search_media(
    query: str = Query(..., description="Search query"),
    start: int = Query(0, description="Start offset"),
    count: int = Query(10, description="Number of results to return"),
    media_type: MediaType | None = Query(None, description="Media type filter"),
    year: int | None = Query(None, description="Year filter"),
    source: BrowseSource | None = Query(None, description="Explicit search source"),
) -> SearchResponse:
    if not query:
        raise InvalidRequestException("backendErrors.queryRequired")
    results = await media_service.search(
        query,
        media_type=media_type,
        start=start,
        limit=count,
        year=year,
        source=source,
    )
    media_service.mark_viewed_search_results(results)
    return SearchResponse(results=results)
