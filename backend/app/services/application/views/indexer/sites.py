import logging
import time

from app.schemas.runtime.indexer_sites import IndexerSitesResponse
from app.services.integration.indexer.catalog import indexer_site_catalog_service

logger = logging.getLogger(__name__)


class IndexerSitesService:
    async def list_indexer_sites(self, indexer_id: str | None = None) -> IndexerSitesResponse:
        request_started_at = time.perf_counter()
        groups = await indexer_site_catalog_service.list_indexer_site_groups(indexer_id)
        logger.debug(
            "Indexer sites api completed: groups=%s total_ms=%.1f",
            len(groups),
            (time.perf_counter() - request_started_at) * 1000,
        )
        return IndexerSitesResponse(indexers=groups)


indexer_sites_service = IndexerSitesService()
