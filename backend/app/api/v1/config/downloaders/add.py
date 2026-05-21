import logging

from app.schemas.config import DownloaderProviderConfig
from app.services.config.bootstrap_service import bootstrap_service
from app.services.config.settings_service import settings_service
from fastapi import APIRouter
from pydantic import BaseModel

from app.schemas.exception import ServiceTypeException
logger = logging.getLogger(__name__)
router = APIRouter()
SUPPORTED_DOWNLOADER_TYPES = ["qbittorrent", "rtorrent"]


class DownloaderAddRequest(BaseModel):
    downloader: DownloaderProviderConfig


class DownloaderSingleResponse(BaseModel):
    downloader: DownloaderProviderConfig


@router.post("/config/downloaders", response_model=DownloaderSingleResponse)
async def add_downloader(request: DownloaderAddRequest):
    """Internal helper."""
    if request.downloader.type not in SUPPORTED_DOWNLOADER_TYPES:
        raise ServiceTypeException(service_type=request.downloader.type, supported_types=SUPPORTED_DOWNLOADER_TYPES)
    downloader = settings_service.create_downloader(request.downloader)
    bootstrap_service.recompute_status()
    return DownloaderSingleResponse(downloader=downloader)
