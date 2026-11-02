from fastapi import APIRouter

from app.schemas.domain.subtitle import SubtitlePreviewRequest, SubtitlePreviewResponse
from app.schemas.exception import InvalidRequestException
from app.services.application.workflows.subtitles import subtitle_application_service

router = APIRouter()


@router.post("/preview", response_model=SubtitlePreviewResponse)
async def preview_subtitle(request: SubtitlePreviewRequest) -> SubtitlePreviewResponse:
    try:
        return SubtitlePreviewResponse(
            content=await subtitle_application_service.preview(request.candidate_file_id)
        )
    except (OSError, ValueError) as exc:
        raise InvalidRequestException(
            "backendErrors.subtitleOperationFailed",
            params={"reason": str(exc)},
        ) from exc
