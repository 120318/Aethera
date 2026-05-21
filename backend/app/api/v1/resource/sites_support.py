from app.schemas.integration.site_models import SiteInfo
from app.services.integration.indexer.catalog import indexer_site_catalog_service


async def list_available_sites() -> list[SiteInfo]:
    return await indexer_site_catalog_service.list_available_sites()
