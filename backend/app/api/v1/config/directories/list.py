import logging

from app.schemas.config import DirectoryConfig
from app.services.config.settings_service import settings_service
from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


class DirectoryResponse(BaseModel):
    directories: list[DirectoryConfig]


@router.get("/config/directories", response_model=DirectoryResponse)
async def list_directories() -> DirectoryResponse:
    """text
    
    Returns:
        text
    """
    return DirectoryResponse(directories=settings_service.list_directories())
