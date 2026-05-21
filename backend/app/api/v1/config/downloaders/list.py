import logging

from app.schemas.config import DownloaderProviderConfig
from app.services.config.settings_service import settings_service
from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


class DownloaderResponse(BaseModel):
    downloaders: list[DownloaderProviderConfig]


@router.get("/config/downloaders", response_model=DownloaderResponse)
async def list_downloaders() -> DownloaderResponse:
    """Internal helper."""
    return DownloaderResponse(downloaders=settings_service.list_downloaders())
