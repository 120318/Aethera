from app.schemas.exception import ConfigurationException
from app.schemas.runtime.indexer_site_health import IndexerSiteHealthGroup, IndexerSiteHealthStatus
from app.services.config.settings_service import settings_service
from app.services.integration.indexer import indexer_gateway
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

router = APIRouter()


class IndexerHealthResponse(BaseModel):
    indexers: list[IndexerSiteHealthGroup] = Field(default_factory=list)


@router.get("/config/indexers/health", response_model=IndexerHealthResponse)
async def list_indexer_health(indexer_id: str | None = Query(None)) -> IndexerHealthResponse:
    stored_map = settings_service.get_indexer_site_health_map()
    groups: list[IndexerSiteHealthGroup] = []
    indexers = settings_service.list_indexers()
    if indexer_id:
        indexers = [item for item in indexers if item.id == indexer_id]
        if not indexers:
            raise ConfigurationException("backendErrors.config.indexerNotFound", params={"id": indexer_id})

    for indexer in indexers:
        stored_group = stored_map[indexer.id] if indexer.id in stored_map else []
        stored_statuses = {status.site_id: status for status in stored_group}
        sites: list[IndexerSiteHealthStatus] = []

        if indexer.enabled:
            try:
                provider_health = await indexer_gateway.get_site_health_for_config(indexer)
                if provider_health:
                    sites.extend(provider_health)
                    live_sites = []
                else:
                    live_sites = await indexer_gateway.list_sites_for_config(indexer)
            except (RuntimeError, ValueError):
                live_sites = []
        else:
            live_sites = []

        if not sites and live_sites:
            for site in live_sites:
                existing = stored_statuses[site.id] if site.id in stored_statuses else None
                if existing:
                    existing.site_name = site.name or existing.site_name
                    existing.indexer_name = indexer.name or existing.indexer_name
                    sites.append(existing)
                else:
                    sites.append(
                        IndexerSiteHealthStatus(
                            indexer_id=indexer.id,
                            indexer_name=indexer.name,
                            site_id=site.id,
                            site_name=site.name,
                            client_type=indexer.type,
                        )
                    )
        elif not sites:
            sites.extend(stored_statuses.values())

        sites.sort(key=lambda item: (item.site_name or item.site_id).lower())
        groups.append(
            IndexerSiteHealthGroup(
                indexer_id=indexer.id,
                indexer_name=indexer.name,
                sites=sites,
            )
        )

    return IndexerHealthResponse(indexers=groups)
