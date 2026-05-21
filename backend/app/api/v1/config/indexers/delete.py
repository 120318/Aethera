from app.api.v1.common_responses import OperationResponse
from app.services.config.bootstrap_service import bootstrap_service
from app.services.config.settings_service import settings_service
from fastapi import APIRouter

router = APIRouter()


@router.delete("/config/indexers/{indexer_id}", response_model=OperationResponse)
async def delete_indexer(indexer_id: str) -> OperationResponse:
    """Internal helper."""
    settings_service.delete_indexer(indexer_id)
    bootstrap_service.recompute_status()
    return OperationResponse(ok=True)
