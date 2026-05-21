import logging

from app.schemas.config import IndexerProviderConfig
from app.services.config.bootstrap_service import bootstrap_service
from app.services.config.settings_service import settings_service
from fastapi import APIRouter
from pydantic import BaseModel

from app.schemas.exception import ServiceTypeException
logger = logging.getLogger(__name__)
router = APIRouter()


class IndexerAddRequest(BaseModel):
    indexer: IndexerProviderConfig


class IndexerSingleResponse(BaseModel):
    indexer: IndexerProviderConfig


@router.post("/config/indexers", response_model=IndexerSingleResponse)
async def add_indexer(request: IndexerAddRequest):
    """Internal helper."""
    if request.indexer.type not in ["jackett", "prowlarr"]:
        raise ServiceTypeException(service_type=request.indexer.type, supported_types=["jackett", "prowlarr"])
    indexer = settings_service.create_indexer(request.indexer)
    bootstrap_service.recompute_status()
    return IndexerSingleResponse(indexer=indexer)
