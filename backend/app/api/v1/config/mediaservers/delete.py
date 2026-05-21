from app.api.v1.common_responses import OperationResponse
from app.services.config.settings_service import settings_service
from fastapi import APIRouter

router = APIRouter()


@router.delete("/config/media-servers/{media_server_id}", response_model=OperationResponse)
async def delete_media_server(media_server_id: str) -> OperationResponse:
    """Internal helper."""
    settings_service.delete_media_server(media_server_id)
    return OperationResponse(ok=True)
