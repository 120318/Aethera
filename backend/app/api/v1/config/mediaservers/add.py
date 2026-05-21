import logging

from app.schemas.config import MediaServerProviderConfig
from app.services.config.settings_service import settings_service
from fastapi import APIRouter
from pydantic import BaseModel

from app.schemas.exception import ServiceTypeException
logger = logging.getLogger(__name__)
router = APIRouter()


class MediaServerAddRequest(BaseModel):
    media_server: MediaServerProviderConfig


class MediaServerSingleResponse(BaseModel):
    media_server: MediaServerProviderConfig


@router.post("/config/media-servers", response_model=MediaServerSingleResponse)
async def add_media_server(request: MediaServerAddRequest):
    """Internal helper."""
    if request.media_server.type not in ["jellyfin"]:
        raise ServiceTypeException(service_type=request.media_server.type, supported_types=["jellyfin"])
    media_server = settings_service.create_media_server(request.media_server)
    return MediaServerSingleResponse(media_server=media_server)
