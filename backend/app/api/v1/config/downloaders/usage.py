from fastapi import APIRouter
from pydantic import BaseModel

from app.schemas.runtime.settings_runtime import SettingsUsage
from app.services.config.settings_service import settings_service

router = APIRouter()


class DownloaderUsageResponse(BaseModel):
    usage: SettingsUsage


@router.get("/config/downloaders/{downloader_id}/usage", response_model=DownloaderUsageResponse)
async def get_downloader_usage(downloader_id: str) -> DownloaderUsageResponse:
    return DownloaderUsageResponse(usage=settings_service.get_downloader_usage(downloader_id))
