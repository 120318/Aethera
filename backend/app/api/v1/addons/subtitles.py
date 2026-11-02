from fastapi import APIRouter

from app.schemas.domain.subtitle import (
    SubtitleInstallRequest,
    SubtitlePreviewRequest,
    SubtitlePreviewResponse,
    SubtitleInstallResponse,
    SubtitleSearchRequest,
    SubtitleSearchResponse,
)
from app.services.application.workflows.subtitles import subtitle_application_service
from app.schemas.exception import InvalidRequestException

router = APIRouter(prefix="/subtitles")


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


@router.post("/install", response_model=SubtitleInstallResponse)
async def install_subtitle(request: SubtitleInstallRequest) -> SubtitleInstallResponse:
    try:
        return await subtitle_application_service.install(request)
    except (OSError, ValueError) as exc:
        raise InvalidRequestException(
            "backendErrors.subtitleOperationFailed",
            params={"reason": str(exc)},
        ) from exc
