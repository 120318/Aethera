from app.api.v1.common_responses import OperationResponse
from app.services.config.settings_service import settings_service
from fastapi import APIRouter

router = APIRouter()


@router.post("/config/media-servers/set-default/{media_server_id}", response_model=OperationResponse)
async def set_default_media_server(media_server_id: str) -> OperationResponse:
    """Internal helper."""
    settings_service.set_default_media_server(media_server_id)
    return OperationResponse(ok=True)


@router.post("/config/media-servers/clear-default", response_model=OperationResponse)
async def clear_default_media_server() -> OperationResponse:
    settings_service.clear_default_media_server()
    return OperationResponse(ok=True)
