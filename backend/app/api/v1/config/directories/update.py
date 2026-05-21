from fastapi import APIRouter
from pydantic import BaseModel

from app.schemas.exception import DirectoryValidationException
from app.schemas.config import DirectoryConfig, TransferMode
from app.schemas.domain.media_types import MediaType
from app.services.config.bootstrap_service import bootstrap_service
from app.services.config.settings_service import settings_service

router = APIRouter()


class DirectoryUpdateRequest(BaseModel):
    """Internal helper."""
    id: str
    name: str
    path: str
    download_path: str
    media_type: MediaType
    enabled: bool
    is_default: bool
    media_server_id: str | None = None
    downloader_id: str | None = None
    movie_template_id: str | None = None  # Internal note.
    tv_template_id: str | None = None  # Internal note.
    downloader_category: str | None = None  # Internal note.
    transfer_mode: TransferMode = TransferMode.HARDLINK


class DirectorySingleResponse(BaseModel):
    directory: DirectoryConfig


@router.put("/config/directories/update", response_model=DirectorySingleResponse)
async def update_directory(request: DirectoryUpdateRequest) -> DirectorySingleResponse:
    """text
    
    Args:
        request: text
        
    Returns:
        text
    """
    # Internal note.
    if request.path:
        settings_service.create_directory_if_not_exists(request.path)
    if request.download_path:
        settings_service.create_directory_if_not_exists(request.download_path)
    
    directory = DirectoryConfig(
        id=request.id,
        name=request.name,
        path=request.path,
        download_path=request.download_path,
        media_type=request.media_type,
        enabled=request.enabled,
        is_default=request.is_default,
        media_server_id=request.media_server_id,
        downloader_id=request.downloader_id,
        movie_template_id=request.movie_template_id,
        tv_template_id=request.tv_template_id,
        download_category=request.downloader_category,
        transfer_mode=request.transfer_mode,
    )
    
    # Internal note.
    errors = settings_service.validate_directory(directory)
    if errors:
        raise DirectoryValidationException("backendErrors.directoryValidationFailed", params={"errors": ";".join(errors)})
    
    directory = settings_service.update_directory(directory)
    bootstrap_service.recompute_status()
    return DirectorySingleResponse(directory=directory)
