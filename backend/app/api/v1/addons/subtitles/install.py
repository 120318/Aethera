from fastapi import APIRouter

from app.schemas.domain.subtitle import SubtitleInstallRequest, SubtitleInstallResponse
from app.schemas.exception import InvalidRequestException
from app.services.application.workflows.subtitles import subtitle_application_service

router = APIRouter()


@router.post("/install", response_model=SubtitleInstallResponse)
async def install_subtitle(request: SubtitleInstallRequest) -> SubtitleInstallResponse:
    try:
        return await subtitle_application_service.install(request)
    except (OSError, ValueError) as exc:
        raise InvalidRequestException(
            "backendErrors.subtitleOperationFailed",
            params={"reason": str(exc)},
        ) from exc
