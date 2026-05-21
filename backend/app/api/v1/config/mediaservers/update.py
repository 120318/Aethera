from app.schemas.config import MediaServerProviderConfig
from app.services.config.settings_service import settings_service
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class MediaServerAddRequest(BaseModel):
    media_server: MediaServerProviderConfig


class MediaServerSingleResponse(BaseModel):
    media_server: MediaServerProviderConfig


@router.put("/config/media-servers/{media_server_id}", response_model=MediaServerSingleResponse)
async def update_media_server(media_server_id: str, request: MediaServerAddRequest):
    """Internal helper."""
    media_server = settings_service.update_media_server(media_server_id, request.media_server)
    return MediaServerSingleResponse(media_server=media_server)
