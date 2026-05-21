from fastapi import APIRouter, Query

from app.schemas.runtime.indexer_sites import IndexerSitesResponse
from app.services.application.views.indexer.sites import indexer_sites_service

router = APIRouter()


@router.get("/config/indexers/sites", response_model=IndexerSitesResponse)
async def list_indexer_sites(indexer_id: str | None = Query(None)) -> IndexerSitesResponse:
    return await indexer_sites_service.list_indexer_sites(indexer_id)
