from fastapi import APIRouter
from pydantic import BaseModel

from app.schemas.runtime.settings_runtime import SettingsUsage
from app.services.config.settings_service import settings_service

router = APIRouter()


class DirectoryUsageResponse(BaseModel):
    usage: SettingsUsage


@router.get("/config/directories/{directory_id}/usage", response_model=DirectoryUsageResponse)
async def get_directory_usage(directory_id: str) -> DirectoryUsageResponse:
    return DirectoryUsageResponse(usage=settings_service.get_directory_usage(directory_id))
