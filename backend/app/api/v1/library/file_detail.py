from fastapi import APIRouter, Query

from app.services.application.views.library import library_resource_detail_service
from app.services.application.views.library.resource_detail import LibraryFileDetailResponse

router = APIRouter()


@router.get("/file/detail", response_model=LibraryFileDetailResponse)
async def get_library_file_detail(
    file_id: str = Query(..., description="Library file id"),
) -> LibraryFileDetailResponse:
    return await library_resource_detail_service.get_file_detail(file_id)
