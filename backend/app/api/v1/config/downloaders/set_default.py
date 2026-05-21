from app.api.v1.common_responses import OperationResponse
from app.services.config.bootstrap_service import bootstrap_service
from app.services.config.settings_service import settings_service
from fastapi import APIRouter

router = APIRouter()


@router.post("/config/downloaders/set-default/{downloader_id}", response_model=OperationResponse)
async def set_default_downloader(downloader_id: str) -> OperationResponse:
    """Internal helper."""
    settings_service.set_default_downloader(downloader_id)
    bootstrap_service.recompute_status()
    return OperationResponse(ok=True)


@router.post("/config/downloaders/clear-default", response_model=OperationResponse)
async def clear_default_downloader() -> OperationResponse:
    settings_service.clear_default_downloader()
    bootstrap_service.recompute_status()
    return OperationResponse(ok=True)
