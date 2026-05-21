import logging

from app.schemas.config import MediaServerProviderConfig
from app.services.config.settings_service import settings_service
from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


class MediaServerResponse(BaseModel):
    media_servers: list[MediaServerProviderConfig]


@router.get("/config/media-servers", response_model=MediaServerResponse)
async def list_media_servers() -> MediaServerResponse:
    """Internal helper."""
    return MediaServerResponse(media_servers=settings_service.list_media_servers())
