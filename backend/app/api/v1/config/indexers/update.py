from app.schemas.config import IndexerProviderConfig
from app.services.config.bootstrap_service import bootstrap_service
from app.services.config.settings_service import settings_service
from fastapi import APIRouter
from pydantic import BaseModel
from app.api.v1.common_responses import OperationResponse

router = APIRouter()


class IndexerAddRequest(BaseModel):
    indexer: IndexerProviderConfig


class IndexerSingleResponse(BaseModel):
    indexer: IndexerProviderConfig


class IndexerListRequest(BaseModel):
    indexers: list[IndexerProviderConfig]


@router.put("/config/indexers/{indexer_id}", response_model=IndexerSingleResponse)
async def update_indexer(indexer_id: str, request: IndexerAddRequest):
    """Internal helper."""
    indexer = settings_service.update_indexer(indexer_id, request.indexer)
    bootstrap_service.recompute_status()
    return IndexerSingleResponse(indexer=indexer)


@router.put("/config/indexers/reorder", response_model=OperationResponse)
async def reorder_indexers(request: IndexerListRequest) -> OperationResponse:
    settings_service.reorder_indexers(request.indexers)
    return OperationResponse(ok=True, message_key="operationMessages.config.indexerOrderUpdated")
