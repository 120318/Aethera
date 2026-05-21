import logging

from app.schemas.config import IndexerProviderConfig
from app.services.config.settings_service import settings_service
from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


class IndexerResponse(BaseModel):
    indexers: list[IndexerProviderConfig]


@router.get("/config/indexers", response_model=IndexerResponse)
async def list_indexers() -> IndexerResponse:
    """Internal helper."""
    return IndexerResponse(indexers=settings_service.list_indexers())
