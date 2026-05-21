"""
textqBittorrenttextAPItext
"""
from app.services.domain.download import download_service
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class SyncResponse(BaseModel):
    status: str
    message_key: str
    params: dict[str, int]
    success: bool
    updated_count: int


@router.post("/sync", response_model=SyncResponse)
async def sync_download_history() -> SyncResponse:
    """
    textqBittorrenttext
    
    Returns:
        text
    """
    active_result = await download_service.sync_active_downloads()

    fast_sync_count = active_result.updated
    total_updated = fast_sync_count

    return SyncResponse(
        status="ok",
        message_key="operationMessages.downloadHistory.synced",
        params={"total": total_updated, "fast_sync": fast_sync_count},
        success=True,
        updated_count=total_updated,
    )
