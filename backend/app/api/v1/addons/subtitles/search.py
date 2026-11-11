from fastapi import APIRouter

from app.schemas.domain.subtitle import SubtitleSearchRequest, SubtitleSearchResponse
from app.schemas.exception import InvalidRequestException
from app.services.application.workflows.subtitles import subtitle_application_service

router = APIRouter()


@router.post("/search", response_model=SubtitleSearchResponse)
async def search_subtitles(request: SubtitleSearchRequest) -> SubtitleSearchResponse:
    try:
        return SubtitleSearchResponse(
            items=await subtitle_application_service.search_for_file(request.file_id)
        )
    except (OSError, ValueError) as exc:
        raise InvalidRequestException(
            "backendErrors.subtitleOperationFailed",
            params={"reason": str(exc)},
        ) from exc
