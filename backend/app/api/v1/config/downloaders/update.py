from app.schemas.config import DownloaderProviderConfig
from app.services.config.bootstrap_service import bootstrap_service
from app.services.config.settings_service import settings_service
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class DownloaderAddRequest(BaseModel):
    downloader: DownloaderProviderConfig


class DownloaderSingleResponse(BaseModel):
    downloader: DownloaderProviderConfig


@router.put("/config/downloaders/{downloader_id}", response_model=DownloaderSingleResponse)
async def update_downloader(downloader_id: str, request: DownloaderAddRequest):
    """Internal helper."""
    downloader = settings_service.update_downloader(downloader_id, request.downloader)
    bootstrap_service.recompute_status()
    return DownloaderSingleResponse(downloader=downloader)
